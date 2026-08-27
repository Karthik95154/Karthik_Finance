import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.db.database import get_db
from app.db.models import Invoice
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
async def test_journal_preview_not_found(auth_headers):
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            inv_id = str(uuid.uuid4())
            response = await client.get(f"/api/v1/invoices/{inv_id}/journal-preview", headers=auth_headers)
            assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_approve_invoice_flow(auth_headers):
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="dummyhash",
        status="COMPLETED",
        accounting_status="COMPLETED",
        approval_status="PENDING_REVIEW",
        current_vlm_output={
            "data": {
                "vendor_name": "Test Vendor",
                "vendor_gstin": "27ABCDE1234F1Z5",
                "total_amount": 1180.0,
                "subtotal": 1000.0,
                "cgst_amount": 90.0,
                "sgst_amount": 90.0,
                "line_items": [
                    {
                        "description": "Test Services",
                        "taxable_amount": 1000.0,
                        "cgst_amount": 90.0,
                        "sgst_amount": 90.0,
                        "total": 1180.0,
                    }
                ]
            }
        },
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "ACC_OFFICE_1",
                    "approved_account_name": "Office Expense",
                }
            ]
        },
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/api/v1/invoices/{str(inv_id)}/approve", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["approval_status"] == "APPROVED"
            assert data["is_balanced"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_reject_invoice_flow(auth_headers):
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="dummyhash",
        status="COMPLETED",
        approval_status="PENDING_REVIEW",
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/invoices/{str(inv_id)}/reject",
                json={"reason": "Incorrect vendor GSTIN provided"},
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["approval_status"] == "REJECTED"
            assert data["reason"] == "Incorrect vendor GSTIN provided"
    finally:
        app.dependency_overrides.pop(get_db, None)
