import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import get_db
from app.db.models import ZohoConnection
from app.core.security import encrypt_secret, decrypt_secret, create_access_token
from app.services.zoho_client import zoho_client_service
from app.services.master_data_service import master_data_service


def test_token_encryption_and_decryption():
    plain_token = "1000.a1b2c3d4e5f6g7h8i9j0.refresh_secret_token_12345"
    encrypted = encrypt_secret(plain_token)
    assert encrypted != plain_token
    assert len(encrypted) > len(plain_token)

    decrypted = decrypt_secret(encrypted)
    assert decrypted == plain_token


def test_encryption_empty_strings():
    assert encrypt_secret("") == ""
    assert decrypt_secret("") == ""


def test_zoho_auth_url_generation():
    auth_url = zoho_client_service.get_authorization_url(
        tenant_id="test-tenant-123",
        redirect_uri="http://localhost:8000/api/v1/zoho/callback",
    )
    assert "oauth/v2/auth" in auth_url
    assert "state=test-tenant-123" in auth_url
    assert "response_type=code" in auth_url
    assert "access_type=offline" in auth_url


@pytest.mark.asyncio
async def test_zoho_status_endpoint():
    mock_connection = ZohoConnection(
        tenant_id="default-tenant-001",
        status="CONNECTED",
        organization_id="org_123",
        organization_name="Sakshi Global Pvt Ltd",
    )

    mock_db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token(
        user_id="user_finance",
        email="finance@sakshi.ai",
        tenant_id="default-tenant-001",
        role="FINANCE",
    )
    headers = {"Authorization": f"Bearer {token}"}

    with patch.object(master_data_service, "get_or_create_zoho_connection", AsyncMock(return_value=mock_connection)):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                res = await ac.get("/api/v1/zoho/status", headers=headers)
                assert res.status_code == 200
                data = res.json()
                assert data["connected"] is True
                assert data["status"] == "CONNECTED"
                assert data["organization_name"] == "Sakshi Global Pvt Ltd"
                assert "accounts_count" in data
                assert "taxes_count" in data
                assert "vendors_count" in data
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_zoho_master_data_endpoint():
    mock_db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token(
        user_id="user_finance",
        email="finance@sakshi.ai",
        tenant_id="default-tenant-001",
        role="FINANCE",
    )
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/api/v1/zoho/master-data", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert "accounts" in data
            assert "taxes" in data
            assert "vendors" in data
            assert isinstance(data["accounts"], list)
            assert isinstance(data["taxes"], list)
            assert isinstance(data["vendors"], list)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_zoho_connect_url_endpoint():
    token = create_access_token(
        user_id="user_finance",
        email="finance@sakshi.ai",
        tenant_id="default-tenant-001",
        role="FINANCE",
    )
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/zoho/connect", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "authorization_url" in data
        assert "https://accounts.zoho.in/oauth/v2/auth" in data["authorization_url"]


@pytest.mark.asyncio
async def test_zoho_disconnect_endpoint():
    mock_connection = ZohoConnection(
        tenant_id="default-tenant-001",
        status="CONNECTED",
    )

    mock_db = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token(
        user_id="user_admin",
        email="admin@sakshi.ai",
        tenant_id="default-tenant-001",
        role="ADMIN",
    )
    headers = {"Authorization": f"Bearer {token}"}

    with patch.object(master_data_service, "get_or_create_zoho_connection", AsyncMock(return_value=mock_connection)):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                res = await ac.post("/api/v1/zoho/disconnect", headers=headers)
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "success"
                assert mock_connection.status == "DISCONNECTED"
        finally:
            app.dependency_overrides.pop(get_db, None)
