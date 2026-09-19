"""
Targeted Regression Tests for P0 #1: Elimination of Unsafe TDS Fallback Rates.

Statutory Principles:
1. The backend must NEVER silently assume a TDS rate such as 2% or 10% when the
   TDS category is unknown, ambiguous, unsupported, or unresolved.
2. If category is missing/unknown/ambiguous:
   - rate is None
   - tds_amount is None
   - approval_status is 'REVIEW_REQUIRED'
   - tds_needs_review is True
3. Deterministic statutory rates for known categories are preserved:
   - Technical Services (FTS): 2.0%
   - Professional Services: 10.0%
   - Contractor (Individual/HUF): 1.0%
   - Contractor (Company/Firm): 2.0%
   - Purchase of Goods: 0.10%
   - Commission: 2.0%
4. Section 397(2) higher-rate logic (20% or 5%) applies ONLY after the underlying
   TDS applicability/category is actually resolved. It does NOT convert unknown categories to 20%.
5. HITL / Manual TDS values remain authoritative.
"""

import pytest
from app.services.tds_engine import (
    tds_engine,
    get_effective_tds_data,
    resolve_tds_tax_details,
)
from app.services.model_response_adapter import ModelResponseAdapter


# ==============================================================================
# 1. Unknown TDS Category -> rate is None, tds_amount is None, REVIEW_REQUIRED
# ==============================================================================

def test_unknown_tds_category_in_calculate_tds():
    """calculate_tds with completely unknown category must not assume 2% or 10%."""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision=None,
        nature_of_payment="Unspecified General Charge",
        base_amount=100000.0,
        vendor_pan="AABCB1234F",
    )
    assert res["applicable"] is True
    assert res["rate"] is None, f"Expected None rate for unknown category, got {res['rate']}"
    assert res["tds_amount"] is None
    assert res["tds_needs_review"] is True
    assert res["tds_conflict_code"] == "TDS_AMBIGUOUS_SAC"


def test_unknown_tds_category_in_get_effective_tds_data():
    """get_effective_tds_data with unknown category must not fallback to 2.0%."""
    accounting = {
        "tds_assessment": {
            "applicable": True,
            "section": "Unknown Section",
            "provision": "Unknown Provision",
            "nature_of_payment": "Miscellaneous Expense",
            "tds_base_amount": 50000.0,
            "tds_rate": None,
            "tds_amount": None,
        }
    }
    eff = get_effective_tds_data(accounting)
    assert eff["applicable"] is True
    assert eff["rate"] is None, f"Expected None rate, got {eff['rate']}"
    assert eff["tds_amount"] is None
    assert eff["approval_status"] == "REVIEW_REQUIRED"
    assert eff["tds_needs_review"] is True


# ==============================================================================
# 2. Ambiguous Category -> rate is None, tds_amount is None, REVIEW_REQUIRED
# ==============================================================================

def test_ambiguous_tds_category_in_calculate_tds():
    """calculate_tds with ambiguous category string must not default to 2% or 10%."""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Statutory Deduction",
        nature_of_payment="General Services & Processing",
        base_amount=75000.0,
        vendor_pan="AABCB1234F",
    )
    assert res["rate"] is None
    assert res["tds_amount"] is None
    assert res["tds_needs_review"] is True


# ==============================================================================
# 3. Missing Category / Bare Section -> rate is None, REVIEW_REQUIRED
# ==============================================================================

def test_missing_category_in_calculate_tds():
    """Missing section/provision/nature with applicable=True must require review."""
    res = tds_engine.calculate_tds(
        applicable=True,
        section=None,
        provision=None,
        nature_of_payment=None,
        base_amount=120000.0,
        vendor_pan="AABCB1234F",
    )
    assert res["rate"] is None
    assert res["tds_amount"] is None
    assert res["tds_needs_review"] is True


def test_missing_category_bare_section_393():
    """Bare Section 393 with no provision/nature must require review."""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision=None,
        nature_of_payment=None,
        base_amount=100000.0,
        vendor_pan="AABCB1234F",
    )
    assert res["rate"] is None
    assert res["tds_amount"] is None
    assert res["tds_needs_review"] is True
    assert res["tds_conflict_code"] == "TDS_AMBIGUOUS_SAC"


# ==============================================================================
# 4. Known Technical Service -> 2.0%
# ==============================================================================

def test_known_technical_service_rate():
    """Technical services must deterministically resolve to 2.0%."""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 6(iii)(D)(a)] - Fees for Technical Services (FTS)",
        nature_of_payment="Cloud hosting and DevOps engineering",
        base_amount=100000.0,
        vendor_pan="AABCB1234F",
    )
    assert res["applicable"] is True
    assert res["rate"] == 2.0
    assert res["tds_amount"] == 2000.0
    assert res["tds_needs_review"] is False


# ==============================================================================
# 5. Known Professional Service -> 10.0%
# ==============================================================================

def test_known_professional_service_rate():
    """Professional services must deterministically resolve to 10.0%."""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 6(iii)(D)(b)] - Professional Services & Fees",
        nature_of_payment="Legal advisory and representation",
        base_amount=100000.0,
        vendor_pan="AABCB1234F",
    )
    assert res["applicable"] is True
    assert res["rate"] == 10.0
    assert res["tds_amount"] == 10000.0
    assert res["tds_needs_review"] is False


# ==============================================================================
# 6. Known Contractor -> 1.0% (Ind/HUF) or 2.0% (Company/Firm)
# ==============================================================================

def test_known_contractor_rate_individual():
    """Contractor Individual/HUF (4th PAN char P) must resolve to 1.0%."""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 6(i)] - Payments to Contractors and Sub-contractors",
        nature_of_payment="Manpower supply and security staffing",
        base_amount=100000.0,
        vendor_pan="ABCPD1234F",  # 'P' as 4th char -> Individual
    )
    assert res["applicable"] is True
    assert res["rate"] == 1.0
    assert res["tds_amount"] == 1000.0
    assert res["tds_needs_review"] is False


def test_known_contractor_rate_company():
    """Contractor Company/Firm (4th PAN char C) must resolve to 2.0%."""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 6(i)] - Payments to Contractors and Sub-contractors",
        nature_of_payment="Manpower supply and security staffing",
        base_amount=100000.0,
        vendor_pan="AAACC1234F",  # 'C' at index 3 -> Company
    )
    assert res["applicable"] is True
    assert res["rate"] == 2.0
    assert res["tds_amount"] == 2000.0
    assert res["tds_needs_review"] is False


# ==============================================================================
# 7. Known Purchase of Goods -> 0.10%
# ==============================================================================

def test_known_purchase_of_goods_rate():
    """Purchase of Goods under Table 8(ii) / 194Q must resolve to 0.10%."""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 8(ii)] - Purchase of Goods",
        nature_of_payment="Purchase of steel raw materials",
        base_amount=500000.0,
        vendor_pan="AABCB1234F",
    )
    assert res["applicable"] is True
    assert res["rate"] == 0.10
    assert res["tds_amount"] == 500.0
    assert res["tds_needs_review"] is False


# ==============================================================================
# 8. Known Commission -> 2.0%
# ==============================================================================

def test_known_commission_rate():
    """Commission or brokerage under Table 1(ii) / 194H must resolve to 2.0%."""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 1(ii)] - Commission or Brokerage",
        nature_of_payment="Sales distribution commission",
        base_amount=100000.0,
        vendor_pan="AABCB1234F",
    )
    assert res["applicable"] is True
    assert res["rate"] == 2.0
    assert res["tds_amount"] == 2000.0
    assert res["tds_needs_review"] is False


# ==============================================================================
# 9. Existing PAN Higher-Rate Logic applies ONLY to resolved categories
# ==============================================================================

def test_pan_higher_rate_not_blanket_applied_to_unresolved_category():
    """
    Missing PAN on an UNRESOLVED category must NOT blindly become 20%.
    It must require review because category classification is prerequisite.
    """
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision=None,
        nature_of_payment=None,
        base_amount=100000.0,
        vendor_pan=None,  # Missing PAN
    )
    assert res["applicable"] is True
    assert res["rate"] is None, "Must NOT blanket apply 20% to an unclassified transaction"
    assert res["tds_amount"] is None
    assert res["tds_needs_review"] is True


def test_pan_higher_rate_applied_to_resolved_category():
    """Missing PAN on a RESOLVED category correctly triggers Section 397(2)."""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 6(iii)(D)(a)] - Fees for Technical Services (FTS)",
        nature_of_payment="Software development",
        base_amount=100000.0,
        vendor_pan=None,  # Missing PAN
    )
    assert res["applicable"] is True
    assert res["rate"] == 20.0
    assert res["tds_amount"] == 20000.0
    assert "Section 397(2)" in res["reason"]


# ==============================================================================
# 10. HITL / Manual TDS Values Remain Authoritative
# ==============================================================================

def test_hitl_manual_tds_values_authoritative():
    """Approved HITL TDS values must strictly override statutory defaults."""
    accounting = {
        "tds_assessment": {
            "applicable": True,
            "approved_tds_section": "Section 393(1) [Table Sl. No. 6(i)]",
            "approved_nature_of_payment": "Custom Contractor Rate Approved",
            "approved_tds_rate": 1.5,  # Non-standard approved HITL rate
            "tds_base_amount": 100000.0,
            "final_tds_amount": 1500.0,
            "approval_status": "APPROVED",
            "is_approved": True,
        }
    }
    eff = get_effective_tds_data(accounting)
    assert eff["applicable"] is True
    assert eff["rate"] == 1.5
    assert eff["tds_amount"] == 1500.0
    assert eff["is_approved"] is True
    assert eff["approval_status"] == "APPROVED"


def test_model_response_adapter_unresolved_tds():
    """ModelResponseAdapter with unresolvable TDS category must flag review required without guessed rate."""
    raw_model_json = {
        "invoice_details": {"invoice_number": "INV-TEST-001"},
        "vendor_details": {"vendor_pan": "AABCB1234F"},
        "financial_details": {"subtotal": 50000.0, "total_amount": 59000.0},
        "tds_support": {
            "applicable": True,
            "nature_of_payment": "General Operational Fee",
            "provision_candidate": "Section 393",
            "rate_candidate": None,
            "base_candidate": 50000.0,
            "requires_backend_validation": True,
        },
        "line_items": [
            {
                "description": "General Operational Surcharge",
                "taxable_amount": 50000.0,
                "hsn_sac": "999999",
            }
        ],
    }
    norm = ModelResponseAdapter.normalize_model_response(raw_model_json)
    tds = norm["normalized_accounting"]["tds_assessment"]
    assert tds["tds_applicable"] is True
    assert tds["rate"] is None, f"Model adapter must not invent rate, got {tds['rate']}"
    assert tds["proposed_tds_amount"] is None
    assert tds["tds_needs_review"] is True
    assert tds["approval_status"] == "REVIEW_REQUIRED"
