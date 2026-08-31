"""
Dedicated Regression Tests for Zoho Export Precondition Cases (Cases 1 to 6).
Verifies:
CASE 1: approval_status = APPROVED, status = BALANCED, is_balanced = True -> EXPORT ALLOWED
CASE 2: approval_status = APPROVED, is_balanced = False -> EXPORT BLOCKED
CASE 3: approval_status = PENDING_REVIEW, is_balanced = True -> EXPORT BLOCKED
CASE 4: approval_status = APPROVED, No JournalEntry -> EXPORT BLOCKED
CASE 5: approval_status = APPROVED, status = REVIEW_REQUIRED, is_balanced = False -> EXPORT BLOCKED
CASE 6: approval_status = APPROVED, status = POSTED, is_balanced = True -> EXPORT ALLOWED
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.db.models import Invoice, ZohoConnection, JournalEntry, TaxRate
from app.services.export_service import export_service


def _create_mock_invoice(
    invoice_id: uuid.UUID,
    tenant_id: str = "default-tenant-001",
    approval_status: str = "APPROVED",
    export_status: str = "NOT_EXPORTED",
) -> Invoice:
    return Invoice(
        id=invoice_id,
        tenant_id=tenant_id,
        file_path="uploads/test_invoice.pdf",
        file_name="test_invoice.pdf",
        file_size=2048,
        mime_type="application/pdf",
        file_hash="hash_test",
        status="COMPLETED",
        approval_status=approval_status,
        export_status=export_status,
        current_vlm_output={
            "data": {
                "invoice_number": "INV-PRECOND-01",
                "invoice_date": "2026-08-31",
                "vendor_name": "NimbusStack Cloud Solutions Pvt. Ltd.",
                "subtotal": 50000.0,
                "total_amount": 59000.0,
                "line_items": [
                    {
                        "description": "Operating expenses",
                        "quantity": 1.0,
                        "taxable_amount": 50000.0,
                        "cgst_rate": 9.0,
                        "sgst_rate": 9.0,
                        "total": 59000.0,
                    }
                ],
            }
        },
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "ACC_1",
                    "approved_account_name": "Operating expenses",
                }
            ]
        },
    )


@pytest.mark.asyncio
async def test_case_1_approved_balanced_is_allowed():
    """CASE 1: Invoice.approval_status = APPROVED, JournalEntry.status = BALANCED, is_balanced = True -> EXPORT ALLOWED."""
    inv_id = uuid.uuid4()
    tenant_id = "default-tenant-001"
    mock_inv = _create_mock_invoice(inv_id, tenant_id=tenant_id, approval_status="APPROVED")
    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id=tenant_id,
        status="BALANCED",
        is_balanced=True,
    )
    mock_conn = ZohoConnection(id=uuid.uuid4(), tenant_id=tenant_id, status="CONNECTED", organization_id="ORG_1")

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_inv)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_journal)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_conn)),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[TaxRate(zoho_tax_id="T18", tax_percentage=18.0)])))),
    ]

    with patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_vend, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_bill, \
         patch("app.storage.supabase_storage.storage_service.download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock), \
         patch("app.services.audit_service.audit_service.log_event", new_callable=AsyncMock):

        mock_vend.return_value = {"contact_id": "VEND_1"}
        mock_bill.return_value = {"bill_id": "BILL_CASE1", "bill_number": "INV-PRECOND-01"}
        mock_dl.return_value = b"pdf_data"

        res = await export_service.export_invoice_to_zoho(invoice_id=inv_id, tenant_id=tenant_id, db=mock_db)
        assert res["status"] == "success"
        assert res["zoho_bill_id"] == "BILL_CASE1"


@pytest.mark.asyncio
async def test_case_2_approved_unbalanced_is_blocked():
    """CASE 2: Invoice.approval_status = APPROVED, JournalEntry.is_balanced = False -> EXPORT BLOCKED."""
    inv_id = uuid.uuid4()
    tenant_id = "default-tenant-001"
    mock_inv = _create_mock_invoice(inv_id, tenant_id=tenant_id, approval_status="APPROVED")
    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id=tenant_id,
        status="UNBALANCED",
        is_balanced=False,
    )

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_inv)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_journal)),
    ]

    with pytest.raises(ValueError, match="approved, balanced General Ledger journal entry"):
        await export_service.export_invoice_to_zoho(invoice_id=inv_id, tenant_id=tenant_id, db=mock_db)


@pytest.mark.asyncio
async def test_case_3_pending_approval_is_blocked():
    """CASE 3: Invoice.approval_status = PENDING_REVIEW, JournalEntry balanced -> EXPORT BLOCKED."""
    inv_id = uuid.uuid4()
    tenant_id = "default-tenant-001"
    mock_inv = _create_mock_invoice(inv_id, tenant_id=tenant_id, approval_status="PENDING_REVIEW")

    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_inv))

    with pytest.raises(ValueError, match="must be APPROVED by Finance before exporting"):
        await export_service.export_invoice_to_zoho(invoice_id=inv_id, tenant_id=tenant_id, db=mock_db)


@pytest.mark.asyncio
async def test_case_4_no_journal_entry_is_blocked():
    """CASE 4: Invoice.approval_status = APPROVED, No JournalEntry in DB -> EXPORT BLOCKED."""
    inv_id = uuid.uuid4()
    tenant_id = "default-tenant-001"
    mock_inv = _create_mock_invoice(inv_id, tenant_id=tenant_id, approval_status="APPROVED")

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_inv)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # No JournalEntry
    ]

    with pytest.raises(ValueError, match="approved, balanced General Ledger journal entry"):
        await export_service.export_invoice_to_zoho(invoice_id=inv_id, tenant_id=tenant_id, db=mock_db)


@pytest.mark.asyncio
async def test_case_5_review_required_journal_is_blocked():
    """CASE 5: Invoice.approval_status = APPROVED, JournalEntry.status = REVIEW_REQUIRED, is_balanced = False -> EXPORT BLOCKED."""
    inv_id = uuid.uuid4()
    tenant_id = "default-tenant-001"
    mock_inv = _create_mock_invoice(inv_id, tenant_id=tenant_id, approval_status="APPROVED")
    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id=tenant_id,
        status="REVIEW_REQUIRED",
        is_balanced=False,
    )

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_inv)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_journal)),
    ]

    with pytest.raises(ValueError, match="approved, balanced General Ledger journal entry"):
        await export_service.export_invoice_to_zoho(invoice_id=inv_id, tenant_id=tenant_id, db=mock_db)


@pytest.mark.asyncio
async def test_case_6_posted_balanced_is_allowed():
    """CASE 6: Invoice.approval_status = APPROVED, JournalEntry.status = POSTED, is_balanced = True -> EXPORT ALLOWED."""
    inv_id = uuid.uuid4()
    tenant_id = "default-tenant-001"
    mock_inv = _create_mock_invoice(inv_id, tenant_id=tenant_id, approval_status="APPROVED")
    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id=tenant_id,
        status="POSTED",
        is_balanced=True,
    )
    mock_conn = ZohoConnection(id=uuid.uuid4(), tenant_id=tenant_id, status="CONNECTED", organization_id="ORG_1")

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_inv)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_journal)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_conn)),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[TaxRate(zoho_tax_id="T18", tax_percentage=18.0)])))),
    ]

    with patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_vend, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_bill, \
         patch("app.storage.supabase_storage.storage_service.download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock), \
         patch("app.services.audit_service.audit_service.log_event", new_callable=AsyncMock):

        mock_vend.return_value = {"contact_id": "VEND_1"}
        mock_bill.return_value = {"bill_id": "BILL_CASE6", "bill_number": "INV-PRECOND-01"}
        mock_dl.return_value = b"pdf_data"

        res = await export_service.export_invoice_to_zoho(invoice_id=inv_id, tenant_id=tenant_id, db=mock_db)
        assert res["status"] == "success"
        assert res["zoho_bill_id"] == "BILL_CASE6"
