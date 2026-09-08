import uuid
import hashlib
import base64
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.ai_service import ai_service


# 1. Test SHA256 integrity surviving Base64 encoding & decoding
def test_sha256_base64_encode_decode_integrity():
    raw_pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    original_sha256 = hashlib.sha256(raw_pdf_bytes).hexdigest()

    encoded_b64 = base64.b64encode(raw_pdf_bytes).decode("utf-8")
    decoded_bytes = base64.b64decode(encoded_b64.encode("utf-8"))
    decoded_sha256 = hashlib.sha256(decoded_bytes).hexdigest()

    assert original_sha256 == decoded_sha256
    assert decoded_bytes == raw_pdf_bytes


# 2. Test File Signature (Magic Byte) Detection
def test_file_signature_detection():
    from tests.test_vlm_file_detection import detect_file_type
    
    assert detect_file_type(b"%PDF-1.5 test PDF data") == "pdf"
    assert detect_file_type(b"\xff\xd8\xff\xe0\x00\x10JFIF") == "jpeg"
    assert detect_file_type(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR") == "png"
    assert detect_file_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    assert detect_file_type(b"corrupted binary data") == "unknown"


# 3. End-to-End Async API Integration Test: Upload, Mock Removal on Failure, Retry & User Isolation
@pytest.mark.asyncio
async def test_vlm_pipeline_no_mock_data_and_retry_isolation():
    run_id = uuid.uuid4().hex[:6]
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register User A and User B
        res_a = await client.post("/api/v1/auth/token", json={"email": f"vlm_usera_{run_id}@example.com", "dev_name": "User A"})
        assert res_a.status_code == 200
        token_a = res_a.json()["access_token"]

        res_b = await client.post("/api/v1/auth/token", json={"email": f"vlm_userb_{run_id}@example.com", "dev_name": "User B"})
        assert res_b.status_code == 200
        token_b = res_b.json()["access_token"]

        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Step A: User A uploads an invalid/corrupted file
        corrupted_bytes = b"CORRUPTED_NON_PDF_BINARY_DATA"
        files = {"file": ("corrupted.pdf", corrupted_bytes, "application/pdf")}

        # Mock ai_service to throw exception simulating Colab inference failure
        with patch.object(ai_service, "extract_invoice_vlm", side_effect=RuntimeError("Colab extraction job failed: PyMuPDF FileDataError")):
            res_upload = await client.post("/api/v1/invoices/upload", files=files, headers=headers_a)
            assert res_upload.status_code == 201
            inv_data = res_upload.json()
            invoice_id = inv_data["invoice_id"]

            # Directly run background worker for immediate synchronous execution in test
            from app.services.invoice_processing import process_invoice_background
            await process_invoice_background(uuid.UUID(invoice_id))

            # Step B: Verify Invoice Status is FAILED and NO Mock Data was generated
            inv_res = await client.get(f"/api/v1/invoices/{invoice_id}", headers=headers_a)
            assert inv_res.status_code == 200
            inv_detail = inv_res.json()

            assert inv_detail["status"] == "FAILED"
            assert inv_detail["raw_vlm_output"] is None
            assert inv_detail["current_vlm_output"] is None
            assert ("VLM extraction failed" in inv_detail["error_message"] or "Kimi K3 inference failed" in inv_detail["error_message"])

            # Step C: Verify User B CANNOT retry User A's invoice (User Isolation -> 404)
            retry_b = await client.post(f"/api/v1/invoices/{invoice_id}/retry_extraction", headers=headers_b)
            assert retry_b.status_code == 404

            # Step D: User A retries extraction using original stored file
            with patch.object(ai_service, "extract_invoice_vlm", return_value={"confidence_score": 0.95, "data": {"invoice_number": "REAL-INV-100", "total_amount": 5000.0}}):
                retry_a = await client.post(f"/api/v1/invoices/{invoice_id}/retry_extraction", headers=headers_a)
                assert retry_a.status_code == 202
                assert retry_a.json()["status"] == "PENDING"

                # Run background worker for retry
                await process_invoice_background(uuid.UUID(invoice_id))

                # Step E: Verify Invoice Status is HITL_REVIEW with real model output
                inv_res_after = await client.get(f"/api/v1/invoices/{invoice_id}", headers=headers_a)
                assert inv_res_after.status_code == 200
                inv_detail_after = inv_res_after.json()

                assert inv_detail_after["status"] in ("HITL_REVIEW", "FINAL_HITL_REVIEW")
                assert inv_detail_after["raw_vlm_output"]["data"]["invoice_number"] == "REAL-INV-100"
                assert inv_detail_after["raw_vlm_output"]["data"]["total_amount"] == 5000.0
