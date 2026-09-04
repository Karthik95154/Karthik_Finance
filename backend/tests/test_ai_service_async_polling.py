import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from app.services.ai_service import AIService


@pytest.mark.asyncio
async def test_extract_invoice_vlm_async_polling_success():
    """
    Tests that AIService correctly handles the Async Job Polling protocol:
    1. POST /api/infer/extract-invoice returns {"job_id": "job_123", "status": "processing"}
    2. GET /api/infer/jobs/job_123 returns {"status": "processing"} on first poll
    3. GET /api/infer/jobs/job_123 returns {"status": "completed", "result": {...}} on second poll
    """
    service = AIService(base_url="http://mock-colab-vlm.ngrok.dev")
    service.timeout = 30.0

    mock_submit_resp = MagicMock()
    mock_submit_resp.status_code = 200
    mock_submit_resp.json.return_value = {
        "job_id": "VLM-20260902-123456-0001",
        "status": "processing",
        "poll_endpoint": "/api/infer/jobs/VLM-20260902-123456-0001",
    }

    mock_poll_processing = MagicMock()
    mock_poll_processing.status_code = 200
    mock_poll_processing.json.return_value = {
        "job_id": "VLM-20260902-123456-0001",
        "status": "processing",
        "elapsed_seconds": 4.5,
    }

    expected_invoice_data = {
        "data": {
            "invoice_number": "INV-2026-1722",
            "vendor_name": "Satpura Industrial Fabrications Pvt. Ltd.",
            "vendor_gstin": "36AABCS7845R1Z4",
            "subtotal": 973600.0,
            "total_amount": 1148848.0,
        },
        "needs_review": False,
    }

    mock_poll_completed = MagicMock()
    mock_poll_completed.status_code = 200
    mock_poll_completed.json.return_value = {
        "job_id": "VLM-20260902-123456-0001",
        "status": "completed",
        "result": expected_invoice_data,
        "latency_seconds": 334.0,
    }

    call_count = 0

    async def mock_post(*args, **kwargs):
        return mock_submit_resp

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_poll_processing
        return mock_poll_completed

    with patch("httpx.AsyncClient.post", side_effect=mock_post), \
         patch("httpx.AsyncClient.get", side_effect=mock_get), \
         patch("asyncio.sleep", new_callable=AsyncMock):

        result = await service.extract_invoice_vlm(b"%PDF-1.4 dummy pdf bytes")
        assert result == expected_invoice_data
        assert call_count == 2


@pytest.mark.asyncio
async def test_extract_invoice_vlm_legacy_synchronous_fallback():
    """
    Tests that AIService remains fully backwards-compatible if a server returns
    the direct extraction result synchronously without a job_id.
    """
    service = AIService(base_url="http://mock-colab-vlm.ngrok.dev")
    service.timeout = 30.0

    expected_direct_result = {
        "data": {
            "invoice_number": "INV-DIRECT-001",
            "vendor_name": "Direct Test Vendor",
            "total_amount": 5000.0,
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = expected_direct_result

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await service.extract_invoice_vlm(b"%PDF-1.4 dummy pdf bytes")
        assert result == expected_direct_result
