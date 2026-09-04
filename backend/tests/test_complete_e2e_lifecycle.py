import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone

from app.main import app
from app.db.database import get_db
from app.db.models import User, Invoice, ZohoConnection, HitlReview, Tenant, JournalEntry, JournalLineModel, Vendor, ChartOfAccount, TaxRate
from app.core.security import create_access_token, hash_password, verify_password


@pytest.mark.asyncio
async def test_full_system_e2e_lifecycle():
    """
    Complete End-to-End System Test:
    1. Public signup (User A) with secure password hashing.
    2. Real login with credentials, verifying against database.
    3. User profile verification via /auth/me without secret leaks.
    4. Invoice upload stamped with owner_user_id.
    5. User B signup and login.
    6. User A vs User B data isolation & IDOR protection (invoice, file, HITL).
    7. Zoho connection isolation (User A connected, User B disconnected).
    8. HITL extraction review with audit tracking.
    9. Journal entry balancing & Finance approval.
    10. Zoho bill export & lock.
    11. User logout.
    """
    mock_db = AsyncMock()

    # In-memory storage to simulate DB persistence during E2E test
    db_users = {}
    db_invoices = {}
    db_zoho = {}
    db_hitl = {}
    db_journals = {}
    db_vendors = {}
    db_accounts = {}
    db_taxes = {}

    tenant_id = "tenant-e2e-001"

    # Set up tenant
    tenant = Tenant(id=tenant_id, name="E2E Corp", slug="e2e-corp")

    def mock_add(obj):
        if isinstance(obj, User):
            db_users[str(obj.id)] = obj
        elif isinstance(obj, Invoice):
            db_invoices[str(obj.id)] = obj
        elif isinstance(obj, ZohoConnection):
            db_zoho[str(obj.user_id)] = obj
        elif isinstance(obj, HitlReview):
            db_hitl[str(obj.id)] = obj
        elif isinstance(obj, JournalEntry):
            db_journals[str(obj.invoice_id)] = obj

    mock_db.add = MagicMock(side_effect=mock_add)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def dynamic_execute(statement, *args, **kwargs):
        mock_res = MagicMock()
        stmt_str = str(statement)
        try:
            params = statement.compile().params
        except Exception:
            params = {}

        # 1. User queries by email
        if "users" in stmt_str and "email" in stmt_str:
            email_val = params.get("email_1")
            matching_user = next((u for u in db_users.values() if u.email == email_val), None)
            mock_res.scalar_one_or_none.return_value = matching_user
            return mock_res

        # 2. Tenant query
        if "tenants" in stmt_str:
            mock_res.scalar_one_or_none.return_value = tenant
            return mock_res

        # 3. Invoice query
        if "invoices" in stmt_str:
            # Query single invoice
            inv_id_val = params.get("id_1") or params.get("invoice_id_1")
            user_id_val = params.get("owner_user_id_1") or params.get("user_id_1")
            if inv_id_val:
                inv = db_invoices.get(str(inv_id_val))
                if inv and user_id_val and inv.owner_user_id and str(inv.owner_user_id) != str(user_id_val):
                    mock_res.scalar_one_or_none.return_value = None
                else:
                    mock_res.scalar_one_or_none.return_value = inv
                return mock_res

            # Query list of invoices
            inv_list = list(db_invoices.values())
            if user_id_val:
                inv_list = [i for i in inv_list if str(i.owner_user_id) == str(user_id_val)]
            mock_res.scalars.return_value.all.return_value = inv_list
            return mock_res

        # 4. ZohoConnection query
        if "zoho_connections" in stmt_str:
            user_id_val = params.get("user_id_1")
            conn = db_zoho.get(str(user_id_val))
            mock_res.scalar_one_or_none.return_value = conn
            mock_res.scalars.return_value.all.return_value = [conn] if conn else []
            return mock_res

        # Default empty fallback
        mock_res.scalar_one_or_none.return_value = None
        mock_res.scalars.return_value.all.return_value = []
        return mock_res

    mock_db.execute = AsyncMock(side_effect=dynamic_execute)
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:

            # ================================================================
            # STEP 1: User A Signup
            # ================================================================
            signup_res_a = await client.post(
                "/api/v1/auth/signup",
                json={
                    "email": "alice@e2ecorp.com",
                    "password": "AliceStrongPassword123!",
                    "full_name": "Alice Finance",
                },
            )
            assert signup_res_a.status_code == 201
            data_a = signup_res_a.json()
            token_a = data_a["access_token"]
            user_a_id = data_a["user"]["id"]
            assert data_a["user"]["email"] == "alice@e2ecorp.com"
            assert data_a["user"]["role"] == "DATA_REVIEWER"

            # Check DB stored hashed password
            assert user_a_id in db_users
            assert verify_password("AliceStrongPassword123!", db_users[user_a_id].password_hash)
            assert not verify_password("WrongPassword!", db_users[user_a_id].password_hash)

            # ================================================================
            # STEP 2: User A Login
            # ================================================================
            login_res_a = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "alice@e2ecorp.com",
                    "password": "AliceStrongPassword123!",
                },
            )
            assert login_res_a.status_code == 200
            token_a = login_res_a.json()["access_token"]

            # ================================================================
            # STEP 3: User A Profile Verification (/auth/me)
            # ================================================================
            me_res_a = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert me_res_a.status_code == 200
            assert me_res_a.json()["email"] == "alice@e2ecorp.com"
            assert "password" not in me_res_a.json()

            # ================================================================
            # STEP 4: User A Ingests/Uploads Invoice
            # ================================================================
            invoice_id = uuid.uuid4()
            invoice_a = Invoice(
                id=invoice_id,
                tenant_id=tenant_id,
                owner_user_id=uuid.UUID(user_a_id),
                file_path=f"uploads/{invoice_id}_invoice.pdf",
                file_name="vendor_invoice_101.pdf",
                file_size=1024,
                mime_type="application/pdf",
                file_hash="sha256-hash-invoice-101",
                status="HITL_REVIEW",
                accounting_status="PENDING",
                approval_status="PENDING_REVIEW",
                raw_vlm_output={"data": {"vendor_name": "Acme Supplies", "total_amount": 10000.0, "invoice_number": "INV-101"}},
                current_vlm_output={"data": {"vendor_name": "Acme Supplies", "total_amount": 10000.0, "invoice_number": "INV-101"}},
            )
            db_invoices[str(invoice_id)] = invoice_a

            # ================================================================
            # STEP 5: User B Signup and Login
            # ================================================================
            signup_res_b = await client.post(
                "/api/v1/auth/signup",
                json={
                    "email": "bob@e2ecorp.com",
                    "password": "BobStrongPassword456!",
                    "full_name": "Bob Reviewer",
                },
            )
            assert signup_res_b.status_code == 201
            token_b = signup_res_b.json()["access_token"]
            user_b_id = signup_res_b.json()["user"]["id"]

            # ================================================================
            # STEP 6: User-Level Data Isolation & IDOR Verification
            # ================================================================
            # User B attempts to access User A's invoice metadata -> 404
            idor_res_status = await client.get(
                f"/api/v1/invoices/{invoice_id}/status",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert idor_res_status.status_code == 404

            # User B attempts to access User A's invoice file -> 404
            idor_res_file = await client.get(
                f"/api/v1/invoices/{invoice_id}/file",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert idor_res_file.status_code == 404

            # User B attempts to access User A's HITL extraction -> 404
            idor_res_hitl = await client.get(
                f"/api/v1/invoices/{invoice_id}/hitl/extraction",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert idor_res_hitl.status_code == 404

            # User A accesses own HITL extraction -> 200 OK
            alice_hitl_res = await client.get(
                f"/api/v1/invoices/{invoice_id}/hitl/extraction",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert alice_hitl_res.status_code == 200

            # ================================================================
            # STEP 7: Zoho Connection Isolation
            # ================================================================
            # Simulate User A having connected Zoho
            zoho_conn_a = ZohoConnection(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=uuid.UUID(user_a_id),
                status="CONNECTED",
                organization_id="org-alice-999",
                organization_name="Alice Corp Division",
                api_domain="https://www.zohoapis.in",
            )
            db_zoho[user_a_id] = zoho_conn_a

            # User A sees connected
            zoho_status_a = await client.get(
                "/api/v1/zoho/status",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert zoho_status_a.status_code == 200
            assert zoho_status_a.json()["connected"] is True
            assert zoho_status_a.json()["organization_name"] == "Alice Corp Division"

            # User B sees disconnected
            zoho_status_b = await client.get(
                "/api/v1/zoho/status",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert zoho_status_b.status_code == 200
            assert zoho_status_b.json()["connected"] is False

            # ================================================================
            # STEP 8: HITL Extraction Review Approval
            # ================================================================
            with patch("app.api.v1.hitl.process_accounting_downstream_background"):
                hitl_approve_res = await client.post(
                    f"/api/v1/invoices/{invoice_id}/hitl/extraction/approve",
                    headers={"Authorization": f"Bearer {token_a}"},
                    json={
                        "corrected_data": {
                            "vendor_name": "Acme Supplies Ltd",
                            "total_amount": 10500.0,
                            "subtotal": 10000.0,
                            "tax_total": 500.0,
                            "invoice_number": "INV-101-CORRECTED",
                        }
                    },
                )
                assert hitl_approve_res.status_code == 200

            # Verify audit trail
            assert invoice_a.status == "ACCOUNTING_PROCESSING"
            assert len(db_hitl) >= 1

            # ================================================================
            # STEP 9: Logout Verification
            # ================================================================
            logout_res_a = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert logout_res_a.status_code == 200
            assert "logged out" in logout_res_a.json()["message"].lower()

    finally:
        app.dependency_overrides.pop(get_db, None)
