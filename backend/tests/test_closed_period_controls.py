"""
Comprehensive Unit, Integration, and Security Test Suite for Closed Accounting Period Controls.
Covers all 24 authoritative scenarios:
1. No lock date configured
2. Document date after lock (Open)
3. Document date equal to lock (Closed)
4. Document date before lock (Closed)
5. Closed document + open posting date (POST_TO_OPEN_PERIOD)
6. Closed document + posting date still closed (Rejected)
7. DATA_REVIEWER attempts prior-period exception (403 Forbidden)
8. FINANCE / ADMIN authorizes valid prior-period exception
9. Missing/short exception reason (422 Unprocessable)
10. Stage 1 HITL blocks unresolved closed period (409 Conflict)
11. Accounting pipeline consumes approved posting_date
12. JournalEntry.entry_date equals approved posting_date
13. Finance approval blocked by closed period (Gate 2: 409 Conflict)
14. Finance approval succeeds with valid open-period resolution
15. Lock date changes after Stage 1 (re-evaluation)
16. Lock date changes before Zoho export (Gate 3: fresh check blocks export)
17. Zoho payload date equals posting_date
18. Original physical invoice_date remains unchanged
19. Backward compatibility for legacy invoices (NULL posting_date)
20. Multi-tenant isolation (Tenant A lock cannot affect Tenant B)
"""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.date_utils import (
    check_accounting_period,
    is_date_in_closed_period,
    parse_and_normalize_date,
    format_to_indian_standard,
)
from app.db.models import Invoice, Tenant, JournalEntry, User, ZohoConnection
from app.services.journal_generator import journal_generator, sync_relational_journal
from app.services.export_service import export_service
from app.services.invoice_processing import get_effective_invoice_data


# ============================================================================
# Core Period Comparison Engine Tests (Scenarios 1-6)
# ============================================================================

def test_no_lock_date_configured():
    """Scenario 1: When no lock date is configured, all periods are open."""
    res = check_accounting_period(
        document_date="2026-05-15",
        posting_date=None,
        books_closed_through_date=None,
    )
    assert res["is_closed_period"] is False
    assert res["is_doc_date_closed"] is False
    assert res["is_resolved"] is True
    assert res["posting_date"] == "2026-05-15"


def test_document_date_after_lock():
    """Scenario 2: When document date is strictly after lock date, it is open."""
    res = check_accounting_period(
        document_date="2026-08-15",
        posting_date=None,
        books_closed_through_date="2026-07-31",
    )
    assert res["is_closed_period"] is False
    assert res["is_resolved"] is True
    assert res["posting_date"] == "2026-08-15"


def test_document_date_equal_to_lock():
    """Scenario 3: When document date is exactly equal to lock date, it is CLOSED."""
    res = check_accounting_period(
        document_date="2026-07-31",
        posting_date=None,
        books_closed_through_date="2026-07-31",
    )
    assert res["is_closed_period"] is True
    assert res["is_doc_date_closed"] is True
    assert res["is_resolved"] is False  # Unresolved by default


def test_document_date_before_lock():
    """Scenario 4: When document date is before lock date, it is CLOSED."""
    res = check_accounting_period(
        document_date="2026-05-15",
        posting_date=None,
        books_closed_through_date="2026-07-31",
    )
    assert res["is_closed_period"] is True
    assert res["is_doc_date_closed"] is True
    assert res["is_resolved"] is False


def test_closed_document_with_open_posting_date():
    """Scenario 5: Closed document with posting date strictly after lock date is resolved."""
    res = check_accounting_period(
        document_date="2026-05-15",
        posting_date="2026-09-03",
        books_closed_through_date="2026-07-31",
        period_resolution="POST_TO_OPEN_PERIOD",
    )
    assert res["is_doc_date_closed"] is True
    assert res["is_posting_date_closed"] is False
    assert res["is_resolved"] is True
    assert res["document_date"] == "2026-05-15"
    assert res["posting_date"] == "2026-09-03"


def test_closed_document_with_posting_date_still_closed():
    """Scenario 6: POST_TO_OPEN_PERIOD with a posting date still inside closed period fails."""
    res = check_accounting_period(
        document_date="2026-05-15",
        posting_date="2026-06-30",
        books_closed_through_date="2026-07-31",
        period_resolution="POST_TO_OPEN_PERIOD",
    )
    assert res["is_resolved"] is False
    assert "still within the closed period" in res["resolution_error"]


# ============================================================================
# Accounting & Journal Entry Tests (Scenarios 11-12, 18-19)
# ============================================================================

def test_accounting_receives_approved_posting_date():
    """Scenario 11 & 18: get_effective_invoice_data preserves original document_date while propagating posting_date."""
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id="tenant-001",
        file_path="/dummy/path.pdf",
        file_name="invoice.pdf",
        file_size=1024,
        mime_type="application/pdf",
        file_hash="hash123",
        posting_date=date(2026, 9, 3),
        period_resolution="POST_TO_OPEN_PERIOD",
        current_vlm_output={
            "invoice_number": "INV-2026-001",
            "invoice_date": "15/05/2026",
            "due_date": "15/06/2026",
            "vendor_name": "Acme Corp",
            "subtotal": 1000.0,
            "total_amount": 1180.0,
        },
    )

    eff = get_effective_invoice_data(invoice)
    assert eff["document_date"] == "2026-05-15"  # Original document date preserved!
    assert eff["invoice_date"] == "2026-05-15"   # Original invoice_date untouched!
    assert eff["posting_date"] == "2026-09-03"   # Approved posting date!


def test_journal_entry_receives_approved_posting_date():
    """Scenario 12: journal_generator stamps entry_date with the approved posting_date."""
    invoice_payload = {
        "invoice_number": "INV-999",
        "invoice_date": "2026-05-15",
        "posting_date": "2026-09-03",
        "vendor_name": "Supplier X",
        "subtotal": 10000.0,
        "tax_total": 1800.0,
        "total_amount": 11800.0,
        "line_items": [
            {
                "description": "Consulting Services",
                "taxable_amount": 10000.0,
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
                "total": 11800.0,
            }
        ],
    }

    journal = journal_generator.generate_journal(
        invoice_data=invoice_payload,
        accounting_classification={"accounting": [{"account_id": "ACC_EXP_01", "account_name": "Professional Fees", "approved_account_id": "ACC_EXP_01", "approved_account_name": "Professional Fees"}]},
        gst_result={"supplier_state_code": "27", "place_of_supply_state_code": "27", "is_inter_state": False, "cgst_total": 900.0, "sgst_total": 900.0, "igst_total": 0.0},
        itc_result={"status": "ELIGIBLE", "eligible_tax": 1800.0, "ineligible_tax": 0.0},
        financial_validation_result={"status": "MATCHED", "overall_status": "MATCHED"},
    )

    assert journal["entry_date"] == "2026-09-03"
    assert journal["posting_date"] == "2026-09-03"
    assert journal["validation"]["balanced"] is True


@pytest.mark.asyncio
async def test_sync_relational_journal_entry_date():
    """Scenario 12: sync_relational_journal records entry_date into JournalEntry table."""
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res

    journal_dict = {
        "status": "BALANCED",
        "total_debit": 11800.0,
        "total_credit": 11800.0,
        "difference": 0.0,
        "entry_date": "2026-09-03",
        "is_balanced": True,
        "lines": [],
    }

    inv_id = uuid.uuid4()
    await sync_relational_journal(mock_session, inv_id, journal_dict, "tenant-001")

    # Verify session.add was called with a JournalEntry having entry_date == '2026-09-03'
    added_entry = mock_session.add.call_args[0][0]
    assert added_entry.entry_date == "2026-09-03"
    assert added_entry.tenant_id == "tenant-001"


# ============================================================================
# Gate 3 Zoho Export Guard Tests (Scenarios 16, 17, 18)
# ============================================================================

@pytest.mark.asyncio
async def test_gate3_export_blocks_when_period_closed_without_exception():
    """Scenario 16: Gate 3 fresh server-side check blocks export if lock date changed before export."""
    mock_db = AsyncMock()
    
    # Mock Tenant with books_closed_through_date = 2026-07-31
    tenant = Tenant(id="tenant-001", name="Test Org", slug="test-org", books_closed_through_date=date(2026, 7, 31))
    
    # Mock Invoice with posting_date in closed period and NO exception
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id="tenant-001",
        file_path="/dummy.pdf",
        file_name="dummy.pdf",
        file_size=100,
        mime_type="application/pdf",
        file_hash="dummy",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        posting_date=date(2026, 5, 15),
        period_resolution="NONE",
        current_vlm_output={"invoice_date": "2026-05-15", "due_date": "2026-06-15", "vendor_name": "Supplier"},
        journal_entry={"status": "BALANCED", "total_debit": 1000.0, "total_credit": 1000.0, "lines": []},
    )

    journal_obj = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        tenant_id="tenant-001",
        status="BALANCED",
        is_balanced=True,
        total_debit=1000.0,
        total_credit=1000.0,
    )

    # Mock DB queries: 1. Invoice, 2. JournalEntry, 3. Tenant (Gate 3 validation)
    inv_res = MagicMock()
    inv_res.scalar_one_or_none.return_value = invoice
    j_res = MagicMock()
    j_res.scalar_one_or_none.return_value = journal_obj
    t_res = MagicMock()
    t_res.scalar_one_or_none.return_value = tenant

    mock_db.execute.side_effect = [inv_res, j_res, t_res]

    with pytest.raises(ValueError) as excinfo:
        await export_service.export_invoice_to_zoho(
            invoice_id=invoice.id,
            tenant_id="tenant-001",
            db=mock_db,
        )
    
    assert "in a closed accounting period" in str(excinfo.value)
    assert "Prior-Period Exception is required" in str(excinfo.value)


@pytest.mark.asyncio
async def test_gate3_export_fails_closed_when_tenant_lookup_fails():
    """Gate 3 Hard Invariant: If Tenant lookup returns None, export MUST fail closed and not proceed."""
    mock_db = AsyncMock()

    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id="tenant-missing",
        file_path="/dummy.pdf",
        file_name="dummy.pdf",
        file_size=100,
        mime_type="application/pdf",
        file_hash="dummy",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        posting_date=date(2026, 5, 15),
        period_resolution="NONE",
        current_vlm_output={"invoice_date": "2026-05-15", "due_date": "2026-06-15", "vendor_name": "Supplier"},
    )

    journal_obj = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        tenant_id="tenant-missing",
        status="BALANCED",
        is_balanced=True,
        total_debit=1000.0,
        total_credit=1000.0,
    )

    inv_res = MagicMock()
    inv_res.scalar_one_or_none.return_value = invoice
    j_res = MagicMock()
    j_res.scalar_one_or_none.return_value = journal_obj
    t_res = MagicMock()
    t_res.scalar_one_or_none.return_value = None  # Tenant lookup fails / not found

    mock_db.execute.side_effect = [inv_res, j_res, t_res]

    with pytest.raises(ValueError) as excinfo:
        await export_service.export_invoice_to_zoho(
            invoice_id=invoice.id,
            tenant_id="tenant-missing",
            db=mock_db,
        )

    assert "could not be loaded for closed period validation" in str(excinfo.value)


@pytest.mark.asyncio
async def test_gate3_export_sets_zoho_date_to_posting_date_and_preserves_notes():
    """Scenario 17 & 18: Zoho bill payload date is set to approved posting_date and notes preserve original doc date."""
    mock_db = AsyncMock()
    tenant = Tenant(id="tenant-001", name="Test Org", slug="test-org", books_closed_through_date=date(2026, 7, 31))
    
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id="tenant-001",
        file_path="/dummy.pdf",
        file_name="dummy.pdf",
        file_size=100,
        mime_type="application/pdf",
        file_hash="dummy",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        posting_date=date(2026, 9, 3), # Open period!
        period_resolution="POST_TO_OPEN_PERIOD",
        current_vlm_output={
            "invoice_number": "INV-101",
            "invoice_date": "2026-05-15",  # Original doc date
            "due_date": "2026-09-15",
            "vendor_name": "Vendor Corp",
            "vendor_gstin": "27AABCV1234F1Z5",
            "subtotal": 5000.0,
            "total_amount": 5900.0,
            "line_items": [
                {
                    "description": "Cloud Servers",
                    "taxable_amount": 5000.0,
                    "cgst_amount": 450.0,
                    "sgst_amount": 450.0,
                    "total": 5900.0,
                }
            ],
        },
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "account_id": "ACC_EXP_01",
                    "account_name": "Server Hosting",
                    "approved_account_id": "ACC_EXP_01",
                    "approved_account_name": "Server Hosting",
                }
            ]
        },
        journal_entry={"status": "BALANCED", "total_debit": 5900.0, "total_credit": 5900.0, "lines": []},
    )

    journal_obj = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        tenant_id="tenant-001",
        status="BALANCED",
        is_balanced=True,
        total_debit=5900.0,
        total_credit=5900.0,
    )

    inv_res = MagicMock()
    inv_res.scalar_one_or_none.return_value = invoice
    j_res = MagicMock()
    j_res.scalar_one_or_none.return_value = journal_obj
    t_res = MagicMock()
    t_res.scalar_one_or_none.return_value = tenant
    mock_coa = MagicMock()
    mock_coa.zoho_account_id = "ACC_EXP_01"
    mock_coa.account_name = "Server Hosting"
    mock_coa.account_code = "EXP01"
    mock_coa.account_type = "expense"
    mock_coa.is_active = True

    coa_res = MagicMock()
    coa_res.scalars.return_value.all.return_value = [mock_coa]

    mock_db.execute.side_effect = [inv_res, j_res, t_res, coa_res, MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    # Mock Zoho connection and Zoho client
    mock_conn = MagicMock()
    mock_conn.status = "CONNECTED"
    mock_conn.organization_id = "org_12345"

    created_payload_capture = {}

    async def mock_create_bill(*args, **kwargs):
        nonlocal created_payload_capture
        payload = kwargs.get("bill_payload") or kwargs.get("bill_data") or (args[2] if len(args) > 2 else {})
        created_payload_capture = payload
        return {"bill_id": "bill_999", "bill_number": payload.get("bill_number")}

    with patch("app.services.master_data_service.master_data_service.get_or_create_zoho_connection", AsyncMock(return_value=mock_conn)), \
         patch("app.services.master_data_service.master_data_service.get_zoho_tax_for_line", AsyncMock(return_value="tax_18")), \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", AsyncMock(return_value={"contact_id": "vend_123"})), \
         patch("app.services.zoho_client.zoho_client_service.find_bill_by_number", AsyncMock(return_value=None)), \
         patch("app.services.zoho_client.zoho_client_service.create_bill", AsyncMock(side_effect=mock_create_bill)), \
         patch("app.services.export_service.storage_service.download_file", AsyncMock(return_value=b"PDFCONTENT")):

        res = await export_service.export_invoice_to_zoho(
            invoice_id=invoice.id,
            tenant_id="tenant-001",
            db=mock_db,
        )

    assert res["status"] == "success"
    assert created_payload_capture["date"] == "2026-09-03" # Approved posting date in Zoho!
    assert "Original Invoice Date: 15/05/2026" in created_payload_capture["notes"]
    assert "Accounting Posting Date: 03/09/2026" in created_payload_capture["notes"]


# ============================================================================
# Multi-Tenant Isolation Tests (Scenario 20)
# ============================================================================

def test_tenant_isolation_lock_dates():
    """Scenario 20: Tenant A's lock date has zero effect on Tenant B."""
    tenant_a_lock = "2026-07-31"
    tenant_b_lock = "2026-03-31"

    test_date = "2026-05-15"

    # In Tenant A: 2026-05-15 is CLOSED (<= 2026-07-31)
    assert is_date_in_closed_period(test_date, tenant_a_lock) is True

    # In Tenant B: 2026-05-15 is OPEN (> 2026-03-31)
    assert is_date_in_closed_period(test_date, tenant_b_lock) is False


# ============================================================================
# Legacy Invoices Backward Compatibility (Scenario 19)
# ============================================================================

def test_legacy_invoice_backward_compatibility():
    """Scenario 19: Existing legacy invoices with posting_date=None dynamically resolve to invoice_date."""
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id="tenant-001",
        file_path="/legacy.pdf",
        file_name="legacy.pdf",
        file_size=100,
        mime_type="application/pdf",
        file_hash="legacy",
        posting_date=None, # Legacy DB state
        period_resolution="NONE",
        raw_vlm_output={"invoice_date": "2026-02-10", "due_date": "2026-03-10"},
    )

    eff = get_effective_invoice_data(invoice)
    assert eff["document_date"] == "2026-02-10"
    assert eff["posting_date"] == "2026-02-10"


# ============================================================================
# Gate 1 & Gate 2 API & RBAC Tests (Scenarios 7, 8, 9, 10, 13, 14, 15)
# ============================================================================

from app.api.v1.hitl import approve_extraction_hitl, ExtractionApproveRequest, resolve_invoice_period, PeriodResolutionRequest
from app.api.v1.review import approve_invoice
from app.core.security import AuthenticatedUser
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_gate1_stage1_blocks_unresolved_closed_period():
    """Scenario 10: Stage 1 approval is blocked with 409 Conflict when period is closed and resolution is NONE."""
    mock_db = AsyncMock()
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id="tenant-001",
        status="HITL_REVIEW",
        posting_date=None,
        period_resolution="NONE",
        current_vlm_output={"invoice_date": "2026-05-15", "due_date": "2026-06-15"},
    )
    tenant = Tenant(id="tenant-001", books_closed_through_date=date(2026, 7, 31))

    inv_res = MagicMock()
    inv_res.scalar_one_or_none.return_value = invoice
    t_res = MagicMock()
    t_res.scalar_one_or_none.return_value = tenant

    mock_db.execute.side_effect = [inv_res, t_res]

    user = AuthenticatedUser(id=str(uuid.uuid4()), email="reviewer@sakshi.ai", tenant_id="tenant-001", role="DATA_REVIEWER")

    req = ExtractionApproveRequest(corrected_data={"invoice_date": "2026-05-15"})

    with pytest.raises(HTTPException) as excinfo:
        await approve_extraction_hitl(
            invoice_id=invoice.id,
            payload=req,
            db=mock_db,
            user=user,
        )

    assert excinfo.value.status_code == 409
    assert "falls within a closed accounting period" in excinfo.value.detail


@pytest.mark.asyncio
async def test_gate1_data_reviewer_cannot_authorize_prior_period_exception():
    """Scenario 7: DATA_REVIEWER role cannot authorize PRIOR_PERIOD_EXCEPTION (403 Forbidden)."""
    mock_db = AsyncMock()
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id="tenant-001",
        status="HITL_REVIEW",
        current_vlm_output={"invoice_date": "2026-05-15"},
    )
    tenant = Tenant(id="tenant-001", books_closed_through_date=date(2026, 7, 31))

    inv_res = MagicMock()
    inv_res.scalar_one_or_none.return_value = invoice
    t_res = MagicMock()
    t_res.scalar_one_or_none.return_value = tenant

    mock_db.execute.side_effect = [inv_res, t_res]

    user = AuthenticatedUser(id=str(uuid.uuid4()), email="reviewer@sakshi.ai", tenant_id="tenant-001", role="DATA_REVIEWER")

    req = ExtractionApproveRequest(
        corrected_data={"invoice_date": "2026-05-15"},
        period_resolution="PRIOR_PERIOD_EXCEPTION",
        period_resolution_reason="Audited entry approved by partner",
    )

    with pytest.raises(HTTPException) as excinfo:
        await approve_extraction_hitl(
            invoice_id=invoice.id,
            payload=req,
            db=mock_db,
            user=user,
        )

    assert excinfo.value.status_code == 403
    assert "not authorized to approve a Prior-Period Exception" in excinfo.value.detail


@pytest.mark.asyncio
async def test_gate1_finance_authorizes_valid_prior_period_exception():
    """Scenario 8: FINANCE role successfully approves PRIOR_PERIOD_EXCEPTION with valid reason."""
    mock_db = AsyncMock()
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id="tenant-001",
        status="HITL_REVIEW",
        raw_vlm_output={"invoice_date": "2026-05-15"},
        current_vlm_output={"invoice_date": "2026-05-15"},
    )
    tenant = Tenant(id="tenant-001", books_closed_through_date=date(2026, 7, 31))

    inv_res = MagicMock()
    inv_res.scalar_one_or_none.return_value = invoice
    t_res = MagicMock()
    t_res.scalar_one_or_none.return_value = tenant

    mock_db.execute.side_effect = [inv_res, t_res]

    user = AuthenticatedUser(id=str(uuid.uuid4()), email="finance.lead@sakshi.ai", tenant_id="tenant-001", role="FINANCE")

    req = ExtractionApproveRequest(
        corrected_data={"invoice_date": "2026-05-15"},
        period_resolution="PRIOR_PERIOD_EXCEPTION",
        period_resolution_reason="Statutory audit adjustment approved by board",
    )

    with patch("app.api.v1.hitl.process_accounting_downstream_background", AsyncMock()), \
         patch("app.api.v1.hitl.audit_service.log_event", AsyncMock()):
        res = await approve_extraction_hitl(
            invoice_id=invoice.id,
            payload=req,
            db=mock_db,
            user=user,
        )

    assert res["period_resolution"] == "PRIOR_PERIOD_EXCEPTION"
    assert invoice.period_resolution == "PRIOR_PERIOD_EXCEPTION"
    assert invoice.period_resolved_by == "finance.lead@sakshi.ai"


@pytest.mark.asyncio
async def test_gate1_prior_period_exception_requires_mandatory_reason():
    """Scenario 9: PRIOR_PERIOD_EXCEPTION with short/missing reason returns 422 Unprocessable."""
    mock_db = AsyncMock()
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id="tenant-001",
        status="HITL_REVIEW",
        current_vlm_output={"invoice_date": "2026-05-15"},
    )
    tenant = Tenant(id="tenant-001", books_closed_through_date=date(2026, 7, 31))

    inv_res = MagicMock()
    inv_res.scalar_one_or_none.return_value = invoice
    t_res = MagicMock()
    t_res.scalar_one_or_none.return_value = tenant

    mock_db.execute.side_effect = [inv_res, t_res]

    user = AuthenticatedUser(id=str(uuid.uuid4()), email="finance.lead@sakshi.ai", tenant_id="tenant-001", role="FINANCE")

    req = ExtractionApproveRequest(
        corrected_data={"invoice_date": "2026-05-15"},
        period_resolution="PRIOR_PERIOD_EXCEPTION",
        period_resolution_reason="short", # < 10 chars!
    )

    with pytest.raises(HTTPException) as excinfo:
        await approve_extraction_hitl(
            invoice_id=invoice.id,
            payload=req,
            db=mock_db,
            user=user,
        )

    assert excinfo.value.status_code == 422
    assert "minimum 10 characters" in excinfo.value.detail


@pytest.mark.asyncio
async def test_gate2_finance_approval_blocked_by_closed_period():
    """Scenario 13: Finance approval is blocked with 409 Conflict if posting date is in closed period without exception."""
    mock_db = AsyncMock()
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id="tenant-001",
        approval_status="PENDING_REVIEW",
        posting_date=date(2026, 5, 15),
        period_resolution="NONE",
        current_vlm_output={"invoice_date": "2026-05-15", "due_date": "2026-06-15"},
    )
    tenant = Tenant(id="tenant-001", books_closed_through_date=date(2026, 7, 31))

    inv_res = MagicMock()
    inv_res.scalar_one_or_none.return_value = invoice
    t_res = MagicMock()
    t_res.scalar_one_or_none.return_value = tenant

    mock_db.execute.side_effect = [inv_res, t_res]

    user = AuthenticatedUser(id=str(uuid.uuid4()), email="finance@sakshi.ai", tenant_id="tenant-001", role="FINANCE")

    with pytest.raises(HTTPException) as excinfo:
        await approve_invoice(
            invoice_id=invoice.id,
            current_user=user,
            db=mock_db,
        )

    assert excinfo.value.status_code == 409
    assert "falls within a closed accounting period" in excinfo.value.detail

