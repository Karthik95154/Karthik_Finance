import pytest
import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security_util import encrypt_data, decrypt_data
from app.storage.supabase_storage import storage_service
from app.services.imap_service import imap_service
from app.db.database import get_db
from app.db.models import Invoice, Integration


def test_encryption_decryption():
    """Verify that credentials can be encrypted and decrypted correctly using Fernet."""
    test_pwd = "my_app_password_123"
    encrypted = encrypt_data(test_pwd)
    assert encrypted != test_pwd
    assert decrypt_data(encrypted) == test_pwd


@pytest.mark.asyncio
async def test_settings_api_flow():
    """Verify settings configure, get, and disconnect endpoints work correctly and mask passwords."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    
    # Mocking select(Integration) to return None (no config yet)
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Mock IMAP validate connection to succeed
            with patch.object(imap_service, "validate_connection", return_value=None):
                # 1. Configure settings
                payload = {
                    "imap_server": "imap.gmail.com",
                    "imap_port": 993,
                    "email_address": "finance@company.com",
                    "password": "my_google_app_password"
                }
                res = await client.post("/api/v1/settings/integrations/imap_email/configure", json=payload)
                assert res.status_code == 200
                assert res.json()["success"] is True
                assert res.json()["status"] == "connected"
                assert res.json()["config"]["password"] == "••••••••••••••••"

                # Setup DB mock to return the integration we just configured
                mock_integration = Integration(
                    id="imap_email",
                    status="connected",
                    config={
                        "imap_server": "imap.gmail.com",
                        "imap_port": 993,
                        "email_address": "finance@company.com",
                        "password": encrypt_data("my_google_app_password")
                    }
                )
                mock_result.scalar_one_or_none.return_value = mock_integration

                # 2. Get settings (verify masked password)
                res = await client.get("/api/v1/settings/integrations/imap_email")
                assert res.status_code == 200
                assert res.json()["status"] == "connected"
                assert res.json()["config"]["email_address"] == "finance@company.com"
                assert res.json()["config"]["password"] == "••••••••••••••••"

                # 3. Disconnect settings
                res = await client.post("/api/v1/settings/integrations/imap_email/disconnect")
                assert res.status_code == 200
                assert res.json()["status"] == "disconnected"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_email_polling_and_inbox_lifecycle():
    """Verify IMAP polling, staged inbox list, process, and delete endpoints flow."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    
    # Mocking select(Integration) to return active configuration
    mock_integration = Integration(
        id="imap_email",
        status="connected",
        config={
            "imap_server": "imap.gmail.com",
            "imap_port": 993,
            "email_address": "finance@company.com",
            "password": encrypt_data("my_google_app_password")
        }
    )
    
    mock_result.scalar_one_or_none.return_value = mock_integration
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            mock_attachment = {
                "email_subject": "Invoice for Coastal Goods",
                "email_sender": "billing@coastal.com",
                "email_received_at": None,
                "email_message_id": "msg-uid-101",
                "filename": "coastal_goods_invoice.pdf",
                "mime_type": "application/pdf",
                "file_bytes": b"PDF dummy content bytes",
                "file_hash": hashlib.sha256(b"PDF dummy content bytes").hexdigest()
            }
            poll_return_val = {
                "attachments": [mock_attachment],
                "errors": [],
                "emails_checked": 1,
                "attachments_found": 1
            }

            # 1. Trigger email poll (with new unique attachment)
            with patch.object(imap_service, "poll_mailbox", return_value=poll_return_val), \
                 patch.object(storage_service, "upload_file", return_value="uploads/test_path.pdf"):
                
                # Mock Integration select
                mock_result.scalar_one_or_none.return_value = mock_integration
                # Mock Invoice duplicate check (returns None for new file)
                mock_result.scalars.return_value.first.return_value = None

                res = await client.post("/api/v1/email/poll")
                assert res.status_code == 200
                data = res.json()
                assert data["success"] is True
                assert data["new_documents"] == 1
                assert data["duplicates"] == 0

            # 2. List staged documents
            mock_invoice = Invoice(
                id=uuid.uuid4(),
                file_path="uploads/test_path.pdf",
                file_name="coastal_goods_invoice.pdf",
                file_size=100,
                mime_type="application/pdf",
                file_hash=hashlib.sha256(b"PDF dummy content bytes").hexdigest(),
                status="STAGED",
                accounting_status="STAGED",
                email_subject="Invoice for Coastal Goods",
                email_sender="billing@coastal.com",
                email_received_at=None,
                email_message_id="msg-uid-101"
            )
            mock_result.scalars.return_value.all.return_value = [mock_invoice]
            
            res = await client.get("/api/v1/inbox/staged")
            assert res.status_code == 200
            staged_list = res.json()
            assert len(staged_list) == 1
            assert staged_list[0]["file_name"] == "coastal_goods_invoice.pdf"

            # 3. Trigger email poll again (verify SHA-256 duplicate handling)
            with patch.object(imap_service, "poll_mailbox", return_value=poll_return_val):
                # Mock duplicate check to return mock_invoice
                mock_result.scalars.return_value.first.return_value = mock_invoice

                res = await client.post("/api/v1/email/poll")
                assert res.status_code == 200
                data_dup = res.json()
                assert data_dup["new_documents"] == 0
                assert data_dup["duplicates"] == 1

            # 4. Process the staged document (promote to PENDING)
            mock_result.scalar_one_or_none.side_effect = None
            mock_result.scalar_one_or_none.return_value = mock_invoice
            
            with patch("app.api.v1.inbox.process_invoice_background") as mock_process_bg:
                res = await client.post(f"/api/v1/inbox/staged/{mock_invoice.id}/process")
                assert res.status_code == 200
                assert res.json()["success"] is True
                assert res.json()["status"] == "PENDING"
                mock_process_bg.assert_called_once()

            # 5. Delete staged document
            with patch.object(storage_service, "delete_file", return_value=True):
                res = await client.delete(f"/api/v1/inbox/staged/{mock_invoice.id}")
                assert res.status_code == 200
                assert res.json()["success"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_pdf_preview_pages():
    """Verify PDF multi-page rendering API correctly extracts pages as base64 images using PyMuPDF."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    
    mock_invoice = Invoice(
        id=uuid.uuid4(),
        file_path="uploads/test_path.pdf",
        file_name="invoice.pdf",
        mime_type="application/pdf"
    )
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result
    
    async def override_get_db():
        yield mock_db
        
    app.dependency_overrides[get_db] = override_get_db
    
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(storage_service, "download_file", return_value=b"mock-pdf-bytes"), \
                 patch("fitz.open") as mock_fitz_open:
                
                # Mock fitz document and page
                mock_doc = MagicMock()
                mock_doc.page_count = 2
                mock_page = MagicMock()
                mock_pixmap = MagicMock()
                mock_pixmap.tobytes.return_value = b"png-bytes"
                mock_page.get_pixmap.return_value = mock_pixmap
                mock_doc.load_page.return_value = mock_page
                mock_fitz_open.return_value = mock_doc
                
                res = await client.get(f"/api/v1/invoices/{mock_invoice.id}/pages")
                assert res.status_code == 200
                data = res.json()
                assert "pages" in data
                assert len(data["pages"]) == 2
                assert data["pages"][0].startswith("data:image/png;base64,")
    finally:
        app.dependency_overrides.pop(get_db, None)

