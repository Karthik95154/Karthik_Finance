import pytest
from httpx import AsyncClient, ASGITransport
import hashlib
from app.main import app
from app.schemas.invoice import InvoiceUploadResponse, InvoiceResponse


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
async def test_upload_invalid_mime_type():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("test.txt", b"plain text content", "text/plain")}
        response = await client.post("/api/v1/invoices/upload", files=files)
        assert response.status_code == 400
        assert "Unsupported file format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_empty_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("empty.pdf", b"", "application/pdf")}
        response = await client.post("/api/v1/invoices/upload", files=files)
        assert response.status_code == 400
        assert "empty" in response.json()["detail"]


def test_hash_calculation():
    sample_content = b"Sample Invoice Binary PDF Content 12345"
    expected_hash = hashlib.sha256(sample_content).hexdigest()
    assert len(expected_hash) == 64
