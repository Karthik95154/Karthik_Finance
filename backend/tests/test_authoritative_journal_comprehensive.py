"""
Comprehensive test suite verifying authoritative double-entry General Ledger
accounting, ITC/GST/TDS source of truth, preview vs approval identity,
and regression prevention for unbalanced journal issues.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from app.services.journal_generator import journal_generator
from app.services.itc_engine import itc_engine
from app.api.v1.review import approve_invoice, get_journal_preview
from app.db.models import Invoice, JournalEntry
from app.core.security import AuthenticatedUser


def test_a_normal_intra_state_invoice():
    """Test A: Normal intra-state invoice (Expense 15k, CGST 1350, SGST 1350 -> Total 17.7k)."""
    invoice_data = {
        "invoice_number": "INV-A1",
        "subtotal": 15000.0,
        "tax_total": 2700.0,
        "cgst_amount": 1350.0,
        "sgst_amount": 1350.0,
        "total_amount": 17700.0,
        "vendor_name": "Intra Vendor",
        "line_items": [{"description": "Office Chairs", "taxable_amount": 15000.0}],
    }
    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_3",
                "approved_account_name": "Office Furniture & Supplies",
            }
        ]
    }
    gst_result = {
        "supply_type": "INTRA_STATE",
        "validation_status": "PASSED",
        "calculated": {"cgst_amount": 1350.0, "sgst_amount": 1350.0, "gst_total": 2700.0},
    }
    itc_result = {
        "status": "ELIGIBLE",
        "eligible_itc": 2700.0,
        "blocked_itc": 0.0,
        "reversal_itc": 0.0,
        "review_amount": 0.0,
        "net_itc_available": 2700.0,
    }

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting,
        gst_result=gst_result,
        itc_result=itc_result,
    )

    assert journal["status"] == "BALANCED"
    assert journal["validation"]["balanced"] is True
    assert journal["total_debit"] == 17700.0
    assert journal["total_credit"] == 17700.0

    lines = journal["lines"]
    cgst_line = next(l for l in lines if l["account_id"] == "TAX_INP_CGST")
    sgst_line = next(l for l in lines if l["account_id"] == "TAX_INP_SGST")
    ap_line = next(l for l in lines if l["account_id"] == "LIAB_AP")

    assert cgst_line["debit"] == 1350.0
    assert sgst_line["debit"] == 1350.0
    assert ap_line["credit"] == 17700.0


def test_b_inter_state_invoice_and_previous_bug_regression():
    """Test B & Previous Bug: Inter-state invoice (Expense 5500, IGST 990, AP 6490) must balance perfectly in Preview and Approval."""
    invoice_data = {
        "invoice_number": "INV-2025-26-0778",
        "subtotal": 5500.0,
        "tax_total": 990.0,
        "igst_amount": 990.0,
        "total_amount": 6490.0,
        "vendor_name": "Armstrong Vendor",
        "line_items": [{"description": "Technical Consulting", "taxable_amount": 5500.0}],
    }
    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_5",
                "approved_account_name": "Consulting & Technical Services",
            }
        ]
    }
    gst_result = {
        "supply_type": "INTER_STATE",
        "validation_status": "PASSED",
        "calculated": {"igst_amount": 990.0, "gst_total": 990.0},
    }
    itc_result = {
        "status": "ELIGIBLE",
        "eligible_itc": 990.0,
        "blocked_itc": 0.0,
        "net_itc_available": 990.0,
    }

    # 1. Preview Generation
    preview_journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting,
        gst_result=gst_result,
        itc_result=itc_result,
    )
    assert preview_journal["validation"]["balanced"] is True
    assert preview_journal["total_debit"] == 6490.0
    assert preview_journal["total_credit"] == 6490.0

    # 2. Approval Entry Generation (require_approved=True)
    approval_journal = journal_generator.generate_journal_entry(
        invoice_data=invoice_data,
        accounting_data=accounting,
        gst_result=gst_result,
        itc_result=itc_result,
        require_approved=True,
    )
    assert approval_journal["is_balanced"] is True
    assert approval_journal["total_debit"] == 6490.0
    assert approval_journal["total_credit"] == 6490.0

    # 3. Preview == Approval Identity
    assert preview_journal["total_debit"] == approval_journal["total_debit"]
    assert preview_journal["total_credit"] == approval_journal["total_credit"]


def test_c_blocked_itc_routed_to_ineligible_tax_expense():
    """Test C: Section 17(5) blocked motor car input tax is debited to TAX_BLOCKED rather than input tax receivable."""
    invoice_data = {
        "invoice_number": "INV-CAR-101",
        "subtotal": 1200000.0,
        "tax_total": 336000.0,
        "cgst_amount": 168000.0,
        "sgst_amount": 168000.0,
        "total_amount": 1536000.0,
        "line_items": [{"description": "Sedan Car for Director", "taxable_amount": 1200000.0}],
    }
    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_6",
                "approved_account_name": "Vehicles & Fixed Assets",
            }
        ]
    }
    itc_result = {
        "status": "INELIGIBLE",
        "eligible_itc": 0.0,
        "blocked_itc": 336000.0,
        "reversal_itc": 0.0,
        "review_amount": 0.0,
        "net_itc_available": 0.0,
        "rule_reference": "CGST Act Sec 17(5)(a)",
    }

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting,
        itc_result=itc_result,
    )

    assert journal["status"] == "BALANCED"
    assert journal["total_debit"] == 1536000.0
    assert journal["total_credit"] == 1536000.0

    # Ensure zero Input GST asset lines
    asset_tax_lines = [l for l in journal["lines"] if l["line_type"] == "INPUT_TAX"]
    assert len(asset_tax_lines) == 0

    # Ineligible tax is routed to expense
    blocked_line = next(l for l in journal["lines"] if l["account_id"] == "TAX_BLOCKED")
    assert blocked_line["debit"] == 336000.0
    assert blocked_line["line_type"] == "EXPENSE"


def test_f_tds_withholding_and_net_payable():
    """Test F: TDS withholding creates TDS_PAYABLE credit and reduces Accounts Payable."""
    invoice_data = {
        "invoice_number": "INV-TDS-01",
        "subtotal": 100000.0,
        "tax_total": 18000.0,
        "igst_amount": 18000.0,
        "total_amount": 118000.0,
        "vendor_name": "Audit Firm",
        "line_items": [{"description": "Statutory Audit", "taxable_amount": 100000.0}],
    }
    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_5",
                "approved_account_name": "Audit & Legal Fees",
            }
        ],
        "tds": {
            "applicable": True,
            "tds_applicable": True,
            "is_approved": True,
            "tds_section": "194J",
            "final_tds_amount": 10000.0,  # 10% on 100k
        }
    }
    gst_result = {"supply_type": "INTER_STATE", "calculated": {"igst_amount": 18000.0}}
    itc_result = {"status": "ELIGIBLE", "eligible_itc": 18000.0}

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting,
        gst_result=gst_result,
        itc_result=itc_result,
    )

    assert journal["status"] == "BALANCED"
    assert journal["total_debit"] == 118000.0
    assert journal["total_credit"] == 118000.0

    tds_line = next(l for l in journal["lines"] if l["line_type"] == "TDS_PAYABLE")
    ap_line = next(l for l in journal["lines"] if l["line_type"] == "ACCOUNTS_PAYABLE")

    assert tds_line["credit"] == 10000.0
    assert ap_line["credit"] == 108000.0  # 118,000 - 10,000


def test_g_financial_validation_mismatch_blocks_approval():
    """Test G: Stage 5 Financial Validation MISMATCH blocks approval and flags REVIEW_REQUIRED."""
    invoice_data = {
        "invoice_number": "INV-PHARMA-99",
        "subtotal": 9367123.0,
        "tax_total": 496835.76,
        "total_amount": 10433551.0,
        "line_items": [{"description": "Drug batch", "taxable_amount": 115200.82}],
    }
    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_1",
                "approved_account_name": "Pharma Raw Materials",
            }
        ]
    }
    fin_val = {
        "overall_status": "MISMATCH",
        "errors": ["Line item sum (115200.82) does not equal subtotal (9367123.00)"],
    }

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting,
        financial_validation_result=fin_val,
    )

    assert journal["status"] in ("REVIEW_REQUIRED", "UNBALANCED")
    assert journal["validation"]["balanced"] is False
    assert any("Financial Validation reported discrepancies" in w for w in journal["validation"]["warnings"])


@pytest.mark.asyncio
async def test_approval_rejects_financial_mismatch():
    """Test approval endpoint blocks invoice when financial validation reported MISMATCH."""
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="tenant-1",
        approval_status="PENDING_REVIEW",
        financial_validation_result={"overall_status": "MISMATCH", "errors": ["Sum mismatch"]},
        current_vlm_output={"data": {"total_amount": 1000.0, "line_items": [{"description": "X", "taxable_amount": 100.0}]}},
        current_accounting_output={"accounting": [{"line_index": 1, "approved_account_id": "ACC_1", "approved_account_name": "Exp"}]},
    )

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_res

    user = AuthenticatedUser(
        id=str(uuid.uuid4()),
        email="cfo@tenant-1.com",
        tenant_id="tenant-1",
        role="FINANCE",
    )

    with pytest.raises(HTTPException) as exc_info:
        await approve_invoice(invoice_id=inv_id, current_user=user, db=mock_db)

    assert exc_info.value.status_code == 400
    assert "Stage 5 Financial Validation reported MISMATCH" in exc_info.value.detail


def test_j_shipping_and_other_charges_and_roundoff():
    """Test J: Shipping, other charges, and positive/negative round-off are preserved in General Ledger."""
    invoice_data = {
        "invoice_number": "INV-LOGISTICS-01",
        "subtotal": 1000.0,
        "shipping_charges": 150.0,
        "other_charges": 50.0,
        "round_off": 0.50,
        "tax_total": 180.0,
        "igst_amount": 180.0,
        "total_amount": 1380.50,
        "line_items": [{"description": "Item", "taxable_amount": 1000.0}],
    }
    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_1",
                "approved_account_name": "General Expenses",
            }
        ]
    }
    gst_result = {"supply_type": "INTER_STATE", "calculated": {"igst_amount": 180.0}}
    itc_result = {"status": "ELIGIBLE", "eligible_itc": 180.0}

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting,
        gst_result=gst_result,
        itc_result=itc_result,
    )

    assert journal["status"] == "BALANCED"
    assert journal["total_debit"] == 1380.50
    assert journal["total_credit"] == 1380.50

    line_ids = [l["account_id"] for l in journal["lines"]]
    assert "ACC_12" in line_ids  # Shipping
    assert "EXP_OTHER_CHARGES" in line_ids  # Other charges
    assert "ROUND_OFF" in line_ids  # Round off
