import pytest
import copy
from app.services.journal_generator import (
    JournalGenerator,
    journal_generator,
    STANDARD_ACCOUNTS,
)


def test_1_simple_expense_invoice_balances():
    """Valid intra-state invoice with single line item produces balanced journal."""
    invoice_data = {
        "subtotal": 10000.0,
        "tax_total": 1800.0,
        "total_amount": 11800.0,
        "cgst_amount": 900.0,
        "sgst_amount": 900.0,
        "vendor_name": "Acme Supplies",
        "line_items": [
            {
                "description": "Office Stationery",
                "taxable_amount": 10000.0,
            }
        ],
    }
    accounting = {
        "accounting": [
            {
                "line_index": 0,
                "ai_account_id": "ACC_3",
                "ai_account_name": "Office Supplies & Stationery",
            }
        ]
    }
    gst_result = {
        "supply_type": "INTRA_STATE",
        "validation_status": "PASSED",
        "calculated": {"cgst_amount": 900.0, "sgst_amount": 900.0, "gst_total": 1800.0},
    }
    itc_result = {
        "status": "ELIGIBLE",
        "eligible_amount": 1800.0,
        "ineligible_amount": 0.0,
    }
    fin_val = {"overall_status": "PASSED"}

    res = journal_generator.generate_journal(
        invoice_data, accounting, gst_result, itc_result, None, fin_val
    )

    assert res["status"] == "BALANCED"
    assert res["total_debit"] == 11800.0
    assert res["total_credit"] == 11800.0
    assert res["difference"] == 0.0
    assert res["validation"]["balanced"] is True
    assert len(res["lines"]) == 4  # 1 expense, 1 CGST, 1 SGST, 1 AP


def test_2_multiple_coa_expense_accounts():
    """Invoice with multiple lines maps each to its respective COA account."""
    invoice_data = {
        "subtotal": 25000.0,
        "tax_total": 4500.0,
        "total_amount": 29500.0,
        "igst_amount": 4500.0,
        "vendor_name": "Multi Vendor",
        "line_items": [
            {"description": "Paper", "taxable_amount": 5000.0},
            {"description": "Consulting", "taxable_amount": 20000.0},
        ],
    }
    accounting = {
        "accounting": [
            {"line_index": 0, "ai_account_id": "ACC_3", "ai_account_name": "Office Supplies & Stationery"},
            {"line_index": 1, "ai_account_id": "ACC_5", "ai_account_name": "Consulting & Technical Services"},
        ]
    }
    gst_result = {
        "supply_type": "INTER_STATE",
        "validation_status": "PASSED",
        "calculated": {"igst_amount": 4500.0, "gst_total": 4500.0},
    }
    itc_result = {"status": "ELIGIBLE", "eligible_amount": 4500.0}
    fin_val = {"overall_status": "PASSED"}

    res = journal_generator.generate_journal(
        invoice_data, accounting, gst_result, itc_result, None, fin_val
    )

    assert res["status"] == "BALANCED"
    account_ids = [l["account_id"] for l in res["lines"]]
    assert "ACC_3" in account_ids
    assert "ACC_5" in account_ids
    assert "TAX_INP_IGST" in account_ids
    assert "LIAB_AP" in account_ids


def test_3_cgst_plus_sgst_journal():
    """Intra-state supply creates separate Input CGST and Input SGST debits."""
    invoice_data = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "total_amount": 1180.0,
        "line_items": [{"description": "Item", "taxable_amount": 1000.0}],
    }
    accounting = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_1", "ai_account_name": "Cloud Hosting"}]}
    gst_result = {
        "supply_type": "INTRA_STATE",
        "validation_status": "PASSED",
        "calculated": {"cgst_amount": 90.0, "sgst_amount": 90.0},
    }
    itc_result = {"status": "ELIGIBLE", "eligible_amount": 180.0}

    res = journal_generator.generate_journal(invoice_data, accounting, gst_result, itc_result)

    cgst_lines = [l for l in res["lines"] if l["account_id"] == "TAX_INP_CGST"]
    sgst_lines = [l for l in res["lines"] if l["account_id"] == "TAX_INP_SGST"]
    assert len(cgst_lines) == 1 and cgst_lines[0]["debit"] == 90.0
    assert len(sgst_lines) == 1 and sgst_lines[0]["debit"] == 90.0


def test_4_igst_journal():
    """Inter-state supply creates Input IGST debit."""
    invoice_data = {
        "subtotal": 1000.0,
        "igst_amount": 180.0,
        "total_amount": 1180.0,
        "line_items": [{"description": "Item", "taxable_amount": 1000.0}],
    }
    accounting = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_1", "ai_account_name": "Cloud Hosting"}]}
    gst_result = {
        "supply_type": "INTER_STATE",
        "validation_status": "PASSED",
        "calculated": {"igst_amount": 180.0},
    }
    itc_result = {"status": "ELIGIBLE", "eligible_amount": 180.0}

    res = journal_generator.generate_journal(invoice_data, accounting, gst_result, itc_result)

    igst_lines = [l for l in res["lines"] if l["account_id"] == "TAX_INP_IGST"]
    assert len(igst_lines) == 1 and igst_lines[0]["debit"] == 180.0
    assert len([l for l in res["lines"] if l["account_id"] == "TAX_INP_CGST"]) == 0


def test_5_eligible_itc():
    """Eligible ITC creates INPUT_TAX lines."""
    invoice_data = {
        "subtotal": 5000.0,
        "cgst_amount": 450.0,
        "sgst_amount": 450.0,
        "total_amount": 5900.0,
        "line_items": [{"description": "Laptops", "taxable_amount": 5000.0}],
    }
    accounting = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_6", "ai_account_name": "Hardware & Equipment"}]}
    itc_result = {"status": "ELIGIBLE", "eligible_amount": 900.0, "ineligible_amount": 0.0}

    res = journal_generator.generate_journal(invoice_data, accounting, None, itc_result)
    input_tax_lines = [l for l in res["lines"] if l["line_type"] == "INPUT_TAX"]
    assert len(input_tax_lines) == 2
    assert sum(l["debit"] for l in input_tax_lines) == 900.0


def test_6_blocked_itc_routed_to_ineligible_expense():
    """Ineligible/Blocked ITC under Sec 17(5) routes tax to Ineligible Tax Expense and NOT Input Tax."""
    invoice_data = {
        "subtotal": 5000.0,
        "cgst_amount": 250.0,
        "sgst_amount": 250.0,
        "total_amount": 5500.0,
        "line_items": [{"description": "Food & Beverages for Office Party", "taxable_amount": 5000.0}],
    }
    accounting = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_3", "ai_account_name": "Office Supplies"}]}
    itc_result = {
        "status": "INELIGIBLE",
        "eligible_amount": 0.0,
        "ineligible_amount": 500.0,
        "rule_reference": "CGST Sec 17(5)(b)(i)",
    }

    res = journal_generator.generate_journal(invoice_data, accounting, None, itc_result)

    input_tax_lines = [l for l in res["lines"] if l["line_type"] == "INPUT_TAX"]
    assert len(input_tax_lines) == 0  # No eligible input tax!

    blocked_lines = [l for l in res["lines"] if l["account_id"] == "TAX_BLOCKED"]
    assert len(blocked_lines) == 1
    assert blocked_lines[0]["debit"] == 500.0
    assert res["total_debit"] == 5500.0
    assert res["total_credit"] == 5500.0
    assert res["status"] == "BALANCED"


def test_7_tds_payable_created():
    """Approved TDS creates TDS Payable credit line."""
    invoice_data = {
        "subtotal": 10000.0,
        "tax_total": 1800.0,
        "total_amount": 11800.0,
        "cgst_amount": 900.0,
        "sgst_amount": 900.0,
        "line_items": [{"description": "Professional Consulting", "taxable_amount": 10000.0}],
    }
    accounting = {
        "accounting": [{"line_index": 0, "ai_account_id": "ACC_4", "ai_account_name": "Professional & Legal Fees"}],
        "tds": {
            "tds_applicable": True,
            "final_tds_amount": 1000.0,
            "tds_section": "194J",
            "is_approved": True,
        },
    }

    res = journal_generator.generate_journal(invoice_data, accounting)

    tds_lines = [l for l in res["lines"] if l["line_type"] == "TDS_PAYABLE"]
    assert len(tds_lines) == 1
    assert tds_lines[0]["credit"] == 1000.0
    assert tds_lines[0]["account_id"] == "LIAB_TDS_PAYABLE"


def test_8_accounts_payable_reduced_by_tds():
    """Vendor liability is Gross Total - TDS Withholding."""
    invoice_data = {
        "subtotal": 10000.0,
        "tax_total": 1800.0,
        "total_amount": 11800.0,
        "cgst_amount": 900.0,
        "sgst_amount": 900.0,
        "line_items": [{"description": "Legal Services", "taxable_amount": 10000.0}],
    }
    accounting = {
        "accounting": [{"line_index": 0, "ai_account_id": "ACC_4", "ai_account_name": "Professional & Legal Fees"}],
        "tds": {
            "tds_applicable": True,
            "final_tds_amount": 1000.0,
            "tds_section": "194J",
            "is_approved": True,
        },
    }

    res = journal_generator.generate_journal(invoice_data, accounting)

    ap_lines = [l for l in res["lines"] if l["line_type"] == "ACCOUNTS_PAYABLE"]
    assert len(ap_lines) == 1
    assert ap_lines[0]["credit"] == 10800.0  # 11,800 - 1,000

    # Total credits = AP (10,800) + TDS (1,000) = 11,800
    assert res["total_credit"] == 11800.0
    assert res["status"] == "BALANCED"


def test_9_no_tds_when_not_applicable():
    """Invoice without TDS sets full Gross Amount to Accounts Payable."""
    invoice_data = {
        "subtotal": 5000.0,
        "tax_total": 900.0,
        "total_amount": 5900.0,
        "line_items": [{"description": "Goods", "taxable_amount": 5000.0}],
    }
    accounting = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_3", "ai_account_name": "Office Supplies"}]}

    res = journal_generator.generate_journal(invoice_data, accounting)

    tds_lines = [l for l in res["lines"] if l["line_type"] == "TDS_PAYABLE"]
    assert len(tds_lines) == 0
    ap_lines = [l for l in res["lines"] if l["line_type"] == "ACCOUNTS_PAYABLE"]
    assert ap_lines[0]["credit"] == 5900.0


def test_10_round_off_treatment():
    """Round-off adjustments are balanced via dedicated ROUND_OFF lines."""
    # Positive round off
    inv_pos = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "round_off": 0.40,
        "total_amount": 1180.40,
        "line_items": [{"description": "Goods", "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0}],
    }
    acc = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_1", "ai_account_name": "Cloud"}]}
    res_pos = journal_generator.generate_journal(inv_pos, acc)
    assert res_pos["total_debit"] == 1180.40
    assert res_pos["total_credit"] == 1180.40
    assert res_pos["status"] == "BALANCED"

    # Negative round off
    inv_neg = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "round_off": -0.40,
        "total_amount": 1179.60,
        "line_items": [{"description": "Goods", "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0}],
    }
    res_neg = journal_generator.generate_journal(inv_neg, acc)
    assert res_neg["total_debit"] == 1180.00
    assert res_neg["total_credit"] == 1180.00
    assert res_neg["status"] == "BALANCED"


def test_11_discount_treatment():
    """Invoice with line discounts reflects net taxable amount in expense debits."""
    invoice_data = {
        "subtotal": 900.0,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1062.0,
        "line_items": [
            {"description": "Item with discount", "quantity": 10, "unit_price": 100.0, "discount": 100.0, "taxable_amount": 900.0, "cgst_amount": 81.0, "sgst_amount": 81.0}
        ],
    }
    acc = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_3", "ai_account_name": "Office Supplies"}]}

    res = journal_generator.generate_journal(invoice_data, acc)
    assert res["lines"][0]["debit"] == 900.0
    assert res["total_debit"] == 1062.0
    assert res["total_credit"] == 1062.0
    assert res["status"] == "BALANCED"


def test_12_shipping_and_other_charges():
    """Shipping charges and other charges create corresponding expense debit entries."""
    invoice_data = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "shipping_charges": 150.0,
        "other_charges": 50.0,
        "total_amount": 1380.0,
        "line_items": [{"description": "Hardware", "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0}],
    }
    acc = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_6", "ai_account_name": "Hardware"}]}

    res = journal_generator.generate_journal(invoice_data, acc)
    assert any(l["account_id"] == "ACC_12" and l["debit"] == 150.0 for l in res["lines"])
    assert any(l["account_id"] == "EXP_OTHER_CHARGES" and l["debit"] == 50.0 for l in res["lines"])
    assert res["total_debit"] == 1380.0
    assert res["total_credit"] == 1380.0
    assert res["status"] == "BALANCED"


def test_13_gst_mismatch_sets_review_required():
    """GST validation failure sets journal status to REVIEW_REQUIRED."""
    invoice_data = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "total_amount": 1180.0,
        "line_items": [{"description": "Item", "taxable_amount": 1000.0}],
    }
    acc = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_1", "ai_account_name": "Cloud"}]}
    gst_result = {
        "supply_type": "INTER_STATE",
        "validation_status": "GST_MISMATCH",
        "errors": ["Inter-State transaction cannot charge CGST/SGST"],
    }

    res = journal_generator.generate_journal(invoice_data, acc, gst_result=gst_result)
    assert res["status"] == "REVIEW_REQUIRED"
    assert any("GST Engine reported GST_MISMATCH" in w for w in res["validation"]["warnings"])


def test_14_financial_validation_mismatch_sets_review_required():
    """Stage 5 financial discrepancy sets journal status to REVIEW_REQUIRED."""
    invoice_data = {
        "subtotal": 4900.0,
        "tax_total": 888.0,
        "total_amount": 5788.0,
        "line_items": [{"description": "Items", "taxable_amount": 4900.0}],
    }
    acc = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_3", "ai_account_name": "Office Supplies"}]}
    fin_val = {
        "overall_status": "MISMATCH",
        "errors": ["GST components sum (₹882.00) does not match extracted Tax Total (₹888.00)"],
    }

    res = journal_generator.generate_journal(invoice_data, acc, financial_validation_result=fin_val)
    assert res["status"] == "REVIEW_REQUIRED"


def test_15_missing_coa_account_sets_review_required():
    """Line without resolved COA classification triggers REVIEW_REQUIRED."""
    invoice_data = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "total_amount": 1180.0,
        "line_items": [{"description": "Mystery Item", "taxable_amount": 1000.0}],
    }
    accounting = {"accounting": []}  # No accounts provided!

    res = journal_generator.generate_journal(invoice_data, accounting)
    assert res["status"] == "REVIEW_REQUIRED"
    assert any("Missing COA account classification" in e for e in res["validation"]["errors"])


def test_16_unapproved_tds_triggers_review_required():
    """Proposed TDS without explicit approval sets REVIEW_REQUIRED."""
    invoice_data = {
        "subtotal": 10000.0,
        "tax_total": 1800.0,
        "total_amount": 11800.0,
        "line_items": [{"description": "Consulting", "taxable_amount": 10000.0}],
    }
    accounting = {
        "accounting": [{"line_index": 0, "ai_account_id": "ACC_5", "ai_account_name": "Consulting"}],
        "tds": {
            "tds_applicable": True,
            "final_tds_amount": 1000.0,
            "is_approved": False,
        },
    }

    res = journal_generator.generate_journal(invoice_data, accounting)
    assert res["status"] == "REVIEW_REQUIRED"
    assert any("Proposed TDS requires finance approval" in w for w in res["validation"]["warnings"])


def test_17_balanced_journal_flag():
    """Mathematically equal debits and credits produce balanced=True."""
    invoice_data = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "total_amount": 1180.0,
        "line_items": [{"description": "Item", "taxable_amount": 1000.0}],
    }
    acc = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_1", "ai_account_name": "Cloud"}]}
    res = journal_generator.generate_journal(invoice_data, acc)
    assert res["validation"]["balanced"] is True
    assert res["difference"] == 0.0


def test_18_unbalanced_journal_flag():
    """Severely inconsistent line items vs total produce UNBALANCED."""
    invoice_data = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "total_amount": 5000.0,  # Arbitrary total that does not equal debits
        "line_items": [{"description": "Item", "taxable_amount": 1000.0}],
    }
    acc = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_1", "ai_account_name": "Cloud"}]}
    res = journal_generator.generate_journal(invoice_data, acc)
    assert res["validation"]["balanced"] is False
    assert res["status"] == "UNBALANCED"


def test_19_no_fake_balancing_line():
    """Generator never adds a fake dummy balancing line."""
    invoice_data = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "total_amount": 2000.0,  # 820 mismatch
        "line_items": [{"description": "Item", "taxable_amount": 1000.0}],
    }
    acc = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_1", "ai_account_name": "Cloud"}]}
    res = journal_generator.generate_journal(invoice_data, acc)
    line_names = [l["account_name"] for l in res["lines"]]
    assert "Balancing Account" not in line_names
    assert "Suspense" not in line_names
    assert res["difference"] != 0.0


def test_20_customer_edit_regenerates_journal():
    """Changing invoice amount updates debit/credit figures in regenerated journal."""
    invoice_v1 = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "total_amount": 1180.0,
        "line_items": [{"description": "Item", "taxable_amount": 1000.0}],
    }
    acc = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_1", "ai_account_name": "Cloud"}]}
    res_v1 = journal_generator.generate_journal(invoice_v1, acc)

    invoice_v2 = {
        "subtotal": 2000.0,
        "tax_total": 360.0,
        "total_amount": 2360.0,
        "line_items": [{"description": "Item", "taxable_amount": 2000.0}],
    }
    res_v2 = journal_generator.generate_journal(invoice_v2, acc)

    assert res_v1["total_debit"] == 1180.0
    assert res_v2["total_debit"] == 2360.0


def test_21_journal_rerun_is_idempotent():
    """Running journal generation repeatedly on same data returns identical result."""
    invoice_data = {
        "subtotal": 15000.0,
        "tax_total": 2700.0,
        "total_amount": 17700.0,
        "line_items": [{"description": "Stationery", "taxable_amount": 15000.0}],
    }
    acc = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_3", "ai_account_name": "Office Supplies"}]}

    res1 = journal_generator.generate_journal(invoice_data, acc)
    res2 = journal_generator.generate_journal(invoice_data, acc)

    assert res1 == res2


def test_22_raw_vlm_data_preserved():
    """Input dictionaries are never mutated by the journal generator."""
    original_inv = {
        "subtotal": 10000.0,
        "tax_total": 1800.0,
        "total_amount": 11800.0,
        "line_items": [{"description": "Software", "taxable_amount": 10000.0}],
    }
    copy_inv = copy.deepcopy(original_inv)
    acc = {"accounting": [{"line_index": 0, "ai_account_id": "ACC_2", "ai_account_name": "Software"}]}

    journal_generator.generate_journal(original_inv, acc)
    assert original_inv == copy_inv


def test_23_ai_vs_finance_account_provenance_preserved():
    """Final account override sets provenance to HITL_OVERRIDE while AI default uses AI_PREDICTED."""
    invoice_data = {
        "subtotal": 10000.0,
        "tax_total": 1800.0,
        "total_amount": 11800.0,
        "line_items": [
            {"description": "Item 1", "taxable_amount": 5000.0},
            {"description": "Item 2", "taxable_amount": 5000.0},
        ],
    }
    # Line 0 has finance override, Line 1 has AI prediction only
    accounting = {
        "accounting": [
            {
                "line_index": 0,
                "ai_account_id": "ACC_1",
                "ai_account_name": "Cloud",
                "final_account_id": "ACC_2",
                "final_account_name": "Software & Subscription",
            },
            {
                "line_index": 1,
                "ai_account_id": "ACC_3",
                "ai_account_name": "Office Supplies",
            },
        ]
    }

    res = journal_generator.generate_journal(invoice_data, accounting)

    assert res["lines"][0]["account_id"] == "ACC_2"
    assert res["lines"][0]["provenance"] == "HITL_OVERRIDE"

    assert res["lines"][1]["account_id"] == "ACC_3"
    assert res["lines"][1]["provenance"] == "AI_PREDICTED"
