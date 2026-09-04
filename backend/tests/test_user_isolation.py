import uuid
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_user_level_invoice_isolation():
    run_id = uuid.uuid4().hex[:6]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register/Login User A
        res_a = await client.post("/api/v1/auth/token", json={"email": f"usera_{run_id}@example.com", "dev_name": "User A"})
        assert res_a.status_code == 200
        token_a = res_a.json()["access_token"]

        # Register/Login User B
        res_b = await client.post("/api/v1/auth/token", json={"email": f"userb_{run_id}@example.com", "dev_name": "User B"})
        assert res_b.status_code == 200
        token_b = res_b.json()["access_token"]

        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 1. User A uploads an invoice
        file_content = f"%PDF-1.4 test invoice for user A {run_id}".encode()
        files = {"file": ("invoice_user_a.pdf", file_content, "application/pdf")}

        response_a = await client.post("/api/v1/invoices/upload", files=files, headers=headers_a)
        assert response_a.status_code == 201
        inv_data = response_a.json()
        invoice_id_a = inv_data["invoice_id"]

        # 2. User A can see the invoice in /api/v1/invoices
        list_a = await client.get("/api/v1/invoices", headers=headers_a)
        assert list_a.status_code == 200
        ids_a = [item["id"] for item in list_a.json()]
        assert invoice_id_a in ids_a

        # 3. User B CANNOT see User A's invoice in /api/v1/invoices
        list_b = await client.get("/api/v1/invoices", headers=headers_b)
        assert list_b.status_code == 200
        ids_b = [item["id"] for item in list_b.json()]
        assert invoice_id_a not in ids_b

        # 4. User B CANNOT view User A's invoice directly via ID
        get_b = await client.get(f"/api/v1/invoices/{invoice_id_a}", headers=headers_b)
        assert get_b.status_code == 404

        # 5. User B CANNOT download User A's invoice file
        file_b = await client.get(f"/api/v1/invoices/{invoice_id_a}/file", headers=headers_b)
        assert file_b.status_code == 404

        # 6. User B CANNOT process User A's invoice
        proc_b = await client.post(f"/api/v1/inbox/staged/{invoice_id_a}/process", headers=headers_b)
        assert proc_b.status_code == 404

        # 7. User B CANNOT delete User A's invoice
        del_b = await client.delete(f"/api/v1/inbox/staged/{invoice_id_a}", headers=headers_b)
        assert del_b.status_code == 404

        # 8. User B sees "disconnected" status for IMAP integration initially
        imap_b = await client.get("/api/v1/settings/integrations/imap_email", headers=headers_b)
        assert imap_b.status_code == 200
        assert imap_b.json()["status"] == "disconnected"

        # 9. User A configures IMAP integration
        with patch("app.services.imap_service.imap_service.validate_connection", return_value=None):
            payload_a = {
                "imap_server": "imap.gmail.com",
                "imap_port": 993,
                "email_address": "usera@gmail.com",
                "password": "app_password_a"
            }
            cfg_a = await client.post("/api/v1/settings/integrations/imap_email/configure", json=payload_a, headers=headers_a)
            assert cfg_a.status_code == 200
            assert cfg_a.json()["config"]["email_address"] == "usera@gmail.com"

            # User A sees connected
            imap_a = await client.get("/api/v1/settings/integrations/imap_email", headers=headers_a)
            assert imap_a.status_code == 200
            assert imap_a.json()["status"] == "connected"
            assert imap_a.json()["config"]["email_address"] == "usera@gmail.com"

            # User B STILL sees disconnected
            imap_b2 = await client.get("/api/v1/settings/integrations/imap_email", headers=headers_b)
            assert imap_b2.status_code == 200
            assert imap_b2.json()["status"] == "disconnected"

            # User B configures their own email
            payload_b = {
                "imap_server": "imap.gmail.com",
                "imap_port": 993,
                "email_address": "userb@gmail.com",
                "password": "app_password_b"
            }
            cfg_b = await client.post("/api/v1/settings/integrations/imap_email/configure", json=payload_b, headers=headers_b)
            assert cfg_b.status_code == 200
            assert cfg_b.json()["config"]["email_address"] == "userb@gmail.com"

            # User B sees only their email
            imap_b3 = await client.get("/api/v1/settings/integrations/imap_email", headers=headers_b)
            assert imap_b3.status_code == 200
            assert imap_b3.json()["config"]["email_address"] == "userb@gmail.com"

            # User A STILL sees only their email
            imap_a2 = await client.get("/api/v1/settings/integrations/imap_email", headers=headers_a)
            assert imap_a2.status_code == 200
            assert imap_a2.json()["config"]["email_address"] == "usera@gmail.com"

        # 10. Zoho status is per-user (User B initially sees disconnected)
        zoho_b = await client.get("/api/v1/zoho/status", headers=headers_b)
        assert zoho_b.status_code == 200
        assert zoho_b.json()["connected"] is False
        assert zoho_b.json()["status"] == "DISCONNECTED"
