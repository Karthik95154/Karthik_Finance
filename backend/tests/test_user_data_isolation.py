import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_user_data_isolation_e2e_suite():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_id = uuid.uuid4().hex[:6]

        # ── 1. Register & Login User A and User B ────────────────────────────
        res_signup_a = await client.post("/api/v1/auth/signup", json={"email": f"usera_{run_id}@example.com", "password": "SecurePassword123!", "full_name": "User A"})
        assert res_signup_a.status_code == 200
        token_a = res_signup_a.json()["access_token"]

        # Duplicate signup fails with 400
        res_signup_dup = await client.post("/api/v1/auth/signup", json={"email": f"usera_{run_id}@example.com", "password": "SecurePassword123!"})
        assert res_signup_dup.status_code == 400

        # Login User A with correct password succeeds
        res_login_a = await client.post("/api/v1/auth/login", json={"email": f"usera_{run_id}@example.com", "password": "SecurePassword123!"})
        assert res_login_a.status_code == 200

        # Login User A with incorrect password fails with 401
        res_login_bad = await client.post("/api/v1/auth/login", json={"email": f"usera_{run_id}@example.com", "password": "WrongPassword!"})
        assert res_login_bad.status_code == 401

        # Register User B
        res_signup_b = await client.post("/api/v1/auth/signup", json={"email": f"userb_{run_id}@example.com", "password": "SecurePassword456!", "full_name": "User B"})
        assert res_signup_b.status_code == 200
        token_b = res_signup_b.json()["access_token"]

        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # ── 2. Create Invoice A (User A) and Invoice B (User B) ───────────────
        file_a = f"%PDF-1.4 Invoice for User A {run_id}".encode()
        resp_upload_a = await client.post("/api/v1/invoices/upload", files={"file": ("inv_a.pdf", file_a, "application/pdf")}, headers=headers_a)
        assert resp_upload_a.status_code == 201
        inv_id_a = resp_upload_a.json()["invoice_id"]

        file_b = f"%PDF-1.4 Invoice for User B {run_id}".encode()
        resp_upload_b = await client.post("/api/v1/invoices/upload", files={"file": ("inv_b.pdf", file_b, "application/pdf")}, headers=headers_b)
        assert resp_upload_b.status_code == 201
        inv_id_b = resp_upload_b.json()["invoice_id"]

        # ── 3. Invoice Listing Isolation ─────────────────────────────────────
        list_a = await client.get("/api/v1/invoices", headers=headers_a)
        assert list_a.status_code == 200
        ids_a = [i["id"] for i in list_a.json()]
        assert inv_id_a in ids_a
        assert inv_id_b not in ids_a

        list_b = await client.get("/api/v1/invoices", headers=headers_b)
        assert list_b.status_code == 200
        ids_b = [i["id"] for i in list_b.json()]
        assert inv_id_b in ids_b
        assert inv_id_a not in ids_b

        # ── 4. Direct Cross-User Resource Attack Checks (User A -> Invoice B) ─
        # GET Invoice B -> 404
        get_b_by_a = await client.get(f"/api/v1/invoices/{inv_id_b}", headers=headers_a)
        assert get_b_by_a.status_code == 404

        # PUT Invoice B -> 404
        put_b_by_a = await client.put(f"/api/v1/invoices/{inv_id_b}", json={"vendor_name": "Hacked"}, headers=headers_a)
        assert put_b_by_a.status_code == 404

        # DELETE Invoice B via inbox staged -> 404
        del_b_by_a = await client.delete(f"/api/v1/inbox/staged/{inv_id_b}", headers=headers_a)
        assert del_b_by_a.status_code == 404

        # Categorize Invoice B -> 404
        appr_b_by_a = await client.post(f"/api/v1/invoices/{inv_id_b}/categorize", headers=headers_a)
        assert appr_b_by_a.status_code == 404

        # Assign COA Invoice B -> 404
        rej_b_by_a = await client.post(f"/api/v1/invoices/{inv_id_b}/assign_coa", json={"zoho_account_id": "123", "account_name": "Test"}, headers=headers_a)
        assert rej_b_by_a.status_code == 404

        # COA Match Invoice B -> 404
        coa_b_by_a = await client.post(f"/api/v1/invoices/{inv_id_b}/coa-match", json={}, headers=headers_a)
        assert coa_b_by_a.status_code == 404

        # Export Invoice B -> 404
        exp_b_by_a = await client.post(f"/api/v1/invoices/{inv_id_b}/export-zoho", headers=headers_a)
        assert exp_b_by_a.status_code == 404

        # ── 5. Zoho Connection & Organization Isolation ─────────────────────
        # Org selection manipulation attack (invalid/unowned org) -> 403 or 400
        org_select_res = await client.post(
            "/api/v1/zoho/select-org",
            json={"organization_id": "unowned_fake_org_id"},
            headers=headers_a,
        )
        assert org_select_res.status_code in (400, 403)

        # ── 6. Newly Uploaded Invoice Immediate GET & Duplicate Upload Isolation ───────────
        # User A uploads a brand new invoice file
        file_unique_content = f"%PDF-1.4 Unique Invoice content {run_id}".encode()
        resp_upload_new = await client.post(
            "/api/v1/invoices/upload",
            files={"file": ("new_inv.pdf", file_unique_content, "application/pdf")},
            headers=headers_a,
        )
        assert resp_upload_new.status_code == 201
        new_inv_id = resp_upload_new.json()["invoice_id"]

        # Immediate GET by User A must return HTTP 200
        get_immediate_a = await client.get(f"/api/v1/invoices/{new_inv_id}", headers=headers_a)
        assert get_immediate_a.status_code == 200
        assert get_immediate_a.json()["id"] == new_inv_id

        # GET by User B for User A's newly uploaded invoice must return HTTP 404
        get_immediate_b = await client.get(f"/api/v1/invoices/{new_inv_id}", headers=headers_b)
        assert get_immediate_b.status_code == 404

        # User B uploads the EXACT SAME file content (matching file hash)
        resp_upload_dup_b = await client.post(
            "/api/v1/invoices/upload",
            files={"file": ("dup_by_b.pdf", file_unique_content, "application/pdf")},
            headers=headers_b,
        )
        assert resp_upload_dup_b.status_code == 201
        dup_b_inv_id = resp_upload_dup_b.json()["invoice_id"]
        # User B's duplicate upload must NOT return User A's invoice ID
        assert dup_b_inv_id != new_inv_id

        # User B can immediately fetch their own newly created invoice record
        get_dup_b = await client.get(f"/api/v1/invoices/{dup_b_inv_id}", headers=headers_b)
        assert get_dup_b.status_code == 200
        assert get_dup_b.json()["id"] == dup_b_inv_id

        # User A cannot view User B's duplicate invoice record -> HTTP 404
        get_dup_a = await client.get(f"/api/v1/invoices/{dup_b_inv_id}", headers=headers_a)
        assert get_dup_a.status_code == 404

