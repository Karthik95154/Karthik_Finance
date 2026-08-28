import pytest
import hashlib
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token


@pytest.fixture
def auth_headers():
    token = create_access_token(
        user_id=str(uuid.uuid4()),
        email="finance@default-org.com",
        tenant_id="default-tenant-001",
        role="FINANCE",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_root_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "Finance Web Application" in data["message"]
        assert data["health"] == "/api/v1/health"


@pytest.mark.asyncio
async def test_upload_invalid_mime_type(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("test.txt", b"plain text content", "text/plain")}
        response = await client.post("/api/v1/invoices/upload", files=files, headers=auth_headers)
        assert response.status_code == 400
        assert "Unsupported file format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_empty_file(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("empty.pdf", b"", "application/pdf")}
        response = await client.post("/api/v1/invoices/upload", files=files, headers=auth_headers)
        assert response.status_code == 400
        assert "empty" in response.json()["detail"]


def test_hash_calculation():
    sample_content = b"Sample Invoice Binary PDF Content 12345"
    expected_hash = hashlib.sha256(sample_content).hexdigest()
    assert len(expected_hash) == 64
