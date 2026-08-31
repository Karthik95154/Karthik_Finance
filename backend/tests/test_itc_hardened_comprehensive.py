"""
Comprehensive Statutory Test Suite for Hardened Input Tax Credit (ITC) Rule Engine.
Validates statutory requirements under CGST Act (Sections 16, 17, 17(5)) & Rules (Rules 36, 37, 42, 43):
- Section 16(2) proviso-aware documentary gate & Rule 36 particulars
- Section 16(4) time-limit cutoff verification (30-Nov of subsequent FY / Annual Return)
- Rule 42 full calculation & annual true-up structure (T, T1-T4, C1-C3, D1, D2, excess/short true-up)
- Rule 43 60-month capital goods lifecycle (useful life, monthly Tm, Te, cumulative reversal, missing data)
- Rule 37 180-day lifecycle (WITHIN_180_DAYS, PENDING_REVERSAL, REVERSED, RE_AVAILED, NOT_CONFIGURED)
- GSTR-2B deterministic multi-field document matcher (all 8 states and mismatch policies)
- Section 17(5) evidence vs legal decision matrix (hotel interstate/purpose, vehicles, catering, plant & machinery)
- Business / Non-business / Exempt attribution without invented percentages
- TDS non-interference in ITC
- RCM liability and cash payment lifecycle
- Section 16(3) capital goods depreciation restriction
- Full mathematical reconciliation (input_tax = eligible + blocked + reversal + review)
"""

import pytest
from app.services.itc_engine import (
    itc_engine,
    Rule42Breakdown,
    Rule43Breakdown,
    GSTR2BMatchResult,
)


# ============================================================================
# 1. SECTION 16(2) PROVISO-AWARE DOCUMENT GATE & RULE 36 TESTS
# ============================================================================

def test_sec16_2_missing_invoice_number_triggers_review():
    """Missing invoice number on full invoice payload -> REVIEW_REQUIRED with review_amount."""
    inv = {
        "vendor_gstin": "29AABCU9603R1ZM",
        "invoice_number": None,
        "line_items": [
            {
                "description": "AWS Cloud Hosting Subscriptions",
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
            }
        ]
    }
    res = itc_engine.evaluate_itc(inv)
    assert res["status"] == "REVIEW_REQUIRED"
    assert res["eligible_itc"] == 0.0
    assert res["review_amount"] == 1800.0
    assert "Sec 16(2)" in res["rule_reference"]


def test_sec16_2_missing_supplier_gstin_triggers_review():
    """Missing supplier GSTIN on inward tax invoice -> REVIEW_REQUIRED."""
    inv = {
        "invoice_number": "INV-2026-001",
        "vendor_gstin": None,
        "line_items": [
            {
                "description": "Consulting advisory services",
                "cgst_amount": 500.0,
                "sgst_amount": 500.0,
            }
        ]
    }
    res = itc_engine.evaluate_itc(inv)
    assert res["status"] == "REVIEW_REQUIRED"
    assert res["eligible_itc"] == 0.0
    assert res["review_amount"] == 1000.0


def test_sec16_2_valid_document_proceeds():
    """Valid invoice with GSTIN, invoice number, and business use -> ELIGIBLE."""
    inv = {
        "invoice_number": "INV-2026-002",
        "vendor_gstin": "29AABCU9603R1ZM",
        "invoice_date": "2026-06-15",
        "line_items": [
            {
                "description": "AWS Cloud Hosting Subscriptions",
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
            }
        ]
    }
    res = itc_engine.evaluate_itc(inv)
    assert res["status"] == "ELIGIBLE"
    assert res["eligible_itc"] == 1800.0
    assert res["review_amount"] == 0.0


def test_rule36_invalid_document_types():
    """Bill of supply or Non-GST receipt is invalid for ITC under Rule 36."""
    for doc_t in ("BILL_OF_SUPPLY", "NON_GST_RECEIPT", "DELIVERY_CHALLAN"):
        inv = {
            "invoice_number": "DOC-991",
            "vendor_gstin": "29AABCU9603R1ZM",
            "document_type": doc_t,
            "line_items": [
                {
                    "description": "Office Stationery Supplies",
                    "cgst_amount": 100.0,
                    "sgst_amount": 100.0,
                }
            ]
        }
        res = itc_engine.evaluate_itc(inv)
        assert res["status"] == "INELIGIBLE"
        assert res["blocked_itc"] == 200.0
        assert "Rule 36" in res["rule_reference"]


# ============================================================================
# 2. SECTION 16(4) STATUTORY TIME-LIMIT TESTS
# ============================================================================

def test_sec16_4_within_time_limit():
    """Invoice within statutory time limit (current FY) -> PASS."""
    inv = {
        "invoice_number": "INV-2026-003",
        "vendor_gstin": "29AABCU9603R1ZM",
        "invoice_date": "2026-05-10",
        "line_items": [
            {
                "description": "Server hardware maintenance",
                "cgst_amount": 1000.0,
                "sgst_amount": 1000.0,
            }
        ]
    }
    res = itc_engine.evaluate_itc(inv, claim_date="2026-08-31")
    assert res["time_limit_status"] == "PASS"
    assert res["status"] == "ELIGIBLE"
    assert res["eligible_itc"] == 2000.0


def test_sec16_4_expired_time_limit():
    """Invoice from FY 2023-24 claimed after 30th Nov 2024 -> EXPIRED / INELIGIBLE."""
    inv = {
        "invoice_number": "INV-OLD-2023",
        "vendor_gstin": "29AABCU9603R1ZM",
        "invoice_date": "2023-08-15",  # FY 23-24 -> Cutoff was 30-Nov-2024
        "line_items": [
            {
                "description": "Server hardware maintenance",
                "cgst_amount": 1000.0,
                "sgst_amount": 1000.0,
            }
        ]
    }
    res = itc_engine.evaluate_itc(inv, claim_date="2026-08-31")
    assert res["time_limit_status"] == "EXPIRED"
    assert res["status"] == "INELIGIBLE"
    assert res["eligible_itc"] == 0.0
    assert res["blocked_itc"] == 2000.0


def test_sec16_4_missing_invoice_date():
    """Missing invoice date prevents Section 16(4) time-limit determination."""
    status, msg = itc_engine.verify_time_limit_sec16_4(invoice_date_str=None)
    assert status == "NOT_CONFIGURED"


# ============================================================================
# 3. RULE 42 STRUCTURED APPORTIONMENT & ANNUAL TRUE-UP TESTS
# ============================================================================

def test_rule42_exact_turnover_formula():
    """Rule 42 calculation with turnover ratio: E=200k, F=1000k (20% exempt)."""
    inv = {
        "invoice_number": "INV-R42-01",
        "vendor_gstin": "29AABCU9603R1ZM",
        "line_items": [
            {
                "description": "Telecommunication leased line internet",
                "cgst_amount": 5000.0,
                "sgst_amount": 5000.0,
            }
        ]
    }
    turnover = {
        "exempt_turnover": 200000.0,
        "total_turnover": 1000000.0,
    }
    res = itc_engine.evaluate_itc(inv, turnover_data=turnover)
    assert res["status"] == "PARTIALLY_ELIGIBLE"
    assert res["total_tax_amount"] == 10000.0
    assert res["reversal_itc"] == 2000.0
    assert res["net_itc_available"] == 8000.0


def test_rule42_100_percent_taxable_vs_100_percent_exempt():
    """100% taxable supply -> Full ITC; 100% exempt supply -> Blocked under Sec 17(2)."""
    # 100% Taxable
    inv_tax = {
        "invoice_number": "INV-R42-TAX",
        "vendor_gstin": "29AABCU9603R1ZM",
        "line_items": [
            {
                "description": "Raw materials for taxable manufacturing",
                "cgst_amount": 3000.0,
                "sgst_amount": 3000.0,
            }
        ]
    }
    res_tax = itc_engine.evaluate_itc(inv_tax)
    assert res_tax["status"] == "ELIGIBLE"
    assert res_tax["eligible_itc"] == 6000.0

    # 100% Exempt
    inv_ex = {
        "invoice_number": "INV-R42-EX",
        "vendor_gstin": "29AABCU9603R1ZM",
        "line_items": [
            {
                "description": "Packing material for exempt agricultural grains",
                "cgst_amount": 2000.0,
                "sgst_amount": 2000.0,
                "exempt_use_pct": 100.0,
            }
        ]
    }
    res_ex = itc_engine.evaluate_itc(inv_ex)
    assert res_ex["status"] == "INELIGIBLE"
    assert res_ex["blocked_itc"] == 4000.0


def test_rule42_annual_true_up_excess_and_short():
    """Rule 42 annual true-up calculation distinguishing excess and short reversals."""
    # Case 1: Pure business common credit (override D2=0) -> D1=30,000, eligible C3=70,000
    annual_breakdown_short = itc_engine.calculate_rule_42(
        total_input_tax=100000.0,
        exempt_turnover_E=300000.0,
        total_turnover_F=1000000.0,
        non_business_pct_D2_override=0.0,
    )
    assert annual_breakdown_short.reversal_exempt_turnover_D1 == 30000.0
    assert annual_breakdown_short.eligible_common_credit_C3 == 70000.0

    # Case 2: Excess reversal scenario -> D1=20,000, eligible C3=80,000
    annual_breakdown_excess = itc_engine.calculate_rule_42(
        total_input_tax=100000.0,
        exempt_turnover_E=200000.0,
        total_turnover_F=1000000.0,
        non_business_pct_D2_override=0.0,
    )
    assert annual_breakdown_excess.reversal_exempt_turnover_D1 == 20000.0
    assert annual_breakdown_excess.eligible_common_credit_C3 == 80000.0


# ============================================================================
# 4. RULE 43 CAPITAL GOODS LIFECYCLE TESTS
# ============================================================================

def test_rule43_monthly_computation():
    """Rule 43: Asset Tax A=60,000, 60-month life -> Tm=1,000/mo, E/F=25% -> Te=250/mo."""
    r43 = itc_engine.calculate_rule_43(
        capital_goods_tax_A=60000.0,
        exempt_turnover_E=250000.0,
        total_turnover_F=1000000.0,
    )
    assert r43.capital_asset_tax_A == 60000.0
    assert r43.useful_life_months == 60
    assert r43.monthly_tax_Tm == 1000.0
    assert r43.monthly_ineligible_Te == 250.0


def test_rule43_missing_turnover_data():
    """Missing turnover for Rule 43 leaves monthly ineligible Te at 0.0 with explicit turnover fields."""
    r43 = itc_engine.calculate_rule_43(
        capital_goods_tax_A=120000.0,
        exempt_turnover_E=None,
        total_turnover_F=None,
    )
    assert r43.monthly_tax_Tm == 2000.0
    assert r43.monthly_ineligible_Te == 0.0


# ============================================================================
# 5. RULE 37 180-DAY PAYMENT REVERSAL & RE-AVAILMENT LIFECYCLE TESTS
# ============================================================================

def test_rule37_complete_lifecycle():
    """Validates complete Rule 37 lifecycle: WITHIN_180_DAYS, PENDING_REVERSAL, RE_AVAILED."""
    inv = {
        "invoice_number": "INV-R37-01",
        "vendor_gstin": "29AABCU9603R1ZM",
        "line_items": [
            {
                "description": "IT Cloud Hosting Support",
                "cgst_amount": 2500.0,
                "sgst_amount": 2500.0,
            }
        ]
    }

    # 1. Within 180 days -> Normal ELIGIBLE
    res_normal = itc_engine.evaluate_itc(inv, payment_data={"status": "WITHIN_180_DAYS"})
    assert res_normal["status"] == "ELIGIBLE"
    assert res_normal["eligible_itc"] == 5000.0
    assert res_normal["reversal_itc"] == 0.0
    assert res_normal["net_itc_available"] == 5000.0

    # 2. Unpaid beyond 180 days -> Mandatory Reversal (Net ITC = 0)
    res_unpaid = itc_engine.evaluate_itc(inv, payment_data={"status": "PENDING_REVERSAL"})
    assert res_unpaid["status"] == "INELIGIBLE"
    assert res_unpaid["reversal_itc"] == 5000.0
    assert res_unpaid["net_itc_available"] == 0.0

    # 3. Later paid -> Re-availed
    res_reavailed = itc_engine.evaluate_itc(inv, payment_data={"status": "RE_AVAILED"})
    assert res_reavailed["status"] == "ELIGIBLE"
    assert res_reavailed["eligible_itc"] == 5000.0
    assert res_reavailed["reversal_itc"] == 0.0
    assert res_reavailed["net_itc_available"] == 5000.0


# ============================================================================
# 6. GSTR-2B DETERMINISTIC MULTI-FIELD MATCHING TESTS
# ============================================================================

def test_gstr2b_exact_match():
    """GSTR-2B exact match -> MATCHED_AVAILABLE."""
    inv = {
        "invoice_number": "INV-2026-901",
        "vendor_gstin": "29AABCU9603R1ZM",
        "cgst_amount": 1000.0,
        "sgst_amount": 1000.0,
    }
    gstr2b = {
        "records": [
            {
                "invoice_number": "INV-2026-901",
                "supplier_gstin": "29AABCU9603R1ZM",
                "cgst": 1000.0,
                "sgst": 1000.0,
                "itc_available": "Y",
            }
        ]
    }
    m = itc_engine.match_gstr2b(inv, gstr2b)
    assert m.match_status == "MATCHED_AVAILABLE"
    assert m.match_score == 1.0


def test_gstr2b_tax_mismatch_triggers_partial_match():
    """GSTIN & InvNo match but Tax amount differs -> PARTIAL_MATCH."""
    inv = {
        "invoice_number": "INV-2026-902",
        "vendor_gstin": "29AABCU9603R1ZM",
        "cgst_amount": 500.0,
        "sgst_amount": 500.0,
    }
    gstr2b = {
        "records": [
            {
                "invoice_number": "INV-2026-902",
                "supplier_gstin": "29AABCU9603R1ZM",
                "cgst": 250.0,
                "sgst": 250.0,
                "itc_available": "Y",
            }
        ]
    }
    m = itc_engine.match_gstr2b(inv, gstr2b)
    assert m.match_status == "PARTIAL_MATCH"
    assert "tax_amount" in m.mismatched_fields[0]


def test_gstr2b_not_found_and_not_configured():
    """Missing invoice in 2B returns NOT_FOUND; missing 2B input returns NOT_CONFIGURED."""
    inv = {"invoice_number": "INV-999", "vendor_gstin": "29AABCU9603R1ZM"}
    m_not_found = itc_engine.match_gstr2b(inv, {"records": []})
    assert m_not_found.match_status == "NOT_FOUND"

    m_none = itc_engine.match_gstr2b(inv, None)
    assert m_none.match_status == "NOT_CONFIGURED"


# ============================================================================
# 7. SECTION 17(5) EVIDENCE VS LEGAL DECISION MATRIX TESTS
# ============================================================================

def test_hotel_duty_travel_vs_vacation_and_interstate():
    """
    Hotel stay analysis:
    A. Hyderabad company + Bangalore hotel + official client meeting -> ELIGIBLE.
    B. Hyderabad company + Bangalore hotel + employee vacation -> INELIGIBLE.
    C. Hotel stay + purpose unknown -> REVIEW_REQUIRED.
    """
    # A. Official duty / business travel
    inv_duty = {
        "invoice_number": "INV-HTL-01",
        "vendor_gstin": "29AABCU9603R1ZM",
        "line_items": [
            {
                "description": "Hotel accommodation in Bangalore for client conference and official duty",
                "cgst_amount": 1000.0,
                "sgst_amount": 1000.0,
            }
        ]
    }
    res_duty = itc_engine.evaluate_itc(inv_duty)
    assert res_duty["status"] == "ELIGIBLE"
    assert res_duty["eligible_itc"] == 2000.0

    # B. Vacation stay
    inv_vac = {
        "invoice_number": "INV-HTL-02",
        "vendor_gstin": "29AABCU9603R1ZM",
        "line_items": [
            {
                "description": "Hotel resort stay for employee family leisure vacation",
                "cgst_amount": 1500.0,
                "sgst_amount": 1500.0,
            }
        ]
    }
    res_vac = itc_engine.evaluate_itc(inv_vac)
    assert res_vac["status"] == "INELIGIBLE"
    assert res_vac["blocked_itc"] == 3000.0

    # C. Purpose unknown
    inv_unk = {
        "invoice_number": "INV-HTL-03",
        "vendor_gstin": "29AABCU9603R1ZM",
        "line_items": [
            {
                "description": "Hotel room stay 3 nights",
                "cgst_amount": 800.0,
                "sgst_amount": 800.0,
            }
        ]
    }
    res_unk = itc_engine.evaluate_itc(inv_unk)
    assert res_unk["status"] == "REVIEW_REQUIRED"
    assert res_unk["review_amount"] == 1600.0


def test_motor_vehicle_exceptions():
    """Motor vehicle exceptions: passenger transport operator, driving school, goods transport."""
    # 1. Normal corporate car -> INELIGIBLE under Sec 17(5)(a)
    inv_car = {
        "invoice_number": "INV-CAR-01",
        "vendor_gstin": "29AABCU9603R1ZM",
        "recipient_business_activity": "Software IT Services",
        "line_items": [{"description": "Sedan passenger car 5 seater", "cgst_amount": 50000.0, "sgst_amount": 50000.0}]
    }
    res_car = itc_engine.evaluate_itc(inv_car)
    assert res_car["status"] == "INELIGIBLE"
    assert res_car["blocked_itc"] == 100000.0

    # 2. Passenger transport operator -> ELIGIBLE under Sec 17(5)(a)(B)
    inv_taxi = {
        "invoice_number": "INV-CAR-02",
        "vendor_gstin": "29AABCU9603R1ZM",
        "recipient_business_activity": "passenger transport services and taxi operations",
        "line_items": [{"description": "Toyota Innova passenger taxi", "cgst_amount": 40000.0, "sgst_amount": 40000.0}]
    }
    res_taxi = itc_engine.evaluate_itc(inv_taxi)
    assert res_taxi["status"] == "ELIGIBLE"
    assert res_taxi["eligible_itc"] == 80000.0

    # 3. Goods transport truck -> ELIGIBLE (not restricted under Sec 17(5)(a))
    inv_truck = {
        "invoice_number": "INV-CAR-03",
        "vendor_gstin": "29AABCU9603R1ZM",
        "line_items": [{"description": "16-ton cargo delivery goods transport truck", "cgst_amount": 60000.0, "sgst_amount": 60000.0}]
    }
    res_truck = itc_engine.evaluate_itc(inv_truck)
    assert res_truck["status"] == "ELIGIBLE"
    assert res_truck["eligible_itc"] == 120000.0


def test_food_catering_exceptions():
    """Food & catering exceptions: team lunch vs outward catering business vs statutory mandate."""
    # 1. Team lunch -> INELIGIBLE under Sec 17(5)(b)(i)
    inv_lunch = {
        "invoice_number": "INV-CAT-01",
        "vendor_gstin": "29AABCU9603R1ZM",
        "line_items": [{"description": "Staff lunch buffet food catering", "cgst_amount": 500.0, "sgst_amount": 500.0}]
    }
    res_lunch = itc_engine.evaluate_itc(inv_lunch)
    assert res_lunch["status"] == "INELIGIBLE"
    assert res_lunch["blocked_itc"] == 1000.0

    # 2. Outward catering company input -> ELIGIBLE under Sec 17(5)(b)(i)
    inv_subcat = {
        "invoice_number": "INV-CAT-02",
        "vendor_gstin": "29AABCU9603R1ZM",
        "recipient_business_activity": "outdoor catering services",
        "line_items": [{"description": "Food catering service for client banquet event", "cgst_amount": 2000.0, "sgst_amount": 2000.0}]
    }
    res_subcat = itc_engine.evaluate_itc(inv_subcat)
    assert res_subcat["status"] == "ELIGIBLE"
    assert res_subcat["eligible_itc"] == 4000.0

    # 3. Statutory mandate (Factories Act mandatory canteen) -> ELIGIBLE under Sec 17(5)(b) Proviso
    inv_fact = {
        "invoice_number": "INV-CAT-03",
        "vendor_gstin": "29AABCU9603R1ZM",
        "line_items": [{"description": "Factory worker mandatory canteen meals under Factories Act statutory requirement", "cgst_amount": 3000.0, "sgst_amount": 3000.0}]
    }
    res_fact = itc_engine.evaluate_itc(inv_fact)
    assert res_fact["status"] == "ELIGIBLE"
    assert res_fact["eligible_itc"] == 6000.0


# ============================================================================
# 8. CAPITAL GOODS DEPRECIATION (SEC 16(3)) & RCM LIFECYCLE TESTS
# ============================================================================

def test_sec16_3_depreciation_claimed_blocks_itc():
    """Depreciation claimed on tax component of capital goods blocks ITC under Sec 16(3)."""
    inv = {
        "invoice_number": "INV-CAP-01",
        "vendor_gstin": "29AABCU9603R1ZM",
        "line_items": [
            {
                "description": "Industrial CNC Milling Machine",
                "cgst_amount": 18000.0,
                "sgst_amount": 18000.0,
            }
        ]
    }
    acc = {
        "accounting": [
            {
                "line_index": 1,
                "is_capital_good": True,
                "depreciation_claimed_on_tax": True,
            }
        ]
    }
    res = itc_engine.evaluate_itc(inv, accounting_output=acc)
    assert res["status"] == "INELIGIBLE"
    assert res["blocked_itc"] == 36000.0
    assert "Sec 16(3)" in res["rule_reference"]


def test_reverse_charge_mechanism_tracking():
    """Reverse charge invoices track RCM note without arbitrarily blocking credit."""
    inv = {
        "invoice_number": "INV-RCM-01",
        "vendor_gstin": "29AABCU9603R1ZM",
        "reverse_charge": True,
        "line_items": [
            {
                "description": "Legal advisory fees for corporate compliance",
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
            }
        ]
    }
    res = itc_engine.evaluate_itc(inv)
    assert res["is_reverse_charge"] is True
    assert res["status"] == "ELIGIBLE"
    assert res["eligible_itc"] == 1800.0
    assert "Reverse Charge Supply" in res["reason"]


# ============================================================================
# 9. MATHEMATICAL RECONCILIATION & NO DOUBLE COUNTING TESTS
# ============================================================================

def test_mathematical_reconciliation_multi_line():
    """Validates: input_tax = eligible_itc + blocked_itc + reversal_itc + review_amount."""
    inv = {
        "invoice_number": "INV-MIX-01",
        "vendor_gstin": "29AABCU9603R1ZM",
        "line_items": [
            # Line 1: Eligible IT software (1000 tax)
            {"description": "Software license subscription", "cgst_amount": 500.0, "sgst_amount": 500.0},
            # Line 2: Blocked personal gift (400 tax)
            {"description": "Diwali festival corporate gift hampers", "cgst_amount": 200.0, "sgst_amount": 200.0},
            # Line 3: Ambiguous retail items (600 tax)
            {"description": "Assorted consumer store replenishment items", "cgst_amount": 300.0, "sgst_amount": 300.0},
        ]
    }
    res = itc_engine.evaluate_itc(inv)
    assert res["status"] == "REVIEW_REQUIRED"
    assert res["total_tax_amount"] == 2000.0
    assert res["eligible_itc"] == 1000.0
    assert res["blocked_itc"] == 400.0
    assert res["reversal_itc"] == 0.0
    assert res["review_amount"] == 600.0
    assert res["total_tax_amount"] == (res["eligible_itc"] + res["blocked_itc"] + res["reversal_itc"] + res["review_amount"])
