"""
Comprehensive unit & integration tests for:
1. Internal Finance HITL Review Flow
2. Customer Invoice Flow & Separation
3. Authoritative Journal Overrides & Live Balancing
4. Immutability of raw_vlm_output
5. Role-aware State Machine (Customer edits after approval never trigger second HITL review)
"""

import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.database import get_db
from app.core.security import create_access_token
from app.db.models import Invoice


@pytest.fixture
def finance_token():
    return create_access_token(
        user_id="fin_user_1",
        email="finance@sakshi.ai",
        tenant_id="default-tenant-001",
        role="FINANCE",
    )


@pytest.fixture
def customer_token():
    return create_access_token(
        user_id="cust_user_1",
        email="customer@client.com",
        tenant_id="default-tenant-001",
        role="CUSTOMER",
    )


@pytest.mark.asyncio
async def test_customer_access_blocked_before_approval(customer_token):
    """Customer role receives 403 Forbidden when trying to view an unapproved invoice."""
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/pending_invoice.pdf",
        file_name="pending_invoice.pdf",
        file_size=1024,
        mime_type="application/pdf",
        file_hash="hash123",
        status="COMPLETED",
        approval_status="PENDING_REVIEW",
        raw_vlm_output={"data": {"invoice_number": "INV-100", "total_amount": 1180.0}},
        current_vlm_output={"data": {"invoice_number": "INV-100", "total_amount": 1180.0}},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {customer_token}"}
            res = await client.get(f"/api/v1/invoices/{inv_id}", headers=headers)
            assert res.status_code == 403
            assert "Customer access unavailable" in res.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_customer_access_allowed_after_approval(customer_token):
    """Customer role successfully accesses invoice metadata once approval_status == 'APPROVED'."""
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/approved_invoice.pdf",
        file_name="approved_invoice.pdf",
        file_size=2048,
        mime_type="application/pdf",
        file_hash="hash456",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        raw_vlm_output={"data": {"invoice_number": "INV-200", "total_amount": 2360.0}},
        current_vlm_output={"data": {"invoice_number": "INV-200", "total_amount": 2360.0}},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {customer_token}"}
            res = await client.get(f"/api/v1/invoices/{inv_id}", headers=headers)
            assert res.status_code == 200
            assert res.json()["id"] == str(inv_id)
            assert res.json()["approval_status"] == "APPROVED"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_customer_edit_retains_approved_status_no_second_hitl(customer_token):
    """Customer edit on an approved invoice updates values and validates journal without resetting to PENDING_REVIEW."""
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/test_doc.pdf",
        file_name="test_doc.pdf",
        file_size=4096,
        mime_type="application/pdf",
        file_hash="hash789",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        raw_vlm_output={"data": {"invoice_number": "INV-RAW", "total_amount": 1000.0}},
        current_vlm_output={"data": {"invoice_number": "INV-RAW", "total_amount": 1000.0}},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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
        edit_payload = {
            "current_vlm_output": {
                "data": {
                    "invoice_number": "INV-CUSTOMER-EDIT",
                    "subtotal": 2000.0,
                    "cgst_amount": 180.0,
                    "sgst_amount": 180.0,
                    "total_amount": 2360.0,
                    "line_items": [
                        {
                            "description": "Item 1",
                            "taxable_amount": 2000.0,
                            "cgst_rate": 9.0,
                            "cgst_amount": 180.0,
                            "sgst_rate": 9.0,
                            "sgst_amount": 180.0,
                            "total": 2360.0,
                        }
                    ],
                }
            }
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {customer_token}"}
            res = await client.put(f"/api/v1/invoices/{inv_id}", json=edit_payload, headers=headers)
            assert res.status_code == 200
            # Approval status must remain APPROVED - never reset to PENDING_REVIEW for customer edits
            assert mock_invoice.approval_status == "APPROVED"
            # raw_vlm_output must remain completely untouched
            assert mock_invoice.raw_vlm_output["data"]["invoice_number"] == "INV-RAW"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_manual_journal_override_saved_authoritatively(finance_token):
    """When explicit manual journal lines are sent, they are preserved with HITL_OVERRIDE provenance and synced."""
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/invoice_journal.pdf",
        file_name="invoice_journal.pdf",
        file_size=8192,
        mime_type="application/pdf",
        file_hash="hash999",
        status="COMPLETED",
        approval_status="PENDING_REVIEW",
        export_status="NOT_EXPORTED",
        raw_vlm_output={"data": {"invoice_number": "INV-300", "total_amount": 5000.0}},
        current_vlm_output={"data": {"invoice_number": "INV-300", "total_amount": 5000.0}},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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
        manual_journal_payload = {
            "current_vlm_output": {
                "data": {
                    "invoice_number": "INV-300",
                    "subtotal": 5000.0,
                    "total_amount": 5000.0,
                }
            },
            "journal_entry": {
                "lines": [
                    {
                        "account_id": "ACC_EXPENSE_1",
                        "account_name": "Software Subscription",
                        "line_type": "EXPENSE",
                        "debit": 5000.0,
                        "credit": 0.0,
                        "description": "Manual override expense line",
                    },
                    {
                        "account_id": "ACC_AP_1",
                        "account_name": "Accounts Payable",
                        "line_type": "ACCOUNTS_PAYABLE",
                        "debit": 0.0,
                        "credit": 5000.0,
                        "description": "Manual override AP line",
                    },
                ]
            }
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {finance_token}"}
            res = await client.put(f"/api/v1/invoices/{inv_id}", json=manual_journal_payload, headers=headers)
            assert res.status_code == 200

            # Verify journal output in response / invoice
            assert mock_invoice.journal_entry["status"] == "BALANCED"
            assert mock_invoice.journal_entry["total_debit"] == 5000.0
            assert mock_invoice.journal_entry["total_credit"] == 5000.0
            assert mock_invoice.journal_entry["difference"] == 0.0
            assert len(mock_invoice.journal_entry["lines"]) == 2
            assert mock_invoice.journal_entry["lines"][0]["provenance"] == "HITL_OVERRIDE"
            assert mock_invoice.journal_entry["lines"][0]["account_name"] == "Software Subscription"
    finally:
        app.dependency_overrides.pop(get_db, None)
