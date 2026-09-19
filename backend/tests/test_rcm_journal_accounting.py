"""
Comprehensive Test Suite for P0 #4 — RCM Journal / Accounting Integration.
Validates authoritative General Ledger journal generation for Reverse Charge Mechanism (RCM):
- Forward charge remains untouched
- RCM GST is NOT added to vendor payable
- Recipient RCM GST liability is separately credited (CGST+SGST or IGST)
- RCM + TDS interaction (TDS calculated on pretax base, separate lines)
- Input Tax Credit (ITC) handling under RCM (pending cash discharge under Sec 16(2))
- Blocked ITC under Sec 17(5) debited to TAX_BLOCKED expense
- Review-required ITC preserved
- Strict double-entry balance: total_debits == total_credits across all scenarios
"""

import pytest
from app.services.journal_generator import journal_generator
from app.services.gst_engine import gst_engine


def test_1_normal_forward_charge_invoice_unchanged():
    """1. Normal forward-charge invoice: Existing journal behavior remains 100% unchanged."""
    invoice_data = {
        "invoice_number": "INV-FWD-01",
        "subtotal": 100000.0,
        "tax_total": 18000.0,
        "cgst_amount": 9000.0,
        "sgst_amount": 9000.0,
        "total_amount": 118000.0,
        "vendor_name": "Standard Vendor",
        "line_items": [{"description": "Commercial Consulting", "taxable_amount": 100000.0}],
    }
    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_EXP_1",
                "approved_account_name": "Consulting Services",
            }
        ]
    }
    gst_result = {
        "is_reverse_charge": False,
        "supply_type": "INTRA_STATE",
        "validation_status": "PASSED",
        "calculated": {"cgst_amount": 9000.0, "sgst_amount": 9000.0, "gst_total": 18000.0},
    }
    itc_result = {"status": "ELIGIBLE", "eligible_itc": 18000.0}

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting,
        gst_result=gst_result,
        itc_result=itc_result,
    )

    assert journal["status"] == "BALANCED"
    assert journal["validation"]["balanced"] is True
    assert journal["total_debit"] == 118000.0
    assert journal["total_credit"] == 118000.0

    lines = {l["account_id"]: l for l in journal["lines"]}
    # Asset input tax
    assert "TAX_INP_CGST" in lines
    assert "TAX_INP_SGST" in lines
    assert lines["TAX_INP_CGST"]["debit"] == 9000.0
    assert lines["TAX_INP_SGST"]["debit"] == 9000.0

    # Vendor payable includes GST in forward charge
    assert lines["LIAB_AP"]["credit"] == 118000.0

    # No RCM liability lines
    assert "LIAB_RCM_CGST" not in lines
    assert "LIAB_RCM_SGST" not in lines
    assert "LIAB_RCM_IGST" not in lines


def test_2_rcm_invoice_separate_rcm_gst_liability_exists():
    """2. RCM invoice: Separate RCM GST liability credit lines exist."""
    invoice_data = {
        "invoice_number": "INV-RCM-01",
        "subtotal": 100000.0,
        "tax_total": 18000.0,
        "cgst_amount": 9000.0,
        "sgst_amount": 9000.0,
        "total_amount": 118000.0,
        "vendor_name": "Advocate Ramesh",
        "line_items": [{"description": "Legal Representation", "taxable_amount": 100000.0}],
    }
    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_LEGAL",
                "approved_account_name": "Legal & Professional Fees",
            }
        ]
    }
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "LEGAL_SERVICES",
        "rcm_notification": "Notification No. 13/2017-Central Tax (Rate) Entry 2",
        "supply_type": "INTRA_STATE",
        "validation_status": "PASSED",
        "calculated": {"cgst_amount": 9000.0, "sgst_amount": 9000.0, "gst_total": 18000.0},
    }
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

    lines = {l["account_id"]: l for l in journal["lines"]}
    assert "LIAB_RCM_CGST" in lines
    assert "LIAB_RCM_SGST" in lines
    assert lines["LIAB_RCM_CGST"]["credit"] == 9000.0
    assert lines["LIAB_RCM_SGST"]["credit"] == 9000.0


def test_3_rcm_invoice_rcm_gst_not_added_to_vendor_payable():
    """3. RCM invoice: RCM GST is NOT added to vendor payable."""
    invoice_data = {
        "invoice_number": "INV-RCM-02",
        "subtotal": 100000.0,
        "tax_total": 18000.0,
        "cgst_amount": 9000.0,
        "sgst_amount": 9000.0,
        "total_amount": 118000.0,  # printed total has 118k
        "vendor_name": "Advocate Ramesh",
        "line_items": [{"description": "Legal Representation", "taxable_amount": 100000.0}],
    }
    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_LEGAL",
                "approved_account_name": "Legal Fees",
            }
        ]
    }
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "LEGAL_SERVICES",
        "rcm_notification": "Notification No. 13/2017-CT(R) Entry 2",
        "supply_type": "INTRA_STATE",
        "calculated": {"cgst_amount": 9000.0, "sgst_amount": 9000.0, "gst_total": 18000.0},
    }

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting,
        gst_result=gst_result,
    )

    lines = {l["account_id"]: l for l in journal["lines"]}
    # Vendor payable is strictly 100,000, NOT 118,000!
    assert lines["LIAB_AP"]["credit"] == 100000.0


def test_4_rcm_with_tds():
    """4. RCM + TDS: Vendor payable, TDS payable, and RCM GST liability are separately represented."""
    invoice_data = {
        "invoice_number": "INV-RCM-TDS-01",
        "subtotal": 100000.0,
        "tax_total": 18000.0,
        "cgst_amount": 9000.0,
        "sgst_amount": 9000.0,
        "total_amount": 118000.0,
        "vendor_name": "Lex Associates",
        "line_items": [{"description": "High Court Litigation", "taxable_amount": 100000.0}],
    }
    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_LEGAL",
                "approved_account_name": "Legal Fees",
            }
        ],
        "tds": {
            "applicable": True,
            "is_approved": True,
            "tds_section": "194J",
            "tds_rate": 10.0,
            "final_tds_amount": 10000.0,  # 10% on 100k
        },
    }
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "LEGAL_SERVICES",
        "rcm_notification": "Notification No. 13/2017-CT(R) Entry 2",
        "supply_type": "INTRA_STATE",
        "calculated": {"cgst_amount": 9000.0, "sgst_amount": 9000.0, "gst_total": 18000.0},
    }
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

    lines = {l["account_id"]: l for l in journal["lines"]}
    # Vendor payable = 100,000 (taxable) - 10,000 (TDS) = 90,000
    assert lines["LIAB_AP"]["credit"] == 90000.0
    # TDS payable = 10,000
    assert lines["LIAB_TDS_PAYABLE"]["credit"] == 10000.0
    # RCM liabilities = 9,000 + 9,000 = 18,000
    assert lines["LIAB_RCM_CGST"]["credit"] == 9000.0
    assert lines["LIAB_RCM_SGST"]["credit"] == 9000.0


def test_5_rcm_with_eligible_itc_not_prematurely_claimed():
    """5. RCM + eligible ITC: Not booked as immediate claimable asset before cash discharge; preserved in pending/deferred state."""
    invoice_data = {
        "invoice_number": "INV-RCM-ITC-01",
        "subtotal": 50000.0,
        "tax_total": 9000.0,
        "igst_amount": 9000.0,
        "total_amount": 50000.0,
        "vendor_name": "Security Agency",
        "line_items": [{"description": "Security Guards", "taxable_amount": 50000.0}],
    }
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "SECURITY_SERVICES",
        "rcm_notification": "Notification No. 13/2017-CT(R) Entry 14",
        "supply_type": "INTER_STATE",
        "calculated": {"igst_amount": 9000.0, "gst_total": 9000.0},
    }
    itc_result = {"status": "ELIGIBLE", "eligible_itc": 9000.0}

    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_SEC",
                "approved_account_name": "Security Charges",
            }
        ]
    }

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting,
        gst_result=gst_result,
        itc_result=itc_result,
    )

    assert journal["status"] == "BALANCED"
    lines = {l["account_id"]: l for l in journal["lines"]}

    # No immediate TAX_INP_IGST asset line
    assert "TAX_INP_IGST" not in lines

    # Booked to TAX_RCM_PENDING (Input GST Pending Cash Discharge under RCM)
    assert "TAX_RCM_PENDING" in lines
    assert lines["TAX_RCM_PENDING"]["debit"] == 9000.0
    assert "Sec 16(2)" in lines["TAX_RCM_PENDING"]["description"]


def test_6_rcm_with_blocked_itc():
    """6. RCM + blocked ITC: No input tax asset is created; debited to TAX_BLOCKED expense."""
    invoice_data = {
        "invoice_number": "INV-RCM-BLOCKED",
        "subtotal": 20000.0,
        "tax_total": 3600.0,
        "igst_amount": 3600.0,
        "total_amount": 20000.0,
        "vendor_name": "Cab Service Provider",
        "line_items": [{"description": "Renting of Motor Vehicle", "taxable_amount": 20000.0}],
    }
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "RENTING_MOTOR_VEHICLE",
        "rcm_notification": "Notification No. 13/2017-CT(R) Entry 15",
        "supply_type": "INTER_STATE",
        "calculated": {"igst_amount": 3600.0, "gst_total": 3600.0},
    }
    itc_result = {
        "status": "INELIGIBLE",
        "eligible_itc": 0.0,
        "blocked_itc": 3600.0,
        "rule_reference": "CGST Act Sec 17(5)(a)",
    }

    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_TRAVEL",
                "approved_account_name": "Travel & Conveyance",
            }
        ]
    }

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting,
        gst_result=gst_result,
        itc_result=itc_result,
    )

    assert journal["status"] == "BALANCED"
    lines = {l["account_id"]: l for l in journal["lines"]}

    # Zero input tax assets
    assert "TAX_INP_IGST" not in lines
    assert "TAX_RCM_PENDING" not in lines

    # Debited to TAX_BLOCKED expense
    assert "TAX_BLOCKED" in lines
    assert lines["TAX_BLOCKED"]["debit"] == 3600.0
    assert lines["TAX_BLOCKED"]["line_type"] == "EXPENSE"

    # RCM IGST liability credit
    assert lines["LIAB_RCM_IGST"]["credit"] == 3600.0
    assert lines["LIAB_AP"]["credit"] == 20000.0


def test_7_rcm_with_itc_review_required():
    """7. RCM + ITC REVIEW_REQUIRED: No premature ITC asset, preserved in review state."""
    invoice_data = {
        "invoice_number": "INV-RCM-REV",
        "subtotal": 30000.0,
        "tax_total": 5400.0,
        "cgst_amount": 2700.0,
        "sgst_amount": 2700.0,
        "total_amount": 30000.0,
        "vendor_name": "Sponsorship Agency",
        "line_items": [{"description": "Sponsorship Event", "taxable_amount": 30000.0}],
    }
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "SPONSORSHIP",
        "supply_type": "INTRA_STATE",
        "calculated": {"cgst_amount": 2700.0, "sgst_amount": 2700.0, "gst_total": 5400.0},
    }
    itc_result = {
        "status": "REVIEW_REQUIRED",
        "eligible_itc": 0.0,
        "blocked_itc": 0.0,
        "review_amount": 5400.0,
    }

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        gst_result=gst_result,
        itc_result=itc_result,
    )

    assert journal["status"] == "REVIEW_REQUIRED"
    assert journal["validation"]["balanced"] is True
    lines = {l["account_id"]: l for l in journal["lines"]}

    # No premature asset
    assert "TAX_INP_CGST" not in lines
    assert "TAX_INP_SGST" not in lines
    assert "TAX_RCM_PENDING" not in lines

    # Debited to pending verification
    assert "TAX_BLOCKED" in lines
    assert lines["TAX_BLOCKED"]["debit"] == 5400.0


def test_8_rcm_with_gstr2b_pending():
    """8. RCM + GSTR-2B pending/mismatch follows existing authoritative ITC rules."""
    invoice_data = {
        "invoice_number": "INV-RCM-2B",
        "subtotal": 40000.0,
        "tax_total": 7200.0,
        "igst_amount": 7200.0,
        "total_amount": 40000.0,
        "vendor_name": "GTA Carrier",
        "line_items": [{"description": "Freight Transportation", "taxable_amount": 40000.0}],
    }
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "GOODS_TRANSPORT_AGENCY",
        "supply_type": "INTER_STATE",
        "calculated": {"igst_amount": 7200.0, "gst_total": 7200.0},
    }
    itc_result = {
        "status": "GSTR2B_PENDING",
        "eligible_itc": 0.0,
        "blocked_itc": 0.0,
        "review_amount": 7200.0,
    }

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        gst_result=gst_result,
        itc_result=itc_result,
    )

    assert journal["status"] == "REVIEW_REQUIRED"
    assert journal["validation"]["balanced"] is True
    lines = {l["account_id"]: l for l in journal["lines"]}
    assert "TAX_INP_IGST" not in lines
    assert lines["LIAB_RCM_IGST"]["credit"] == 7200.0


def test_9_rcm_intra_state():
    """9. RCM intra-state: CGST + SGST liability handled correctly."""
    invoice_data = {
        "invoice_number": "INV-RCM-INTRA",
        "subtotal": 25000.0,
        "tax_total": 4500.0,
        "cgst_amount": 2250.0,
        "sgst_amount": 2250.0,
        "total_amount": 25000.0,
        "vendor_name": "Arbitrator Kumar",
        "line_items": [{"description": "Arbitration proceedings", "taxable_amount": 25000.0}],
    }
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "ARBITRAL_TRIBUNAL",
        "rcm_notification": "Notification No. 13/2017-CT(R) Entry 3",
        "supply_type": "INTRA_STATE",
        "calculated": {"cgst_amount": 2250.0, "sgst_amount": 2250.0, "gst_total": 4500.0},
    }

    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_LEGAL",
                "approved_account_name": "Legal & Professional Charges",
            }
        ]
    }

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting,
        gst_result=gst_result,
    )

    assert journal["status"] == "BALANCED"
    assert journal["total_debit"] == 29500.0
    assert journal["total_credit"] == 29500.0

    lines = {l["account_id"]: l for l in journal["lines"]}
    assert lines["LIAB_RCM_CGST"]["credit"] == 2250.0
    assert lines["LIAB_RCM_SGST"]["credit"] == 2250.0
    assert lines["LIAB_AP"]["credit"] == 25000.0


def test_10_rcm_inter_state_import_of_services():
    """10. RCM inter-state / import of services: IGST liability handled correctly."""
    invoice_data = {
        "invoice_number": "INV-RCM-IMPORT",
        "subtotal": 200000.0,
        "tax_total": 36000.0,
        "igst_amount": 36000.0,
        "total_amount": 200000.0,
        "vendor_name": "Cloud AI Corp (USA)",
        "line_items": [{"description": "Offshore Cloud Infrastructure", "taxable_amount": 200000.0}],
    }
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "IMPORT_OF_SERVICES",
        "rcm_notification": "Notification No. 10/2017-IT(R) Entry 1",
        "supply_type": "INTER_STATE",
        "calculated": {"igst_amount": 36000.0, "gst_total": 36000.0},
    }
    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_HOSTING",
                "approved_account_name": "Cloud Hosting Services",
            }
        ]
    }

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting,
        gst_result=gst_result,
    )

    assert journal["status"] == "BALANCED"
    assert journal["total_debit"] == 236000.0
    assert journal["total_credit"] == 236000.0

    lines = {l["account_id"]: l for l in journal["lines"]}
    assert lines["LIAB_RCM_IGST"]["credit"] == 36000.0
    assert lines["LIAB_AP"]["credit"] == 200000.0


def test_11_rcm_journal_balancing_debits_equal_credits():
    """11. RCM journal remains balanced: total_debits == total_credits."""
    invoice_data = {
        "invoice_number": "INV-BAL-01",
        "subtotal": 80000.0,
        "tax_total": 14400.0,
        "cgst_amount": 7200.0,
        "sgst_amount": 7200.0,
        "total_amount": 80000.0,
        "vendor_name": "Recovery Agent",
        "line_items": [{"description": "Debt recovery service", "taxable_amount": 80000.0}],
    }
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "RECOVERY_AGENT",
        "supply_type": "INTRA_STATE",
        "calculated": {"cgst_amount": 7200.0, "sgst_amount": 7200.0, "gst_total": 14400.0},
    }

    journal = journal_generator.generate_journal(invoice_data=invoice_data, gst_result=gst_result)
    assert journal["validation"]["balanced"] is True
    assert journal["total_debit"] == journal["total_credit"]
    assert journal["difference"] == 0.0


def test_12_rcm_with_tds_still_balances():
    """12. RCM with TDS still balances: Total debits == total credits."""
    invoice_data = {
        "invoice_number": "INV-BAL-TDS",
        "subtotal": 150000.0,
        "tax_total": 27000.0,
        "igst_amount": 27000.0,
        "total_amount": 150000.0,
        "vendor_name": "Director Sitting",
        "line_items": [{"description": "Director Commission", "taxable_amount": 150000.0}],
    }
    accounting = {
        "accounting": [{"line_index": 1, "approved_account_id": "ACC_DIR", "approved_account_name": "Director Remuneration"}],
        "tds": {
            "applicable": True,
            "is_approved": True,
            "tds_section": "194J",
            "tds_rate": 10.0,
            "final_tds_amount": 15000.0,
        },
    }
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "DIRECTOR_SERVICES",
        "supply_type": "INTER_STATE",
        "calculated": {"igst_amount": 27000.0, "gst_total": 27000.0},
    }

    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting,
        gst_result=gst_result,
    )

    assert journal["validation"]["balanced"] is True
    assert journal["total_debit"] == 177000.0
    assert journal["total_credit"] == 177000.0


def test_13_rcm_gst_not_duplicated():
    """13. RCM GST is not duplicated: No simultaneous vendor GST credit and RCM liability for same tax."""
    invoice_data = {
        "invoice_number": "INV-NO-DUP",
        "subtotal": 50000.0,
        "tax_total": 9000.0,
        "cgst_amount": 4500.0,
        "sgst_amount": 4500.0,
        "total_amount": 59000.0,  # Vendor incorrectly added 9000 GST to printed total
        "vendor_name": "GTA Transporter",
        "line_items": [{"description": "Consignment note freight", "taxable_amount": 50000.0}],
    }
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "GOODS_TRANSPORT_AGENCY",
        "supply_type": "INTRA_STATE",
        "calculated": {"cgst_amount": 4500.0, "sgst_amount": 4500.0, "gst_total": 9000.0},
    }

    journal = journal_generator.generate_journal(invoice_data=invoice_data, gst_result=gst_result)
    lines = {l["account_id"]: l for l in journal["lines"]}

    # Vendor payable must NOT contain the 9000 tax
    assert lines["LIAB_AP"]["credit"] == 50000.0
    # Total credits = Vendor AP (50k) + RCM CGST (4.5k) + RCM SGST (4.5k) = 59,000
    assert journal["total_credit"] == 59000.0
    assert journal["total_debit"] == 59000.0


def test_14_non_rcm_invoice_does_not_accidentally_use_rcm():
    """14. Non-RCM invoice does not accidentally use RCM liability logic."""
    invoice_data = {
        "invoice_number": "INV-NON-RCM",
        "subtotal": 60000.0,
        "tax_total": 10800.0,
        "cgst_amount": 5400.0,
        "sgst_amount": 5400.0,
        "total_amount": 70800.0,
        "vendor_name": "Stationery Shop",
        "line_items": [{"description": "Office Stationery", "taxable_amount": 60000.0}],
    }
    gst_result = {
        "is_reverse_charge": False,
        "rcm_category": None,
        "supply_type": "INTRA_STATE",
        "calculated": {"cgst_amount": 5400.0, "sgst_amount": 5400.0, "gst_total": 10800.0},
    }

    journal = journal_generator.generate_journal(invoice_data=invoice_data, gst_result=gst_result)
    lines = {l["account_id"]: l for l in journal["lines"]}

    assert "LIAB_RCM_CGST" not in lines
    assert "LIAB_RCM_SGST" not in lines
    assert "LIAB_RCM_IGST" not in lines
    assert "TAX_RCM_PENDING" not in lines
    assert lines["LIAB_AP"]["credit"] == 70800.0


def test_edge_case_a_rcm_tax_amounts_present_in_extracted_invoice():
    """Edge Case A: RCM with GST amounts present in extracted invoice."""
    invoice_data = {
        "invoice_number": "INV-EDGE-A",
        "subtotal": 10000.0,
        "tax_total": 1800.0,
        "cgst_amount": 900.0,
        "sgst_amount": 900.0,
        "total_amount": 11800.0,
        "vendor_name": "Advocate Senior",
        "line_items": [{"description": "Legal opinion", "taxable_amount": 10000.0}],
    }
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "LEGAL_SERVICES",
        "supply_type": "INTRA_STATE",
        "calculated": {"cgst_amount": 900.0, "sgst_amount": 900.0, "gst_total": 1800.0},
    }
    journal = journal_generator.generate_journal(invoice_data=invoice_data, gst_result=gst_result)
    assert journal["validation"]["balanced"] is True
    lines = {l["account_id"]: l for l in journal["lines"]}
    assert lines["LIAB_AP"]["credit"] == 10000.0
    assert lines["LIAB_RCM_CGST"]["credit"] == 900.0
    assert lines["LIAB_RCM_SGST"]["credit"] == 900.0


def test_edge_case_b_rcm_tax_amounts_absent_from_supplier_invoice():
    """Edge Case B: RCM with GST tax amounts absent from supplier invoice (pure bill of supply or unregistered invoice)."""
    invoice_data = {
        "invoice_number": "INV-EDGE-B",
        "subtotal": 10000.0,
        "tax_total": 0.0,
        "total_amount": 10000.0,
        "vendor_name": "Unregistered Landlord",
        "line_items": [{"description": "Commercial Property Rent", "taxable_amount": 10000.0}],
    }
    # GST engine calculated RCM 18% (900 CGST + 900 SGST) under Notif 13/2017 Entry 5AB
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "RENTING_IMMOVABLE_PROPERTY_UNREGISTERED",
        "supply_type": "INTRA_STATE",
        "calculated": {"cgst_amount": 900.0, "sgst_amount": 900.0, "gst_total": 1800.0},
    }
    journal = journal_generator.generate_journal(invoice_data=invoice_data, gst_result=gst_result)
    assert journal["validation"]["balanced"] is True
    lines = {l["account_id"]: l for l in journal["lines"]}
    assert lines["LIAB_AP"]["credit"] == 10000.0
    assert lines["LIAB_RCM_CGST"]["credit"] == 900.0
    assert lines["LIAB_RCM_SGST"]["credit"] == 900.0
    # Since supplier is unregistered without GSTIN, ITC engine marks REVIEW_REQUIRED (documentary check);
    # tax is held in TAX_BLOCKED pending verification rather than recognized asset.
    assert lines["TAX_BLOCKED"]["debit"] == 1800.0


def test_edge_case_f_rcm_ambiguous_itc():
    """Edge Case F: RCM + ambiguous / partially eligible ITC."""
    invoice_data = {
        "invoice_number": "INV-EDGE-F",
        "subtotal": 20000.0,
        "tax_total": 3600.0,
        "igst_amount": 3600.0,
        "total_amount": 20000.0,
        "vendor_name": "Security Agency",
        "line_items": [{"description": "Security Services", "taxable_amount": 20000.0}],
    }
    gst_result = {
        "is_reverse_charge": True,
        "rcm_category": "SECURITY_SERVICES",
        "supply_type": "INTER_STATE",
        "calculated": {"igst_amount": 3600.0, "gst_total": 3600.0},
    }
    itc_result = {
        "status": "PARTIALLY_ELIGIBLE",
        "eligible_itc": 1800.0,
        "blocked_itc": 1800.0,
    }
    journal = journal_generator.generate_journal(
        invoice_data=invoice_data,
        gst_result=gst_result,
        itc_result=itc_result,
    )
    assert journal["validation"]["balanced"] is True
    lines = {l["account_id"]: l for l in journal["lines"]}
    assert lines["TAX_RCM_PENDING"]["debit"] == 1800.0
    assert lines["TAX_BLOCKED"]["debit"] == 1800.0
    assert lines["LIAB_RCM_IGST"]["credit"] == 3600.0
    assert lines["LIAB_AP"]["credit"] == 20000.0
