import pytest
from app.services.financial_validator import financial_validator
from app.services.tds_engine import tds_engine
from app.services.journal_generator import journal_generator


def test_financial_validator_math():
    valid_data = {
        "subtotal": 10000.0,
        "tax_total": 1800.0,
        "discount_total": 0.0,
        "shipping_charges": 0.0,
        "other_charges": 0.0,
        "round_off": 0.0,
        "total_amount": 11800.0,
        "line_items": [
            {
                "description": "Cloud Servers",
                "quantity": 1.0,
                "unit_price": 10000.0,
                "taxable_amount": 10000.0,
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
                "total": 11800.0,
            }
        ]
    }
    is_valid, errors, computed = financial_validator.validate_invoice_math(valid_data)
    assert is_valid is True
    assert len(errors) == 0
    assert computed["computed_grand_total"] == 11800.0


def test_financial_validator_supply_type():
    # Same state code: 27 (Maharashtra)
    intra = financial_validator.determine_supply_type("27ABCDE1234F1Z5", "27XYZAB9876K1Z2")
    assert intra == "INTRA_STATE"

    # Different state codes: 27 (MH) vs 29 (KA)
    inter = financial_validator.determine_supply_type("27ABCDE1234F1Z5", "29XYZAB9876K1Z2")
    assert inter == "INTER_STATE"


def test_tds_engine_calculations():
    # Section 194C Company: 2%
    res_194c_comp = tds_engine.calculate_tds(
        section="194C",
        base_amount=100000.0,
        vendor_pan="AABCB1234F",  # 'C' in 4th position -> Company
    )
    assert res_194c_comp["applicable"] is True
    assert res_194c_comp["rate"] == 2.0
    assert res_194c_comp["tds_amount"] == 2000.0

    # Section 194C Individual: 1%
    res_194c_ind = tds_engine.calculate_tds(
        section="194C",
        base_amount=100000.0,
        vendor_pan="AABPB1234F",  # 'P' in 4th position -> Individual
    )
    assert res_194c_ind["rate"] == 1.0
    assert res_194c_ind["tds_amount"] == 1000.0

    # Section 194J FTS: 2%
    res_194j = tds_engine.calculate_tds(
        section="194J",
        base_amount=50000.0,
        vendor_pan="AABCB1234F",
        is_tech_service=True,
    )
    assert res_194j["rate"] == 2.0
    assert res_194j["tds_amount"] == 1000.0

    # Invalid PAN -> Section 206AA 20% penalty
    res_invalid_pan = tds_engine.calculate_tds(
        section="194J",
        base_amount=50000.0,
        vendor_pan="INVALID_PAN",
    )
    assert res_invalid_pan["rate"] == 20.0
    assert res_invalid_pan["tds_amount"] == 10000.0


def test_journal_generator_balance():
    invoice_data = {
        "invoice_number": "INV-101",
        "invoice_date": "2026-08-20",
        "vendor_name": "Acme Cloud Services",
        "vendor_gstin": "27AABCA1234F1Z5",
        "customer_gstin": "27XYZAB9876K1Z2",
        "vendor_pan": "AABCA1234F",
        "subtotal": 100000.0,
        "cgst_amount": 9000.0,
        "sgst_amount": 9000.0,
        "total_amount": 118000.0,
        "line_items": [
            {
                "description": "Enterprise Cloud Hosting",
                "taxable_amount": 100000.0,
                "cgst_amount": 9000.0,
                "sgst_amount": 9000.0,
                "total": 118000.0,
            }
        ]
    }

    accounting_data = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_1",
                "approved_account_name": "Cloud Hosting & Infrastructure",
            }
        ],
        "tds": {
            "applicable": True,
            "tds_section": "194J",
            "calculated_tds_amount": 2000.0,
        }
    }

    journal = journal_generator.generate_journal_entry(
        invoice_data=invoice_data,
        accounting_data=accounting_data,
        require_approved=True,
    )

    assert journal["is_balanced"] is True
    assert journal["supply_type"] == "INTRA_STATE"
    assert journal["total_debit"] == 118000.0
    assert journal["total_credit"] == 118000.0

    lines = journal["lines"]
    dr_lines = [l for l in lines if l["line_type"] == "DR"]
    cr_lines = [l for l in lines if l["line_type"] == "CR"]

    # Verify line accounts
    assert len(dr_lines) == 3  # Expense (100k) + Input CGST (9k) + Input SGST (9k)
    assert len(cr_lines) == 2  # TDS Payable (2k) + Accounts Payable (116k)

    ap_line = next(l for l in cr_lines if l["account_id"] == "AP_VENDOR")
    assert ap_line["amount"] == 116000.0  # 118,000 - 2,000 TDS
