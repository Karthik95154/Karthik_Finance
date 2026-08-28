import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.core.security import create_access_token
from app.db.models import Invoice, ZohoConnection, ChartOfAccount, TaxRate, JournalEntry
from app.services.journal_generator import journal_generator
from app.services.export_service import export_service
from app.api.v1.review import approve_invoice, RejectRequest, reject_invoice
from app.core.security import AuthenticatedUser
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_g_journal_refuses_ai_fallback_in_authoritative_mode():
    """Test G: Authoritative journal generator raises ValueError if any line lacks approved_account_id (no AI fallback)."""
    invoice_data = {
        "vendor_name": "Test Vendor",
        "total_amount": 11800.0,
        "subtotal": 10000.0,
        "line_items": [{"description": "Server hosting", "quantity": 1, "unit_price": 10000.0, "cgst_rate": 9, "cgst_amount": 900, "sgst_rate": 9, "sgst_amount": 900}],
    }
    
    # Accounting output with ONLY AI suggestions (unapproved)
    accounting_with_ai_only = {
        "accounting": [
            {
                "line_index": 1,
                "ai_account_id": "ACC_AI_SUGGESTION",
                "ai_account_name": "Hosting Charges",
                "approved_account_id": None,  # NOT approved
                "approved_account_name": None,
            }
        ]
    }

    # 1. require_approved=True MUST fail
    with pytest.raises(ValueError, match="has not been approved by Finance"):
        journal_generator.generate_journal_entry(
            invoice_data=invoice_data,
            accounting_data=accounting_with_ai_only,
            require_approved=True,
        )

    # 2. require_approved=False (Preview mode) works and flags has_unapproved_lines=True
    preview = journal_generator.generate_journal_entry(
        invoice_data=invoice_data,
        accounting_data=accounting_with_ai_only,
        require_approved=False,
    )
    assert preview["has_unapproved_lines"] is True
    assert "[Unapproved]" in preview["lines"][0]["account_name"]


@pytest.mark.asyncio
async def test_f_approval_fails_without_approved_account_id():
    """Test F: Invoice approval fails with 400 if any line item lacks approved_account_id."""
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="tenant-a",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="hash_1",
        status="COMPLETED",
        approval_status="PENDING_REVIEW",
        current_vlm_output={"data": {"total_amount": 1000.0, "subtotal": 1000.0, "line_items": [{"description": "Item 1", "unit_price": 1000.0}]}},
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "ai_account_id": "ACC_AI",
                    "ai_account_name": "AI Account",
                    "approved_account_id": None,  # Not approved!
                    "approved_account_name": None,
                }
            ]
        },
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result

    user = AuthenticatedUser(
        id=str(uuid.uuid4()),
        email="finance@tenant-a.com",
        tenant_id="tenant-a",
        role="FINANCE",
    )

    with pytest.raises(HTTPException) as exc_info:
        await approve_invoice(invoice_id=inv_id, current_user=user, db=mock_db)

    assert exc_info.value.status_code == 400
    assert "has not been approved by Finance" in exc_info.value.detail


@pytest.mark.asyncio
async def test_l_finance_can_approve_with_approved_accounts():
    """Test L: Finance user can approve when all lines have approved_account_id."""
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="tenant-a",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="hash_1",
        status="COMPLETED",
        approval_status="PENDING_REVIEW",
        current_vlm_output={"data": {"total_amount": 1000.0, "subtotal": 1000.0, "line_items": [{"description": "Item 1", "unit_price": 1000.0}]}},
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "ACC_APPROVED_123",
                    "approved_account_name": "Approved Software License",
                }
            ]
        },
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    user = AuthenticatedUser(
        id=str(uuid.uuid4()),
        email="finance@tenant-a.com",
        tenant_id="tenant-a",
        role="FINANCE",
    )

    with patch("app.services.audit_service.audit_service.log_event", new_callable=AsyncMock):
        res = await approve_invoice(invoice_id=inv_id, current_user=user, db=mock_db)

    assert res["status"] == "success"
    assert res["approval_status"] == "APPROVED"
    assert mock_invoice.approval_status == "APPROVED"
    assert mock_invoice.locked_at is not None


@pytest.mark.asyncio
async def test_e_tenant_a_cannot_access_tenant_b_invoice():
    """Test E: User in Tenant A querying an invoice in Tenant B receives 404."""
    inv_id = uuid.uuid4()
    # DB query filters with Invoice.tenant_id == current_user.tenant_id ('tenant-a')
    # If the invoice in DB is owned by tenant-b, the query returns None.
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # Not found for tenant-a!
    mock_db.execute.return_value = mock_result

    user_tenant_a = AuthenticatedUser(
        id=str(uuid.uuid4()),
        email="finance@tenant-a.com",
        tenant_id="tenant-a",
        role="FINANCE",
    )

    with pytest.raises(HTTPException) as exc_info:
        await approve_invoice(invoice_id=inv_id, current_user=user_tenant_a, db=mock_db)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_n_export_refuses_ai_fallback():
    """Test N: Export fails if any line item uses only ai_account_id without Finance approval."""
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="tenant-a",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="hash_1",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        current_vlm_output={"data": {"invoice_number": "INV-100", "total_amount": 1000.0, "subtotal": 1000.0, "line_items": [{"description": "Item 1", "unit_price": 1000.0}]}},
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "ai_account_id": "ACC_AI_SUGG",
                    "ai_account_name": "AI Sugg",
                    "approved_account_id": None,  # Not approved!
                    "approved_account_name": None,
                }
            ]
        },
    )

    mock_connection = ZohoConnection(
        id=uuid.uuid4(),
        tenant_id="tenant-a",
        organization_id="ORG_123",
        status="CONNECTED",
    )

    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id="tenant-a",
        is_balanced=True,
        status="APPROVED",
    )

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_invoice)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_journal)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_connection)),
    ]
    mock_db.commit = AsyncMock()

    with pytest.raises(RuntimeError, match="lacks a Finance-approved Chart of Accounts"):
        await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id="tenant-a",
            db=mock_db,
            user_email="finance@tenant-a.com",
        )


@pytest.mark.asyncio
async def test_h_zoho_create_timeout_followed_by_reconciliation():
    """Test H & P: Timeout during Zoho Bill creation is safely reconciled on retry without duplicate Bill creation."""
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="tenant-a",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="hash_1",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        current_vlm_output={"data": {"invoice_number": "INV-TIMEOUT-99", "total_amount": 5000.0, "subtotal": 5000.0, "line_items": [{"description": "Dev", "unit_price": 5000.0}]}},
        current_accounting_output={
            "accounting": [{"line_index": 1, "approved_account_id": "ACC_APP_1", "approved_account_name": "Dev Exp"}]
        },
    )

    mock_connection = ZohoConnection(
        id=uuid.uuid4(),
        tenant_id="tenant-a",
        organization_id="ORG_123",
        status="CONNECTED",
    )

    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id="tenant-a",
        is_balanced=True,
        status="APPROVED",
    )

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_invoice)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_journal)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_connection)),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),  # taxes
    ]
    mock_db.commit = AsyncMock()

    with patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_search_vendor, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_create_bill, \
         patch("app.services.zoho_client.zoho_client_service.find_bill_by_number", new_callable=AsyncMock) as mock_find_bill, \
         patch("app.storage.supabase_storage.storage_service.download_file", new_callable=AsyncMock) as mock_download, \
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock) as mock_attach, \
         patch("app.services.audit_service.audit_service.log_event", new_callable=AsyncMock):

        mock_search_vendor.return_value = {"contact_id": "VEND_123"}
        # find_bill before create returns None
        # create_bill throws a Timeout / Connection Error
        # post-failure find_bill returns the bill that Zoho actually created before the timeout!
        mock_find_bill.side_effect = [
            None,  # Pre-check: bill does not exist yet
            {"bill_id": "BILL_RECOVERED_888", "bill_number": "INV-TIMEOUT-99", "vendor_id": "VEND_123"},  # Recovery check finds it!
        ]
        mock_create_bill.side_effect = TimeoutError("HTTP Connection timed out after 30s")
        mock_download.return_value = b"pdf-bytes"
        mock_attach.return_value = {"status": "success"}

        res = await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id="tenant-a",
            db=mock_db,
            user_email="finance@tenant-a.com",
        )

        assert res["status"] == "success"
        assert res["zoho_bill_id"] == "BILL_RECOVERED_888"
        assert mock_invoice.export_status == "EXPORTED"
        assert mock_invoice.zoho_bill_id == "BILL_RECOVERED_888"


@pytest.mark.asyncio
async def test_q_attachment_retry_uses_existing_zoho_bill_id():
    """Test Q: If Bill is created but attachment failed, subsequent export retries reuse existing zoho_bill_id."""
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="tenant-a",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="hash_1",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="FAILED",
        zoho_bill_id="BILL_ALREADY_CREATED_555",  # Bill was already created in prior attempt!
        zoho_bill_number="INV-100",
        current_vlm_output={"data": {"invoice_number": "INV-100", "total_amount": 1000.0, "subtotal": 1000.0, "line_items": [{"description": "Item 1", "unit_price": 1000.0}]}},
        current_accounting_output={
            "accounting": [{"line_index": 1, "approved_account_id": "ACC_APP_1", "approved_account_name": "Dev Exp"}]
        },
    )

    mock_connection = ZohoConnection(
        id=uuid.uuid4(),
        tenant_id="tenant-a",
        organization_id="ORG_123",
        status="CONNECTED",
    )

    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id="tenant-a",
        is_balanced=True,
        status="APPROVED",
    )

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_invoice)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_journal)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_connection)),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
    ]
    mock_db.commit = AsyncMock()

    with patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_search_vendor, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_create_bill, \
         patch("app.storage.supabase_storage.storage_service.download_file", new_callable=AsyncMock) as mock_download, \
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock) as mock_attach, \
         patch("app.services.audit_service.audit_service.log_event", new_callable=AsyncMock):

        mock_search_vendor.return_value = {"contact_id": "VEND_123"}
        mock_download.return_value = b"pdf-bytes"
        mock_attach.return_value = {"status": "success"}

        res = await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id="tenant-a",
            db=mock_db,
            user_email="finance@tenant-a.com",
        )

        assert res["status"] == "success"
        assert res["zoho_bill_id"] == "BILL_ALREADY_CREATED_555"
        # Verify create_bill was NEVER called again!
        mock_create_bill.assert_not_called()
        # Verify attachment was attempted on the existing Bill ID
        mock_attach.assert_called_once_with(
            connection=mock_connection,
            db=mock_db,
            bill_id="BILL_ALREADY_CREATED_555",
            file_bytes=b"pdf-bytes",
            filename="test.pdf",
            mime_type="application/pdf",
        )
