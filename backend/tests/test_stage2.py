import pytest
import base64
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.ai_service import AIService
from app.services.invoice_processing import process_invoice_background


@pytest.mark.asyncio
async def test_ai_service_payload_construction():
    """Verify that AIService correctly encodes raw file bytes into base64 payload."""
    raw_pdf_bytes = b"%PDF-1.4 test invoice content"
    service = AIService()

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: {
            "data": {
                "invoice_number": "INV-2026-001",
                "vendor_name": "Acme Supplies",
                "total_amount": 1180.00,
                "line_items": [
                    {
                        "description": "Office Supplies",
                        "quantity": 10.0,
                        "unit_price": 100.0,
                        "taxable_amount": 1000.0,
                        "cgst_amount": 90.0,
                        "sgst_amount": 90.0,
                        "total": 1180.0,
                    }
                ],
                "additional_fields": {"custom_tag": "internal_ref_99"},
            },
            "field_sources": {"invoice_number": "llm"},
            "needs_review": False,
        }
        mock_post.return_value = mock_response

        result = await service.extract_invoice_vlm(raw_pdf_bytes)

        # Assert payload was sent with valid base64
        mock_post.assert_called_once()
        sent_payload = mock_post.call_args.kwargs["json"]
        assert "image_base64" in sent_payload
        assert base64.b64decode(sent_payload["image_base64"]) == raw_pdf_bytes

        # Assert complete raw result is preserved
        assert result["data"]["invoice_number"] == "INV-2026-001"
        assert result["data"]["additional_fields"]["custom_tag"] == "internal_ref_99"


@pytest.mark.asyncio
async def test_ai_service_empty_bytes():
    """Verify AIService raises ValueError on empty bytes."""
    service = AIService()
    with pytest.raises(ValueError, match="empty"):
        await service.extract_invoice_vlm(b"")


@pytest.mark.asyncio
async def test_ai_service_timeout_handling():
    """Verify AIService handles timeouts with descriptive TimeoutError."""
    import httpx
    service = AIService()

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(TimeoutError, match="timed out"):
            await service.extract_invoice_vlm(b"sample bytes")


@pytest.mark.asyncio
async def test_ai_service_connection_error():
    """Verify AIService handles connection drops with descriptive RuntimeError."""
    import httpx
    service = AIService()

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(RuntimeError, match="unreachable"):
            await service.extract_invoice_vlm(b"sample bytes")


@pytest.mark.asyncio
async def test_invoice_status_endpoint_not_found():
    """Verify 404 response on unknown invoice ID for status endpoint."""
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
            response = await client.get(f"/api/v1/invoices/{random_id}/status")
            assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)



@pytest.mark.asyncio
async def test_invoice_update_endpoint():
    """Verify PUT /api/v1/invoices/{id} updates current_vlm_output with CORS headers."""
    from datetime import datetime, timezone
    from app.db.database import get_db
    from app.db.models import Invoice

    mock_invoice = Invoice(
        id=uuid.uuid4(),
        file_path="uploads/test.png",
        file_name="test.png",
        file_size=1024,
        mime_type="image/png",
        file_hash="hash123",
        status="COMPLETED",
        raw_vlm_output={"data": {"vendor_name": "Original Vendor"}},
        current_vlm_output={"data": {"vendor_name": "Original Vendor"}},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {"current_vlm_output": {"data": {"vendor_name": "Edited Vendor"}}}
            response = await client.put(
                f"/api/v1/invoices/{mock_invoice.id}",
                headers={"Origin": "http://localhost:3002"},
                json=payload,
            )
            assert response.status_code == 200
            assert response.headers.get("access-control-allow-origin") == "http://localhost:3002"
            assert mock_invoice.current_vlm_output == payload["current_vlm_output"]
            assert mock_invoice.raw_vlm_output == {"data": {"vendor_name": "Original Vendor"}}
    finally:
        app.dependency_overrides.pop(get_db, None)



