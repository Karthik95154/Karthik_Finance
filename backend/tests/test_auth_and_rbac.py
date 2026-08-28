import uuid
from datetime import timedelta
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token


@pytest.fixture
def admin_token():
    return create_access_token(
        user_id=str(uuid.uuid4()),
        email="admin@tenant-a.com",
        tenant_id="tenant-a",
        role="ADMIN",
    )


@pytest.fixture
def finance_token():
    return create_access_token(
        user_id=str(uuid.uuid4()),
        email="finance@tenant-a.com",
        tenant_id="tenant-a",
        role="FINANCE",
    )


@pytest.fixture
def viewer_token():
    return create_access_token(
        user_id=str(uuid.uuid4()),
        email="viewer@tenant-a.com",
        tenant_id="tenant-a",
        role="VIEWER",
    )


@pytest.fixture
def tenant_b_finance_token():
    return create_access_token(
        user_id=str(uuid.uuid4()),
        email="finance@tenant-b.com",
        tenant_id="tenant-b",
        role="FINANCE",
    )


@pytest.mark.asyncio
async def test_a_no_jwt_rejected():
    """Test A: Unauthenticated request (no JWT) is rejected with 401 Unauthorized."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invoices list
        res = await client.get("/api/v1/invoices")
        assert res.status_code == 401
        assert "Authentication required" in res.json()["detail"]

        # Review endpoint
        res2 = await client.post(f"/api/v1/invoices/{uuid.uuid4()}/approve")
        assert res2.status_code == 401


@pytest.mark.asyncio
async def test_b_invalid_or_expired_jwt_rejected():
    """Test B: Invalid signature or expired token is rejected with 401 Unauthorized."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Tampered / invalid token
        headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"}
        res = await client.get("/api/v1/invoices", headers=headers)
        assert res.status_code == 401

        # Expired token
        expired_tok = create_access_token(
            user_id=str(uuid.uuid4()),
            email="exp@test.com",
            tenant_id="tenant-a",
            role="FINANCE",
            expires_delta=timedelta(seconds=-60),  # expired 1 min ago
        )
        res_exp = await client.get("/api/v1/invoices", headers={"Authorization": f"Bearer {expired_tok}"})
        assert res_exp.status_code == 401
        assert "expired" in res_exp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_c_viewer_cannot_approve(viewer_token):
    """Test C: VIEWER role cannot approve invoices (returns 403 Forbidden)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {viewer_token}"}
        res = await client.post(f"/api/v1/invoices/{uuid.uuid4()}/approve", headers=headers)
        assert res.status_code == 403
        assert "Role 'VIEWER' is not authorized" in res.json()["detail"]


@pytest.mark.asyncio
async def test_d_viewer_cannot_export(viewer_token):
    """Test D: VIEWER role cannot export invoices to Zoho (returns 403 Forbidden)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {viewer_token}"}
        res = await client.post(f"/api/v1/invoices/{uuid.uuid4()}/export", headers=headers)
        assert res.status_code == 403
        assert "Role 'VIEWER' is not authorized" in res.json()["detail"]


@pytest.mark.asyncio
async def test_i_viewer_cannot_edit_invoice(viewer_token):
    """Test I: VIEWER role cannot edit invoice accounting data (returns 403 Forbidden)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {viewer_token}"}
        res = await client.put(f"/api/v1/invoices/{uuid.uuid4()}", json={"current_vlm_output": {}}, headers=headers)
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_j_viewer_cannot_upload(viewer_token):
    """Test J: VIEWER role cannot upload invoices (returns 403 Forbidden)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {viewer_token}"}
        files = {"file": ("test.pdf", b"%PDF-dummy", "application/pdf")}
        res = await client.post("/api/v1/invoices/upload", files=files, headers=headers)
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_k_viewer_cannot_modify_zoho(viewer_token):
    """Test K: VIEWER role cannot connect or sync Zoho (returns 403 Forbidden)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {viewer_token}"}
        res_sync = await client.post("/api/v1/zoho/sync", headers=headers)
        assert res_sync.status_code == 403

        res_conn = await client.get("/api/v1/zoho/connect", headers=headers)
        assert res_conn.status_code == 403
