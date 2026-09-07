import uuid
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

from app.main import app
from app.db.database import get_db, Base
from app.db.models import User, Tenant, EmailConnection
from app.core.security import create_access_token
from app.services.imap_service import imap_service


# Teach SQLite to compile PostgreSQL JSONB as JSON in tests
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


# Setup an in-memory SQLite database specifically for testing foreign keys and persistence
TEST_SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_db_session():
    engine = create_async_engine(TEST_SQLITE_URL, echo=False)
    target_tables = [Tenant.__table__, User.__table__, EmailConnection.__table__]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=target_tables))

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn, tables=target_tables))
    await engine.dispose()


@pytest.mark.asyncio
async def test_email_connection_when_user_already_exists(test_db_session):
    """Test 1: User already exists in DB -> email connection links directly to existing user row."""
    user_id = uuid.uuid4()
    tenant_id = "default-tenant-001"

    # Pre-seed tenant and user
    tenant = Tenant(id=tenant_id, name="Test Org", slug="test-org")
    test_db_session.add(tenant)
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="existing_user@company.com",
        full_name="Existing User",
        role="FINANCE",
        is_active=True,
    )
    test_db_session.add(user)
    await test_db_session.commit()

    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        auth_token = create_access_token(
            user_id=str(user_id),
            email="existing_user@company.com",
            tenant_id=tenant_id,
            role="FINANCE",
        )
        headers = {"Authorization": f"Bearer {auth_token}"}

        payload = {
            "imap_server": "imap.gmail.com",
            "imap_port": 993,
            "email_address": "existing_user@company.com",
            "password": "valid_app_password_123",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(imap_service, "validate_connection", return_value=None):
                res = await client.post(
                    "/api/v1/settings/integrations/imap_email/configure",
                    json=payload,
                    headers=headers,
                )
                assert res.status_code == 200
                data = res.json()
                assert data["success"] is True
                assert data["status"] == "connected"

                # Verify email connection record is linked to existing user
                q = select(EmailConnection).where(EmailConnection.user_id == user_id)
                res_db = await test_db_session.execute(q)
                conn_rec = res_db.scalar_one_or_none()
                assert conn_rec is not None
                assert conn_rec.user_id == user_id
                assert conn_rec.is_active is True
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_email_connection_syncs_missing_user(test_db_session):
    """Test 2: Authenticated user exists in auth system (token) but users row is missing in DB.
    System must provision the user in users table before inserting email_connections/integrations.
    """
    failing_user_id = uuid.UUID("d3e29d7a-6be0-4c9a-ac26-77fd06790032")
    user_email = "render_user@production.com"
    tenant_id = "default-tenant-001"

    # Confirm user does NOT exist in DB initially
    user_check = await test_db_session.get(User, failing_user_id)
    assert user_check is None

    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        auth_token = create_access_token(
            user_id=str(failing_user_id),
            email=user_email,
            tenant_id=tenant_id,
            role="FINANCE",
            full_name="Render Prod User",
        )
        headers = {"Authorization": f"Bearer {auth_token}"}

        payload = {
            "imap_server": "imap.gmail.com",
            "imap_port": 993,
            "email_address": user_email,
            "password": "valid_app_password_123",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(imap_service, "validate_connection", return_value=None):
                res = await client.post(
                    "/api/v1/settings/integrations/imap_email/configure",
                    json=payload,
                    headers=headers,
                )
                assert res.status_code == 200
                data = res.json()
                assert data["success"] is True
                assert data["status"] == "connected"

                # Verify user was automatically synced/provisioned
                synced_user = await test_db_session.get(User, failing_user_id)
                assert synced_user is not None
                assert synced_user.email == user_email
                assert synced_user.tenant_id == tenant_id
                assert synced_user.role == "FINANCE"

                # Verify email_connections record was created and links to the synced user
                q = select(EmailConnection).where(EmailConnection.user_id == failing_user_id)
                res_db = await test_db_session.execute(q)
                conn_rec = res_db.scalar_one_or_none()
                assert conn_rec is not None
                assert conn_rec.user_id == failing_user_id
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_email_connection_reconnect_and_update(test_db_session):
    """Test 3: Existing email connection update/reconnect works properly without FK or duplicate errors."""
    user_id = uuid.uuid4()
    tenant_id = "default-tenant-001"

    tenant = Tenant(id=tenant_id, name="Test Org", slug="test-org-reconnect")
    test_db_session.add(tenant)
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="reconnect_user@company.com",
        role="FINANCE",
    )
    test_db_session.add(user)
    await test_db_session.commit()

    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        auth_token = create_access_token(
            user_id=str(user_id),
            email="reconnect_user@company.com",
            tenant_id=tenant_id,
            role="FINANCE",
        )
        headers = {"Authorization": f"Bearer {auth_token}"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(imap_service, "validate_connection", return_value=None):
                # 1. Initial connect
                payload1 = {
                    "imap_server": "imap.gmail.com",
                    "imap_port": 993,
                    "email_address": "reconnect_user@company.com",
                    "password": "first_app_password",
                }
                res1 = await client.post(
                    "/api/v1/settings/integrations/imap_email/configure",
                    json=payload1,
                    headers=headers,
                )
                assert res1.status_code == 200

                # 2. Get settings
                res_get = await client.get("/api/v1/settings/integrations/imap_email", headers=headers)
                assert res_get.status_code == 200
                assert res_get.json()["status"] == "connected"

                # 3. Disconnect
                res_disc = await client.post("/api/v1/settings/integrations/imap_email/disconnect", headers=headers)
                assert res_disc.status_code == 200
                assert res_disc.json()["status"] == "disconnected"

                # 4. Reconnect with new settings
                payload2 = {
                    "imap_server": "imap.outlook.com",
                    "imap_port": 993,
                    "email_address": "reconnect_user@company.com",
                    "password": "second_app_password",
                }
                res2 = await client.post(
                    "/api/v1/settings/integrations/imap_email/configure",
                    json=payload2,
                    headers=headers,
                )
                assert res2.status_code == 200
                assert res2.json()["status"] == "connected"

                # Verify connection updated in DB
                q = select(EmailConnection).where(EmailConnection.user_id == user_id)
                res_db = await test_db_session.execute(q)
                conn_rec = res_db.scalar_one_or_none()
                assert conn_rec is not None
                assert conn_rec.imap_host == "imap.outlook.com"
                assert conn_rec.is_active is True
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_email_connection_unresolvable_user_returns_application_error():
    """Test 4: If an unexpected integrity violation occurs, clean HTTP 400 is returned rather than 500 IntegrityError."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    mock_db.get.return_value = None
    # Let db.commit raise IntegrityError to simulate constraint violation
    mock_db.commit.side_effect = IntegrityError("INSERT INTO integrations", {}, Exception("foreign key violation"))

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        user_id = str(uuid.uuid4())
        auth_token = create_access_token(
            user_id=user_id,
            email="mock_fail@company.com",
            tenant_id="default-tenant-001",
            role="FINANCE",
        )
        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = {
            "imap_server": "imap.gmail.com",
            "imap_port": 993,
            "email_address": "mock_fail@company.com",
            "password": "valid_app_password_123",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(imap_service, "validate_connection", return_value=None):
                res = await client.post(
                    "/api/v1/settings/integrations/imap_email/configure",
                    json=payload,
                    headers=headers,
                )
                assert res.status_code == 400
                assert "Failed to link email connection" in res.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)
