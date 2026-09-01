import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.accounting_service import AccountingService, DEFAULT_CHART_OF_ACCOUNTS
from app.services.tds_service import TDSService
from app.core.security import create_access_token


@pytest.fixture
def auth_headers():
    token = create_access_token(
        user_id=str(uuid.uuid4()),
        email="finance@default-org.com",
        tenant_id="default-tenant-001",
        role="FINANCE",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_coa_service_payload_and_response():
    """Verify that AccountingService calls /api/infer/categorize-accounting and parses accounting array."""
    sample_invoice = {
        "invoice_number": "INV-2026-001",
        "vendor_name": "Apex Tech Solutions",
        "total_amount": 11800.0,
        "line_items": [
            {
                "line_index": 1,
                "description": "Cloud Hosting Services",
                "quantity": 1.0,
                "unit_price": 10000.0,
                "total": 11800.0,
            }
        ],
    }

    service = AccountingService(base_url="https://mock-coa.dev")

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "accounting": [
                {
                    "line_index": 1,
                    "source_description": "Cloud Hosting Services",
                    "account_id": "ACC_1",
                    "account_name": "Cloud Hosting & Infrastructure",
                    "confidence_score": 0.97,
                    "ai_needs_review": False,
                    "accounting_reason": "Matches server hosting pattern",
                }
            ]
        }
        mock_post.return_value = mock_response

        result = await service.categorize_accounting(
            sample_invoice,
            chart_of_accounts=DEFAULT_CHART_OF_ACCOUNTS,
        )

        # Assert payload was sent with valid keys
        mock_post.assert_called_once()
        sent_payload = mock_post.call_args.kwargs["json"]
        assert "invoice_json" in sent_payload
        assert sent_payload["invoice_json"]["invoice_number"] == "INV-2026-001"
        assert "chart_of_accounts" in sent_payload
        assert len(sent_payload["chart_of_accounts"]) == len(DEFAULT_CHART_OF_ACCOUNTS)
        assert "available_taxes" in sent_payload

        # Assert response preservation
        assert len(result["accounting"]) == 1
        assert result["accounting"][0]["account_name"] == "Cloud Hosting & Infrastructure"
        assert result["accounting"][0]["confidence_score"] == 0.97
        assert result["accounting"][0]["ai_needs_review"] is False


@pytest.mark.asyncio
async def test_coa_service_failure_returns_review_required():
    """Verify AccountingService returns explicit review records and does NOT fabricate accounts on failure."""
    import httpx

    service = AccountingService(base_url="https://mock-coa.dev")
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        res = await service.categorize_accounting({
            "vendor_name": "Test Vendor",
            "line_items": [{"line_index": 1, "description": "Consulting"}]
        })
        assert "accounting" in res
        line = res["accounting"][0]
        assert line["account_id"] is None
        assert line["account_name"] is None
        assert line["ai_needs_review"] is True
        assert "COA service unavailable" in line["accounting_reason"]


@pytest.mark.asyncio
async def test_tds_service_payload_and_response():
    """Verify that TDSService calls POST /api/infer/tds with invoice_json and parses tds_assessment."""
    sample_invoice = {
        "invoice_number": "INV-2026-002",
        "vendor_name": "Apex Legal Advisory",
        "subtotal": 50000.0,
        "total_amount": 59000.0,
        "line_items": [{"description": "Legal opinion", "taxable_amount": 50000.0}],
    }

    service = TDSService(base_url="https://mock-tds.dev")

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tds_assessment": {
                "tds_applicable": True,
                "nature_of_payment": "Professional services",
                "tds_provision": "Section 393",
                "tds_section": "Table 6(ii)",
                "tds_rate": 10.0,
                "tds_base_amount": 50000.0,
                "proposed_tds_amount": 5000.0,
                "tds_needs_review": False,
                "tds_reasoning": "Professional legal services exceed statutory threshold",
            }
        }
        mock_post.return_value = mock_response

        result = await service.assess_tds(sample_invoice)
        mock_post.assert_called_once()
        sent_payload = mock_post.call_args.kwargs["json"]
        assert sent_payload == {"invoice_json": sample_invoice}

        assert "tds_assessment" in result
        assess = result["tds_assessment"]
        assert assess["tds_applicable"] is True
        assert assess["tds_rate"] == 10.0
        assert assess["proposed_tds_amount"] == 5000.0


@pytest.mark.asyncio
async def test_tds_service_failure_returns_review_required():
    """Verify TDSService returns safe review required structure without fabricating TDS values."""
    import httpx

    service = TDSService(base_url="https://mock-tds.dev")
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
        res = await service.assess_tds({"vendor_name": "Test Vendor"})
        assert "tds_assessment" in res
        assess = res["tds_assessment"]
        assert assess["tds_applicable"] is None
        assert assess["proposed_tds_amount"] is None
        assert assess["tds_needs_review"] is True
        assert "Qwen TDS service unavailable" in assess["tds_reasoning"]


@pytest.mark.asyncio
async def test_invoice_categorize_endpoint_not_found(auth_headers):
    """Verify 404 response on unknown invoice ID for categorize endpoint."""
    from app.db.database import get_db

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            random_id = str(uuid.uuid4())
            response = await client.post(f"/api/v1/invoices/{random_id}/categorize", headers=auth_headers)
            assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
