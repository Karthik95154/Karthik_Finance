"""
Regression tests for Section 397(2) Missing/Invalid PAN Higher-Rate TDS Logic.
Under Income-tax Act, 2025 Section 397(2):
When the deductee fails to furnish a valid PAN, TDS is deducted at the higher applicable rate:
  - Section 393(1), Table Sl. No. 8(ii) — Purchase of Goods: 5%
  - Section 393(1), Table Sl. No. 8(v) — E-commerce: 5%
  - Other applicable TDS categories: 20%
Valid PAN preserves the normal statutory rate.

Hardened Category Matching:
  - The 5% exception depends STRICTLY on canonical category resolution (Table 8(ii) and Table 8(v)).
  - Descriptions mentioning "goods", "equipment", "online", "purchase" do NOT trigger 5%
    if the transaction resolves to Technical Services, Professional Services, Contractor, Rent, etc.
"""

import pytest
from app.services.tds_engine import tds_engine, resolve_tds_tax_details


def test_1_section_393_exact_table_8_ii_purchase_of_goods_pan_missing():
    """TEST 1: Section 393 + exact Table 8(ii) Purchase of Goods / PAN missing -> 5%"""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 8(ii)] - Purchase of Goods",
        nature_of_payment="Purchase of Goods",
        base_amount=100000.0,
        vendor_pan=None,
    )
    assert res["applicable"] is True
    assert res["rate"] == 5.0
    assert res["tds_amount"] == 5000.0
    assert res["pan_valid"] is False
    assert "Section 397(2)" in res["reason"]


def test_2_section_393_exact_table_8_ii_purchase_of_goods_pan_invalid():
    """TEST 2: Section 393 + exact Table 8(ii) Purchase of Goods / PAN invalid -> 5%"""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 8(ii)] - Purchase of Goods",
        nature_of_payment="Purchase of Goods",
        base_amount=100000.0,
        vendor_pan="INVALID_PAN_123",
    )
    assert res["applicable"] is True
    assert res["rate"] == 5.0
    assert res["tds_amount"] == 5000.0
    assert res["pan_valid"] is False
    assert "Section 397(2)" in res["reason"]


def test_3_section_393_exact_table_8_v_ecommerce_pan_missing():
    """TEST 3: Section 393 + exact Table 8(v) E-commerce / PAN missing -> 5%"""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 8(v)] - E-commerce Participant",
        nature_of_payment="E-commerce Participant Supply",
        base_amount=100000.0,
        vendor_pan=None,
    )
    assert res["applicable"] is True
    assert res["rate"] == 5.0
    assert res["tds_amount"] == 5000.0
    assert res["pan_valid"] is False
    assert "Section 397(2)" in res["reason"]


def test_4_section_393_exact_table_8_v_ecommerce_pan_invalid():
    """TEST 4: Section 393 + exact Table 8(v) E-commerce / PAN invalid -> 5%"""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 8(v)] - E-commerce Participant",
        nature_of_payment="E-commerce Participant Supply",
        base_amount=100000.0,
        vendor_pan="INVALID_PAN_123",
    )
    assert res["applicable"] is True
    assert res["rate"] == 5.0
    assert res["tds_amount"] == 5000.0
    assert res["pan_valid"] is False
    assert "Section 397(2)" in res["reason"]


def test_5_section_393_only_pan_missing_unresolved():
    """
    TEST 5: Section 393 only / PAN missing
      -> NOT 5%
      -> NOT 20% unless category is otherwise resolved
      -> REVIEW_REQUIRED / unresolved
    """
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision=None,
        nature_of_payment=None,
        base_amount=100000.0,
        vendor_pan=None,
    )
    assert res["applicable"] is True
    assert res["rate"] is None
    assert res["tds_amount"] is None
    assert res["pan_valid"] is False
    assert res["tds_needs_review"] is True
    assert res["tds_conflict_code"] == "TDS_AMBIGUOUS_SAC"


def test_6_description_contains_goods_but_resolves_to_technical_services_pan_invalid():
    """
    TEST 6: Description contains "goods" but category resolves to Technical Services
    PAN invalid -> 20% (NOT 5%)
    """
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 6(iii)(D)(a)] - Fees for Technical Services (FTS)",
        nature_of_payment="Technical service for goods processing and IT integration",
        base_amount=50000.0,
        vendor_pan="INVALID_PAN_999",
    )
    assert res["applicable"] is True
    assert res["rate"] == 20.0
    assert res["tds_amount"] == 10000.0
    assert res["pan_valid"] is False
    assert "Section 397(2)" in res["reason"]


def test_7_description_contains_goods_but_resolves_to_professional_services_pan_invalid():
    """
    TEST 7: Description contains "goods" but category resolves to Professional Services
    PAN invalid -> 20% (NOT 5%)
    """
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 6(iii)(D)(b)] - Professional Services & Fees",
        nature_of_payment="Professional legal consulting involving consumer goods compliance",
        base_amount=50000.0,
        vendor_pan="INVALID_PAN_999",
    )
    assert res["applicable"] is True
    assert res["rate"] == 20.0
    assert res["tds_amount"] == 10000.0
    assert res["pan_valid"] is False
    assert "Section 397(2)" in res["reason"]


def test_8_description_contains_goods_but_resolves_to_contractor_pan_invalid():
    """
    TEST 8: Description contains "goods" but category resolves to Contractor
    PAN invalid -> 20% (NOT 5%)
    """
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 6(i)] - Payments to Contractors and Sub-contractors",
        nature_of_payment="Contractor supplying goods logistics and manpower",
        base_amount=100000.0,
        vendor_pan="INVALID_PAN_999",
    )
    assert res["applicable"] is True
    assert res["rate"] == 20.0
    assert res["tds_amount"] == 20000.0
    assert res["pan_valid"] is False
    assert "Section 397(2)" in res["reason"]


def test_9_description_contains_equipment_resolves_to_rent_pan_invalid():
    """
    TEST 9: Description contains "equipment" / category resolves to Rent Plant/Machinery
    PAN invalid -> 20% (NOT 5%)
    """
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 2(ii)] - Rent for Plant, Machinery or Equipment",
        nature_of_payment="Rent of heavy industrial equipment",
        base_amount=100000.0,
        vendor_pan="INVALID_PAN_999",
    )
    assert res["applicable"] is True
    assert res["rate"] == 20.0
    assert res["tds_amount"] == 20000.0
    assert res["pan_valid"] is False
    assert "Section 397(2)" in res["reason"]


def test_10_description_contains_online_not_ecommerce_pan_invalid():
    """
    TEST 10: Description contains "online" but category is not ECOMMERCE (e.g. online technical training / FTS)
    PAN invalid -> 20% (NOT 5%)
    """
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 6(iii)(D)(a)] - Fees for Technical Services (FTS)",
        nature_of_payment="Online cloud computing and technical service portal",
        base_amount=50000.0,
        vendor_pan="INVALID_PAN_999",
    )
    assert res["applicable"] is True
    assert res["rate"] == 20.0
    assert res["tds_amount"] == 10000.0
    assert res["pan_valid"] is False
    assert "Section 397(2)" in res["reason"]


def test_11_exact_purchase_of_goods_valid_pan():
    """TEST 11: Exact Purchase of Goods category + valid PAN -> normal statutory rate (0.1%), not 5%"""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 8(ii)] - Purchase of Goods",
        nature_of_payment="Purchase of Goods",
        base_amount=100000.0,
        vendor_pan="AABCB1234F",
    )
    assert res["applicable"] is True
    assert res["rate"] == 0.1
    assert res["tds_amount"] == 100.0
    assert res["pan_valid"] is True


def test_12_exact_ecommerce_valid_pan():
    """TEST 12: Exact E-commerce category + valid PAN -> normal statutory rate (0.1%), not 5%"""
    res = tds_engine.calculate_tds(
        applicable=True,
        section="Section 393",
        provision="Section 393(1) [Table Sl. No. 8(v)] - E-commerce Participant",
        nature_of_payment="E-commerce Participant Supply",
        base_amount=100000.0,
        vendor_pan="AABCB1234F",
    )
    assert res["applicable"] is True
    assert res["rate"] == 0.1
    assert res["tds_amount"] == 100.0
    assert res["pan_valid"] is True


def test_canonical_resolution_category_key():
    """Test that resolve_tds_tax_details returns authoritative category_key."""
    det_goods = resolve_tds_tax_details("Section 393", "Section 393(1) [Table Sl. No. 8(ii)] - Purchase of Goods", "Purchase of Goods")
    assert det_goods["category_key"] == "PURCHASE_OF_GOODS"

    det_ecom = resolve_tds_tax_details("Section 393", "Section 393(1) [Table Sl. No. 8(v)] - E-commerce Participant", "E-commerce")
    assert det_ecom["category_key"] == "ECOMMERCE"

    det_tech = resolve_tds_tax_details("Section 393", "Section 393(1) [Table Sl. No. 6(iii)(D)(a)] - Fees for Technical Services (FTS)", "FTS")
    assert det_tech["category_key"] == "TECHNICAL_SERVICES"

    det_prof = resolve_tds_tax_details("Section 393", "Section 393(1) [Table Sl. No. 6(iii)(D)(b)] - Professional Services & Fees", "Legal")
    assert det_prof["category_key"] == "PROFESSIONAL_SERVICES"

    det_bare = resolve_tds_tax_details("Section 393", None, None)
    assert det_bare["category_key"] is None
