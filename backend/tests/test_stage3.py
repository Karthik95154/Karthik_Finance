import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.accounting_service import AccountingService, DEFAULT_CHART_OF_ACCOUNTS


@pytest.mark.asyncio
async def test_accounting_service_payload_construction():
    """Verify that AccountingService correctly builds the notebook-compliant JSON payload."""
    sample_invoice = {
        "invoice_number": "INV-2026-001",
        "vendor_name": "Apex Tech Solutions",
        "total_amount": 11800.0,
        "line_items": [
            {
                "description": "Cloud Hosting Services",
                "quantity": 1.0,
                "unit_price": 10000.0,
                "total": 11800.0,
            }
        ],
    }

    service = AccountingService()

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: {
            "accounting": [
                {
                    "line_index": 1,
                    "source_description": "Cloud Hosting Services",
                    "ai_account_id": "ACC_1",
                    "ai_account_name": "Cloud Hosting & Infrastructure",
                    "ai_confidence": 0.95,
                    "ai_needs_review": False,
                    "final_account_id": "ACC_1",
                    "final_account_name": "Cloud Hosting & Infrastructure",
                    "tax_analysis": {
                        "tax_present": True,
                        "tax_types": ["CGST", "SGST"],
                    },
                }
            ],
            "tds": {
                "applicable": False,
                "confidence": 0.9,
                "needs_review": False,
                "reason": "Standard services under threshold",
            },
        }
        mock_post.return_value = mock_response

        result = await service.categorize_accounting(sample_invoice)

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
        assert result["accounting"][0]["ai_account_name"] == "Cloud Hosting & Infrastructure"
        assert result["tds"]["applicable"] is False


@pytest.mark.asyncio
async def test_accounting_service_empty_dict():
    """Verify AccountingService raises ValueError on empty dictionary."""
    service = AccountingService()
    with pytest.raises(ValueError, match="non-empty"):
        await service.categorize_accounting({})


@pytest.mark.asyncio
async def test_accounting_service_timeout_handling():
    """Verify AccountingService handles timeouts with descriptive TimeoutError."""
    import httpx

    service = AccountingService()
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timed out")):
        with pytest.raises(TimeoutError, match="timed out"):
            await service.categorize_accounting({"vendor_name": "Test Vendor"})


@pytest.mark.asyncio
async def test_accounting_service_connection_error():
    """Verify AccountingService handles connection drop with descriptive RuntimeError."""
    import httpx

    service = AccountingService()
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(RuntimeError, match="unreachable"):
            await service.categorize_accounting({"vendor_name": "Test Vendor"})


@pytest.mark.asyncio
async def test_invoice_categorize_endpoint_not_found():
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
            response = await client.post(f"/api/v1/invoices/{random_id}/categorize")
            assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)

