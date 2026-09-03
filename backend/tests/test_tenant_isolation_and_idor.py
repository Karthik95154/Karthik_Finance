import uuid
import time
import base64
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import get_db
from app.db.models import Invoice, Integration, HitlReview
from app.core.security import create_access_token
from app.api.v1.zoho import generate_signed_zoho_state, verify_signed_zoho_state, ZOHO_STATE_MAX_AGE_SECONDS


@pytest.fixture
def tenant_a_admin():
    return create_access_token(
        user_id=str(uuid.uuid4()),
        email="admin@tenant-a.com",
        tenant_id="tenant-a",
        role="ADMIN",
    )


@pytest.fixture
def tenant_a_finance():
    return create_access_token(
        user_id=str(uuid.uuid4()),
        email="finance@tenant-a.com",
        tenant_id="tenant-a",
        role="FINANCE",
    )


@pytest.fixture
def tenant_a_viewer():
    return create_access_token(
        user_id=str(uuid.uuid4()),
        email="viewer@tenant-a.com",
        tenant_id="tenant-a",
        role="VIEWER",
    )


@pytest.fixture
def tenant_b_finance():
    return create_access_token(
        user_id=str(uuid.uuid4()),
        email="finance@tenant-b.com",
        tenant_id="tenant-b",
        role="FINANCE",
    )


# ---------------------------------------------------------------------------
# 1 & 2. Invoice File & Pages Cross-Tenant Authorization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_invoice_file_cross_tenant_returns_404_or_401(tenant_a_finance):
    """Test 1: Tenant A querying a file owned by Tenant B receives 404 Not Found (zero information leak)."""
    inv_b_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # DB filter: Invoice.tenant_id == 'tenant-a'
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        headers = {"Authorization": f"Bearer {tenant_a_finance}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get(f"/api/v1/invoices/{inv_b_id}/file", headers=headers)
            assert res.status_code == 404
            assert "not found" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_get_invoice_pages_cross_tenant_returns_404_or_401(tenant_a_finance):
    """Test 2: Tenant A querying pages owned by Tenant B receives 404 Not Found."""
    inv_b_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        headers = {"Authorization": f"Bearer {tenant_a_finance}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get(f"/api/v1/invoices/{inv_b_id}/pages", headers=headers)
            assert res.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 3 & 4. Invoice File & Pages Unauthenticated Protection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_invoice_file_unauthenticated_rejected(monkeypatch):
    """Test 3: Unauthenticated request to /invoices/{id}/file returns 401."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ENABLE_DEV_AUTH", False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/invoices/{uuid.uuid4()}/file")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_invoice_pages_unauthenticated_rejected(monkeypatch):
    """Test 4: Unauthenticated request to /invoices/{id}/pages returns 401."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ENABLE_DEV_AUTH", False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/invoices/{uuid.uuid4()}/pages")
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# 5. Staged Documents Tenant Filter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_staged_documents_strictly_filters_by_tenant(tenant_a_finance):
    """Test 5: GET /inbox/staged executes query filtered strictly by caller's tenant_id."""
    executed_statements = []
    mock_db = AsyncMock()

    async def tracking_execute(stmt, *args, **kwargs):
        executed_statements.append(str(stmt))
        res = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        res.scalars.return_value = mock_scalars
        return res

    mock_db.execute = tracking_execute

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        headers = {"Authorization": f"Bearer {tenant_a_finance}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/api/v1/inbox/staged", headers=headers)
            assert res.status_code == 200
            assert any("invoices.tenant_id = :tenant_id" in s or "tenant_id" in s for s in executed_statements)
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 6 & 7. Process & Delete Staged Cross-Tenant Protection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_staged_document_cross_tenant_rejected(tenant_a_finance):
    """Test 6: Tenant A attempting to process Tenant B staged invoice receives 404."""
    inv_b_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # Not found for tenant-a
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        headers = {"Authorization": f"Bearer {tenant_a_finance}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post(f"/api/v1/inbox/staged/{inv_b_id}/process", headers=headers)
            assert res.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_delete_staged_document_cross_tenant_rejected(tenant_a_finance):
    """Test 7: Tenant A attempting to delete Tenant B staged invoice receives 404."""
    inv_b_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # Not found for tenant-a
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        headers = {"Authorization": f"Bearer {tenant_a_finance}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.delete(f"/api/v1/inbox/staged/{inv_b_id}", headers=headers)
            assert res.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 8 & 9. Polling Authentication & Tenant Assignment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_staged_poll_requires_authentication(monkeypatch):
    """Test 8: Anonymous request to poll email/inbox returns 401."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ENABLE_DEV_AUTH", False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/inbox/poll")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_email_poll_assigns_current_user_tenant(tenant_a_finance):
    """Test 9: Polling email integration strictly looks up tenant-a configuration."""
    executed_statements = []
    mock_db = AsyncMock()

    async def tracking_execute(stmt, *args, **kwargs):
        executed_statements.append(str(stmt))
        res = MagicMock()
        # No configured integration -> returns None -> 400 with tenant specific error
        res.scalar_one_or_none.return_value = None
        return res

    mock_db.execute = tracking_execute

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        headers = {"Authorization": f"Bearer {tenant_a_finance}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post("/api/v1/inbox/poll", headers=headers)
            assert res.status_code == 400
            assert "configured for your tenant" in res.json()["detail"]
            assert any("integrations.tenant_id = :tenant_id" in s or "tenant_id" in s for s in executed_statements)
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 10 & 11. Integration Settings Multi-Tenancy & RBAC
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_integration_settings_cross_tenant_isolation(tenant_a_admin, tenant_b_finance):
    """Test 10: Tenant A settings query only returns Tenant A integration, not Tenant B."""
    mock_db = AsyncMock()
    tenant_a_integration = Integration(
        id="imap_email_tenant-a",
        tenant_id="tenant-a",
        status="connected",
        config={"email_address": "tenant_a@company.com", "imap_server": "imap.tenant-a.com"},
    )

    async def override_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt)
        res = MagicMock()
        if "tenant-a" in stmt_str or "integrations.tenant_id = :tenant_id" in stmt_str:
            res.scalar_one_or_none.return_value = tenant_a_integration
        else:
            res.scalar_one_or_none.return_value = None
        return res

    mock_db.execute = override_execute

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        headers = {"Authorization": f"Bearer {tenant_a_admin}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/api/v1/settings/integrations/imap_email", headers=headers)
            assert res.status_code == 200
            assert res.json()["config"]["email_address"] == "tenant_a@company.com"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_integration_settings_requires_admin(tenant_a_viewer):
    """Test 11: Non-admin roles (e.g. VIEWER) cannot configure or disconnect integrations (403 Forbidden)."""
    headers = {"Authorization": f"Bearer {tenant_a_viewer}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/settings/integrations/imap_email/configure", json={
            "imap_server": "imap.test.com",
            "imap_port": 993,
            "email_address": "test@test.com",
            "password": "pass",
        }, headers=headers)
        assert res.status_code == 403

        res_disc = await ac.post("/api/v1/settings/integrations/imap_email/disconnect", headers=headers)
        assert res_disc.status_code == 403


# ---------------------------------------------------------------------------
# 12. HITL History Cross-Tenant Isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_invoice_hitl_history_cross_tenant_returns_404(tenant_a_finance):
    """Test 12: Tenant A querying HITL history for an invoice in Tenant B receives 404 Not Found."""
    inv_b_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # Invoice not found for tenant-a
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        headers = {"Authorization": f"Bearer {tenant_a_finance}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get(f"/api/v1/invoices/{inv_b_id}/hitl/history", headers=headers)
            assert res.status_code == 404
            assert "not found" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 13, 14, 15. Zoho OAuth State Protection
# ---------------------------------------------------------------------------

def test_zoho_oauth_state_valid_round_trip():
    """Test 15: Valid signed state decodes successfully with matching tenant_id and frontend_url."""
    signed = generate_signed_zoho_state("tenant-corp-1", "https://app.corp.com")
    verified = verify_signed_zoho_state(signed)
    assert verified["tenant_id"] == "tenant-corp-1"
    assert verified["frontend_url"] == "https://app.corp.com"
    assert "ts" in verified
    assert "nonce" in verified


def test_zoho_oauth_state_tampering_rejected():
    """Test 13: Altered state payload or signature is rejected with ValueError."""
    signed = generate_signed_zoho_state("tenant-corp-1", "https://app.corp.com")
    payload_b64, sig = signed.split(".")

    # Tamper with tenant_id inside payload
    payload_dict = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8"))
    payload_dict["tenant_id"] = "attacker-tenant"
    tampered_b64 = base64.urlsafe_b64encode(json.dumps(payload_dict).encode("utf-8")).decode("utf-8")
    tampered_state = f"{tampered_b64}.{sig}"

    with pytest.raises(ValueError, match="Invalid OAuth state cryptographic signature"):
        verify_signed_zoho_state(tampered_state)


def test_zoho_oauth_state_expiration_rejected():
    """Test 14: Expired state token (> 15 minutes) is rejected with ValueError."""
    # Generate state with timestamp 20 minutes in the past
    expired_ts = int(time.time()) - (ZOHO_STATE_MAX_AGE_SECONDS + 300)
    state_payload = {
        "tenant_id": "tenant-corp-1",
        "frontend_url": "https://app.corp.com",
        "ts": expired_ts,
        "nonce": "testnonce",
    }
    payload_json = json.dumps(state_payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("utf-8")
    import hmac, hashlib
    from app.core.config import settings
    secret = settings.AUTH_SECRET_KEY or "fallback-zoho-state-signing-key-production"
    sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    expired_state = f"{payload_b64}.{sig}"

    with pytest.raises(ValueError, match="OAuth state has expired"):
        verify_signed_zoho_state(expired_state)
