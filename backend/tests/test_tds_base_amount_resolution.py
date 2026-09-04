import pytest
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.tds_engine import tds_engine, get_effective_tds_data
from app.services.journal_generator import journal_generator
from app.db.models import Invoice, JournalEntry, ZohoConnection, TaxRate


def test_tds_base_amount_resolution_hierarchy():
    """
    Verifies determine_tds_base_amount:
    1. Line items with taxable_amount take precedence when available.
    2. Subtotal is used only as fallback if line items lack taxable amount.
    3. User/proposal approved base amount takes precedence if explicitly passed.
    """
    # Case 1: Line items present with specific taxable amount
    invoice_data_lines = {
        "subtotal": 150000.0,
        "total_amount": 177000.0,
        "line_items": [
            {"description": "Consulting service", "taxable_amount": 100000.0},
            {"description": "Hardware purchase", "taxable_amount": 50000.0},
        ],
    }
    # If no explicit proposed base amount, sums line items
    base_amt = tds_engine.determine_tds_base_amount(invoice_data_lines)
    assert base_amt == 150000.0

    # Case 2: Explicit proposed or approved base amount (e.g. partial contract eligible)
    tds_proposal_custom = {
        "tds_applicable": True,
        "tds_base_amount": 100000.0,
        "tds_rate": 10.0,
    }
    base_amt_custom = tds_engine.determine_tds_base_amount(invoice_data_lines, tds_proposal=tds_proposal_custom)
    assert base_amt_custom == 100000.0

    # Case 3: Calculation strictly yields Base Amount * Rate
    calc_result = tds_engine.calculate_tds(
        base_amount=base_amt_custom,
        section="194J",
        rate=10.0,
    )
    assert calc_result["base_amount"] == 100000.0
    assert calc_result["rate"] == 10.0
    assert calc_result["tds_amount"] == 10000.0
    assert "₹100,000.00" in calc_result["reason"]
    assert "subtotal" not in calc_result["reason"].lower()


def test_tds_base_amount_journal_consistency():
    """
    Verifies that journal entry correctly reflects:
    - Base Amount != subtotal if specified
    - TDS Payable = Base Amount * Rate
    - Net AP Payable = Gross Total - TDS Amount
    """
    invoice_data = {
        "vendor_name": "Acme Tech Advisory",
        "subtotal": 200000.0,
        "total_amount": 236000.0,
        "line_items": [
            {"description": "Tech Advisory Service", "taxable_amount": 200000.0},
        ],
    }
    gst_result = {
        "supply_type": "INTRA_STATE",
        "calculated": {"cgst_amount": 18000.0, "sgst_amount": 18000.0},
    }

    # Suppose only 120,000 is eligible under 194J
    accounting_custom_base = {
        "accounting": [
            {"line_index": 1, "account_id": "ACC_EXP_01", "account_name": "Consulting Fees", "debit": 200000.0}
        ],
        "tds_assessment": {
            "tds_applicable": True,
            "tds_section": "194J",
            "tds_rate": 10.0,
            "tds_base_amount": 120000.0,
            "is_approved": True,
        },
    }

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting_custom_base,
        gst_result=gst_result,
    )

    tds_lines = [l for l in journal["lines"] if l.get("line_type") == "TDS_PAYABLE"]
    assert len(tds_lines) == 1
    # 10% of 120,000 = 12,000 (NOT 10% of 200,000)
    assert tds_lines[0]["credit"] == 12000.0

    ap_lines = [l for l in journal["lines"] if l.get("line_type") == "ACCOUNTS_PAYABLE"]
    assert len(ap_lines) == 1
    # Total 236,000 - 12,000 TDS = 224,000 AP
    assert ap_lines[0]["credit"] == 224000.0
    assert journal["validation"]["balanced"] is True


def test_effective_tds_data_extracts_base_amount():
    """
    Verifies that get_effective_tds_data correctly extracts tds_base_amount.
    """
    payload = {
        "tds_assessment": {
            "tds_applicable": True,
            "tds_section": "194C",
            "tds_rate": 2.0,
            "tds_base_amount": 54000.0,
            "nature_of_payment": "Contractor work",
        }
    }
    eff = get_effective_tds_data(payload)
    assert eff["applicable"] is True
    assert eff["rate"] == 2.0
    assert eff["tds_base_amount"] == 54000.0
