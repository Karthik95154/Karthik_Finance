import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import get_db
from app.db.models import User, Invoice, Integration, ZohoConnection, HitlReview
from app.core.security import create_access_token, hash_password, verify_password
from app.api.v1.zoho import generate_signed_zoho_state, verify_signed_zoho_state


# ---------------------------------------------------------------------------
# 1. Signup & Password Security Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signup_success_and_password_hashing():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/auth/signup",
                json={
                    "email": "newuser@sakshi.ai",
                    "password": "SecurePassword123!",
                    "full_name": "New User",
                },
            )
            assert res.status_code == 201
            data = res.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert data["user"]["email"] == "newuser@sakshi.ai"
            assert data["user"]["role"] in ("DATA_REVIEWER", "VIEWER", "CUSTOMER")

            # Check that user was added and password was securely hashed
            added_users = [call[0][0] for call in mock_db.add.call_args_list if isinstance(call[0][0], User)]
            assert len(added_users) >= 1
            added_user = added_users[0]
            assert added_user.password_hash != "SecurePassword123!"
            assert verify_password("SecurePassword123!", added_user.password_hash)
            assert not verify_password("WrongPassword!", added_user.password_hash)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_signup_duplicate_email_rejected():
    mock_db = AsyncMock()
    existing_user = User(
        id=uuid.uuid4(),
        email="existing@sakshi.ai",
        password_hash=hash_password("password123"),
        tenant_id="tenant-001",
        role="DATA_REVIEWER",
        is_active=True,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_user
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/auth/signup",
                json={
                    "email": "existing@sakshi.ai",
                    "password": "SecurePassword123!",
                    "full_name": "Existing User",
                },
            )
            assert res.status_code == 400
            assert "already exists" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 2. Login & Credential Verification Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_success():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    stored_hash = hash_password("MySecretPass!@#")
    db_user = User(
        id=user_id,
        email="loginuser@sakshi.ai",
        password_hash=stored_hash,
        tenant_id="tenant-login",
        role="FINANCE",
        full_name="Finance Login User",
        is_active=True,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_user
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/auth/login",
                json={
                    "email": "loginuser@sakshi.ai",
                    "password": "MySecretPass!@#",
                },
            )
            assert res.status_code == 200
            data = res.json()
            assert "access_token" in data
            assert data["user"]["id"] == str(user_id)
            assert data["user"]["email"] == "loginuser@sakshi.ai"
            assert data["user"]["role"] == "FINANCE"
            assert data["user"]["tenant_id"] == "tenant-login"
            assert "password" not in data["user"]
            assert "password_hash" not in data["user"]
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_wrong_password_fails():
    mock_db = AsyncMock()
    db_user = User(
        id=uuid.uuid4(),
        email="loginuser@sakshi.ai",
        password_hash=hash_password("CorrectPass123"),
        tenant_id="tenant-login",
        role="FINANCE",
        is_active=True,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_user
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/auth/login",
                json={
                    "email": "loginuser@sakshi.ai",
                    "password": "WrongPassword456",
                },
            )
            assert res.status_code == 401
            assert "invalid email or password" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_inactive_user_fails():
    mock_db = AsyncMock()
    db_user = User(
        id=uuid.uuid4(),
        email="inactive@sakshi.ai",
        password_hash=hash_password("CorrectPass123"),
        tenant_id="tenant-login",
        role="FINANCE",
        is_active=False,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_user
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/auth/login",
                json={
                    "email": "inactive@sakshi.ai",
                    "password": "CorrectPass123",
                },
            )
            assert res.status_code in (401, 403)
            assert "deactivated" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 3. Authenticated User Profile & Logout Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auth_me_returns_profile_without_secrets():
    user_id = str(uuid.uuid4())
    token = create_access_token(
        user_id=user_id,
        email="authme@sakshi.ai",
        tenant_id="tenant-authme",
        role="FINANCE_MANAGER",
        full_name="Finance Manager Me",
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == user_id
        assert data["email"] == "authme@sakshi.ai"
        assert data["role"] == "FINANCE_MANAGER"
        assert data["tenant_id"] == "tenant-authme"
        assert "password" not in data
        assert "password_hash" not in data


@pytest.mark.asyncio
async def test_auth_logout():
    user_id = str(uuid.uuid4())
    token = create_access_token(
        user_id=user_id,
        email="logout@sakshi.ai",
        tenant_id="tenant-logout",
        role="DATA_REVIEWER",
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert "logged out" in res.json()["message"].lower()


@pytest.mark.asyncio
async def test_unauthenticated_protected_endpoint_fails(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "ENABLE_DEV_AUTH", False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/me")
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# 4. User-Level Invoice & HITL Data Isolation Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invoice_user_isolation_same_tenant():
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    tenant_id = "shared-tenant-100"

    token_a = create_access_token(
        user_id=str(user_a_id),
        email="user_a@shared.com",
        tenant_id=tenant_id,
        role="DATA_REVIEWER",
    )
    token_b = create_access_token(
        user_id=str(user_b_id),
        email="user_b@shared.com",
        tenant_id=tenant_id,
        role="DATA_REVIEWER",
    )

    inv_a = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        owner_user_id=user_a_id,
        file_name="invoice_user_a.pdf",
        status="UPLOADED",
        approval_status="PENDING",
        accounting_status="PENDING",
    )

    mock_db = AsyncMock()

    async def mock_execute(statement, *args, **kwargs):
        mock_res = MagicMock()
        stmt_str = str(statement)
        if "owner_user_id" in stmt_str and str(user_b_id) in stmt_str:
            mock_res.scalar_one_or_none.return_value = None
            mock_res.scalars.return_value.all.return_value = []
        elif "owner_user_id" in stmt_str and str(user_a_id) in stmt_str:
            mock_res.scalar_one_or_none.return_value = inv_a
            mock_res.scalars.return_value.all.return_value = [inv_a]
        else:
            mock_res.scalar_one_or_none.return_value = None
            mock_res.scalars.return_value.all.return_value = []
        return mock_res

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # User B accessing User A's invoice status -> 404
            res_b = await ac.get(
                f"/api/v1/invoices/{inv_a.id}/status",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert res_b.status_code == 404

            # User B accessing User A's invoice file -> 404
            res_b_file = await ac.get(
                f"/api/v1/invoices/{inv_a.id}/file",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert res_b_file.status_code == 404

            # User B accessing User A's HITL extraction -> 404
            res_b_hitl = await ac.get(
                f"/api/v1/invoices/{inv_a.id}/hitl/extraction",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert res_b_hitl.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 5. Zoho Connection Isolation Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zoho_connection_user_isolation():
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    tenant_id = "shared-tenant-200"

    token_a = create_access_token(
        user_id=str(user_a_id),
        email="zoho_a@shared.com",
        tenant_id=tenant_id,
        role="ADMIN",
    )
    token_b = create_access_token(
        user_id=str(user_b_id),
        email="zoho_b@shared.com",
        tenant_id=tenant_id,
        role="ADMIN",
    )

    zoho_conn_a = ZohoConnection(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_a_id,
        status="CONNECTED",
        organization_id="org-12345",
        organization_name="User A Organization",
        api_domain="https://www.zohoapis.in",
        token_expires_at=None,
        error_message=None,
    )

    mock_db = AsyncMock()

    async def mock_execute(statement, *args, **kwargs):
        mock_res = MagicMock()
        try:
            params = statement.compile().params
        except Exception:
            params = {}
        param_values = list(params.values())

        if user_a_id in param_values or str(user_a_id) in param_values:
            mock_res.scalar_one_or_none.return_value = zoho_conn_a
            mock_res.scalars.return_value.all.return_value = [zoho_conn_a]
        else:
            mock_res.scalar_one_or_none.return_value = None
            mock_res.scalars.return_value.all.return_value = []
        return mock_res

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # User A sees connected=True
            res_a = await ac.get(
                "/api/v1/zoho/status",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert res_a.status_code == 200
            assert res_a.json()["connected"] is True
            assert res_a.json()["organization_name"] == "User A Organization"

            # User B sees connected=False (never falls back to User A's connection)
            res_b = await ac.get(
                "/api/v1/zoho/status",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert res_b.status_code == 200
            assert res_b.json()["connected"] is False
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_zoho_oauth_state_user_binding():
    user_a_id = str(uuid.uuid4())
    user_b_id = str(uuid.uuid4())
    tenant_id = "tenant-zoho-state"
    frontend_url = "http://localhost:3000"

    state_for_user_a = generate_signed_zoho_state(tenant_id=tenant_id, user_id=user_a_id, frontend_url=frontend_url)

    # Verifying signed state extracts correct payload
    payload = verify_signed_zoho_state(state_for_user_a)
    assert payload["tenant_id"] == tenant_id
    assert payload["user_id"] == user_a_id
    assert payload["frontend_url"] == frontend_url

    # Verifying manipulated state fails
    tampered_state = state_for_user_a[:-4] + "abcd"
    with pytest.raises(Exception):
        verify_signed_zoho_state(tampered_state)


# ---------------------------------------------------------------------------
# 6. Email / IMAP Integration Isolation Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_email_integration_user_isolation():
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    tenant_id = "shared-tenant-300"

    token_a = create_access_token(
        user_id=str(user_a_id),
        email="email_a@shared.com",
        tenant_id=tenant_id,
        role="ADMIN",
    )
    token_b = create_access_token(
        user_id=str(user_b_id),
        email="email_b@shared.com",
        tenant_id=tenant_id,
        role="ADMIN",
    )

    integration_a = Integration(
        id="imap_email",
        tenant_id=tenant_id,
        user_id=user_a_id,
        status="connected",
        config={"imap_server": "imap.usera.com", "email_address": "invoices@usera.com"},
    )

    mock_db = AsyncMock()

    async def mock_execute(statement, *args, **kwargs):
        mock_res = MagicMock()
        try:
            params = statement.compile().params
        except Exception:
            params = {}
        param_values = list(params.values())

        if user_a_id in param_values or str(user_a_id) in param_values:
            mock_res.scalar_one_or_none.return_value = integration_a
        else:
            mock_res.scalar_one_or_none.return_value = None
        return mock_res

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # User A sees status=connected and email_address in config
            res_a = await ac.get(
                "/api/v1/settings/integrations/imap_email",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert res_a.status_code == 200
            assert res_a.json()["status"] == "connected"
            assert res_a.json()["config"]["email_address"] == "invoices@usera.com"

            # User B sees status=disconnected
            res_b = await ac.get(
                "/api/v1/settings/integrations/imap_email",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert res_b.status_code == 200
            assert res_b.json()["status"] == "disconnected"
    finally:
        app.dependency_overrides.pop(get_db, None)
