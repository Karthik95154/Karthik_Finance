import pytest
from app.services.tds_engine import (
    parse_vendor_declared_tds,
    tds_engine,
    get_effective_tds_data,
)
from app.services.model_response_adapter import ModelResponseAdapter


def test_explicit_tds_amount_in_raw_text():
    """Test 1: Explicit TDS amount found in raw document text."""
    raw_text = "We have booked TDS amount Rs. 31.08. Kindly share form 16A for the respective quarter."
    parsed = parse_vendor_declared_tds([raw_text], base_amount=31080.0)

    assert parsed["present"] is True
    assert parsed["amount"] == 31.08
    assert parsed["raw_text"] == raw_text
    assert parsed["rate"] is None
    # Derived rate from 31.08 / 31080 * 100 = 0.1%
    assert parsed["derived_rate"] == 0.1


def test_explicit_tds_rate_in_text():
    """Test 2: Explicit TDS rate found in text."""
    raw_text = "Payment terms: TDS @ 1% deducted as per Section 194C"
    parsed = parse_vendor_declared_tds([raw_text], base_amount=50000.0)

    assert parsed["present"] is True
    assert parsed["rate"] == 1.0
    assert parsed["amount"] is None
    assert "TDS @ 1%" in parsed["raw_text"]


def test_vendor_declaration_preserved_in_model_adapter():
    """Test 3: Vendor declaration preserved in model adapter output."""
    raw_text = "Note: TDS withheld amount Rs. 150.00"
    model_response = {
        "invoice_details": {
            "invoice_number": "INV-101",
            "payment_terms": "Net 30",
        },
        "line_items": [
            {
                "description": "General Consulting",
                "taxable_amount": 15000.0,
            }
        ],
        "financial_details": {
            "subtotal": 15000.0,
            "total_amount": 17700.0,
        },
        "tds_support": {
            "applicable": True,
            "section": "194J",
            "rate": 10.0,
        },
    }

    norm = ModelResponseAdapter.normalize_model_response(
        model_response=model_response,
        raw_document_text=raw_text,
    )

    tds_data = norm["normalized_accounting"]["tds_assessment"]
    assert "vendor_declared_tds" in tds_data
    v_decl = tds_data["vendor_declared_tds"]
    assert v_decl["present"] is True
    assert v_decl["amount"] == 150.00


def test_vendor_statutory_conflict_triggers_review():
    """Test 4: Material conflict between vendor declared TDS and statutory calculation triggers REVIEW_REQUIRED."""
    # Statutory 194J at 10% on 31,080 is 3,108.
    # Vendor declares booked TDS of 31.08.
    raw_text = "We have booked TDS amount Rs. 31.08. Kindly share form 16A"
    model_response = {
        "invoice_details": {
            "invoice_number": "KEKA-001",
        },
        "line_items": [
            {
                "description": "HR & Payroll Platform Subscription",
                "hsn_sac": "997331",
                "taxable_amount": 31080.0,
            }
        ],
        "financial_details": {
            "subtotal": 31080.0,
            "total_amount": 36674.4,
        },
        "tds_support": {},
    }

    norm = ModelResponseAdapter.normalize_model_response(
        model_response=model_response,
        raw_document_text=raw_text,
    )

    tds_data = norm["normalized_accounting"]["tds_assessment"]
    # 1. Statutory assessment: SAC 997331 resolved to 194J (2%), statutory TDS is 621.60
    assert tds_data["section"] == "194J"
    assert tds_data["rate"] == 2.0
    assert tds_data["proposed_tds_amount"] == 621.60

    # 2. Conflict exists because vendor declared 31.08 while statutory is 621.60
    assert tds_data["approval_status"] == "REVIEW_REQUIRED"
    assert tds_data["tds_needs_review"] is True
    assert tds_data["tds_conflict_code"] == "TDS_VENDOR_STATUTORY_MISMATCH"
    assert "Conflict between vendor-declared TDS" in tds_data["tds_reasoning"]
    assert "₹31.08" in tds_data["tds_reasoning"]

    # 3. Both values preserved in SSOT
    effective = get_effective_tds_data({"tds_assessment": tds_data})
    assert effective["approval_status"] == "REVIEW_REQUIRED"
    assert effective["tds_conflict_code"] == "TDS_VENDOR_STATUTORY_MISMATCH"
    assert effective["vendor_declared_tds"]["amount"] == 31.08
    assert effective["tds_amount"] == 621.60


def test_sac_997331_software_does_not_become_194i_rent():
    """Test 5: SAC 997331 software/SaaS does NOT become 194I 10% rent."""
    model_response = {
        "invoice_details": {"invoice_number": "INV-SaaS-1"},
        "line_items": [
            {
                "description": "Cloud ERP Software Licensing",
                "hsn_sac": "997331",
                "taxable_amount": 50000.0,
            }
        ],
        "financial_details": {
            "subtotal": 50000.0,
            "total_amount": 59000.0,
        },
        "tds_support": {},
    }

    norm = ModelResponseAdapter.normalize_model_response(model_response)
    tds = norm["normalized_accounting"]["tds_assessment"]

    # Must be 194J (Technical Services / 2%), NOT 194I 10%
    assert tds["section"] == "194J"
    assert tds["rate"] == 2.0
    assert tds["proposed_tds_amount"] == 1000.0


def test_equipment_rental_still_maps_correctly_to_194i_2():
    """Test 6: Physical equipment rental still maps to 194I at 2%."""
    model_response = {
        "invoice_details": {"invoice_number": "INV-EQ-1"},
        "line_items": [
            {
                "description": "Generator & Plant Machinery Leasing Services",
                "hsn_sac": "997314",
                "taxable_amount": 40000.0,
            }
        ],
        "financial_details": {
            "subtotal": 40000.0,
            "total_amount": 47200.0,
        },
        "tds_support": {},
    }

    norm = ModelResponseAdapter.normalize_model_response(model_response)
    tds = norm["normalized_accounting"]["tds_assessment"]

    assert tds["section"] == "194I"
    assert tds["rate"] == 2.0
    assert tds["proposed_tds_amount"] == 800.0
    assert "Plant, Machinery or Equipment" in tds["provision"]


def test_property_rent_still_maps_correctly_to_194i_10():
    """Test 7: Property/building rent still maps to 194I at 10%."""
    model_response = {
        "invoice_details": {"invoice_number": "INV-RENT-1"},
        "line_items": [
            {
                "description": "Commercial Office Space Premises Rent",
                "hsn_sac": "997212",
                "taxable_amount": 100000.0,
            }
        ],
        "financial_details": {
            "subtotal": 100000.0,
            "total_amount": 118000.0,
        },
        "tds_support": {},
    }

    norm = ModelResponseAdapter.normalize_model_response(model_response)
    tds = norm["normalized_accounting"]["tds_assessment"]

    assert tds["section"] == "194I"
    assert tds["rate"] == 10.0
    assert tds["proposed_tds_amount"] == 10000.0
    assert "Immovable Property" in tds["provision"]


def test_ambiguous_9973_requires_review():
    """Test 8: Ambiguous 9973xx with no equipment or software keywords triggers REVIEW_REQUIRED without forced statutory classification."""
    model_response = {
        "invoice_details": {"invoice_number": "INV-AMBIG-1"},
        "line_items": [
            {
                "description": "General Operational Support Services",
                "hsn_sac": "997399",
                "taxable_amount": 60000.0,
            }
        ],
        "financial_details": {
            "subtotal": 60000.0,
            "total_amount": 70800.0,
        },
        "tds_support": {},
    }

    norm = ModelResponseAdapter.normalize_model_response(model_response)
    tds = norm["normalized_accounting"]["tds_assessment"]

    # Ambiguous 9973: no forced section 194I, no forced rate, preserved base, review required
    assert tds["section"] is None
    assert tds["rate"] is None
    assert tds["proposed_tds_amount"] is None
    assert tds["base_amount"] == 60000.0
    assert tds["approval_status"] == "REVIEW_REQUIRED"
    assert tds["tds_needs_review"] is True
    assert tds["tds_conflict_code"] == "TDS_AMBIGUOUS_SAC"

    # Verify downstream TDS SSOT represents "classification unresolved" without inventing section or rate
    effective = get_effective_tds_data({"tds_assessment": tds})
    assert effective["applicable"] is True
    assert effective["section"] is None
    assert effective["rate"] is None
    assert effective["tds_amount"] is None
    assert effective["base_amount"] == 60000.0
    assert effective["approval_status"] == "REVIEW_REQUIRED"
    assert effective["tds_conflict_code"] == "TDS_AMBIGUOUS_SAC"


def test_no_vendor_tds_declaration_unchanged():
    """Test 9: Without vendor TDS declaration, statutory flow operates normally."""
    model_response = {
        "invoice_details": {"invoice_number": "INV-STD-1"},
        "line_items": [
            {
                "description": "Legal Advisory Services",
                "hsn_sac": "998211",
                "taxable_amount": 25000.0,
            }
        ],
        "financial_details": {
            "subtotal": 25000.0,
            "total_amount": 29500.0,
        },
        "tds_support": {},
    }

    norm = ModelResponseAdapter.normalize_model_response(model_response)
    tds = norm["normalized_accounting"]["tds_assessment"]

    assert tds["vendor_declared_tds"]["present"] is False
    assert tds["section"] == "194J"
    assert tds["rate"] == 10.0
    assert tds["proposed_tds_amount"] == 2500.0
    assert tds["tds_conflict_code"] is None


def test_section_393_purchase_of_goods_rate():
    """Test 10: Section 393 + Purchase of Goods (194Q) correctly applies 0.1% rate, NOT 2%."""
    calc_res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 8(ii)] - Purchase of Goods",
        nature_of_payment="Purchase of Goods",
        base_amount=834260.0,
        vendor_pan="AABCB1234F",
    )
    assert calc_res["applicable"] is True
    assert calc_res["rate"] == 0.1
    assert calc_res["tds_amount"] == 834.26


def test_section_393_professional_services_rate():
    """Test 11: Section 393 + Professional Services (194J(1)(a)) applies 10% rate, NOT 2%."""
    calc_res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 6(iii)(D)(b)] - Professional Services",
        nature_of_payment="Professional Services & Legal Consulting",
        base_amount=50000.0,
        vendor_pan="AABCB1234F",
    )
    assert calc_res["applicable"] is True
    assert calc_res["rate"] == 10.0
    assert calc_res["tds_amount"] == 5000.0


def test_section_393_technical_services_rate():
    """Test 12: Section 393 + Technical Services (194J(1)(b)) applies 2% rate."""
    calc_res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 6(iii)(D)(a)] - Fees for Technical Services (FTS)",
        nature_of_payment="Fees for Technical Services (FTS) & Cloud Infrastructure",
        base_amount=50000.0,
        vendor_pan="AABCB1234F",
    )
    assert calc_res["applicable"] is True
    assert calc_res["rate"] == 2.0
    assert calc_res["tds_amount"] == 1000.0


def test_section_393_ambiguous_requires_review():
    """Test 13: Section 393 alone without reliable category/provision does NOT force 2% and marks review required."""
    calc_res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision=None,
        nature_of_payment=None,
        base_amount=100000.0,
        vendor_pan="AABCB1234F",
    )
    assert calc_res["applicable"] is True
    assert calc_res["rate"] is None
    assert calc_res["tds_amount"] is None
    assert calc_res["tds_needs_review"] is True
    assert calc_res["tds_conflict_code"] == "TDS_AMBIGUOUS_SAC"


def test_section_393_coexistence_regression():
    """
    Coexistence Regression:
    Proves that Section 393 can coexist with multiple distinct statutory rates based on specific provision:
      - Section 393 + Technical Services -> 2%
      - Section 393 + Professional Services -> 10%
      - Section 393 + Purchase of Goods -> 0.1%
    """
    res_tech = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 6(iii)(D)(a)] - Technical Services",
        nature_of_payment="Technical Services",
        base_amount=100000.0,
        vendor_pan="AABCB1234F",
    )
    res_prof = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 6(iii)(D)(b)] - Professional Services",
        nature_of_payment="Professional Services",
        base_amount=100000.0,
        vendor_pan="AABCB1234F",
    )
    res_goods = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 8(ii)] - Purchase of Goods",
        nature_of_payment="Goods Supply",
        base_amount=100000.0,
        vendor_pan="AABCB1234F",
    )

    assert res_tech["rate"] == 2.0
    assert res_tech["tds_amount"] == 2000.0

    assert res_prof["rate"] == 10.0
    assert res_prof["tds_amount"] == 10000.0

    assert res_goods["rate"] == 0.1
    assert res_goods["tds_amount"] == 100.0

