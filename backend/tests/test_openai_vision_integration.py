import pytest
from app.services.ai_service import (
    ai_service,
    FIXED_JSON_STRUCTURE,
    get_accounting_knowledge_base,
    decode_invoice_to_pages,
)
from app.services.model_response_adapter import ModelResponseAdapter


def test_fixed_json_structure_keys():
    """Verify that all 13 top-level keys in the fixed contract exist."""
    expected_keys = {
        "invoice_details",
        "vendor_details",
        "customer_details",
        "line_items",
        "financial_details",
        "gst_support",
        "tds_support",
        "tcs_support",
        "itc_support",
        "coa_support",
        "gl_support",
        "validation",
        "review_flags",
    }
    assert set(FIXED_JSON_STRUCTURE.keys()) == expected_keys


def test_accounting_kb_loaded():
    """Verify that the accounting knowledge base is read and non-empty."""
    kb_text = get_accounting_knowledge_base()
    assert isinstance(kb_text, str)
    assert len(kb_text) > 1000
    assert "Indian Invoice Accounting" in kb_text or "Income-tax Act" in kb_text


def test_prompt_includes_tds_2026_instructions():
    """Verify that user and system prompts enforce 2026 TDS law rules."""
    sys_prompt = ai_service._build_system_prompt()
    user_prompt = ai_service._build_user_prompt("sample_invoice.pdf", [
        {"account_id": "ACC_1", "account_name": "Consulting Services", "account_type": "expense"}
    ])
    assert "Income-tax Act, 2025" in sys_prompt
    assert "Income-tax Act, 1961" in sys_prompt
    assert "01-APR-2026" in sys_prompt
    assert "provision_candidate" in sys_prompt
    assert "legacy_provision_reference" in sys_prompt
    assert "cumulative_vendor_data_required" in sys_prompt or "cumulative" in sys_prompt.lower()
    assert "ACC_1" in user_prompt


def test_json_extraction_and_fallback():
    """Verify lightweight JSON parsing and key integrity."""
    raw_response = """
    ```json
    {
      "invoice_details": {"invoice_number": "INV-2026-99"},
      "vendor_details": {"vendor_name": "ABC Corp", "vendor_gstin": "29ABCDE1234F1ZH"},
      "customer_details": {"customer_name": "XYZ Corp"},
      "line_items": [{"line_index": 1, "description": "Tech Support", "taxable_amount": 1000.0}],
      "financial_details": {"subtotal": 1000.0, "total_amount": 1180.0},
      "gst_support": {"supply_type_candidate": "INTRA_STATE"},
      "tds_support": {
        "tds_applicable_candidate": true,
        "law_version_candidate": "Income-tax Act, 2025",
        "provision_candidate": "Section 393 - Table Item for Technical Services",
        "legacy_provision_reference": "Section 194J",
        "rate_candidate": 2.0,
        "base_candidate": 1000.0
      },
      "tcs_support": {"tcs_applicable_candidate": false},
      "itc_support": {"candidate": "ELIGIBLE"},
      "coa_support": {"line_matches": []},
      "gl_support": {"requires_backend_generation": true},
      "validation": {"total_mismatch": false},
      "review_flags": []
    }
    ```
    """
    parsed = ai_service._extract_and_validate_json(raw_response)
    assert parsed["invoice_details"]["invoice_number"] == "INV-2026-99"
    assert parsed["tds_support"]["law_version_candidate"] == "Income-tax Act, 2025"
    assert parsed["tds_support"]["provision_candidate"] == "Section 393 - Table Item for Technical Services"
    assert parsed["tds_support"]["legacy_provision_reference"] == "Section 194J"

    # Normalize through ModelResponseAdapter
    normalized = ModelResponseAdapter.normalize_model_response(parsed)
    data = normalized["normalized_data"]
    acct = normalized["normalized_accounting"]

    assert data["invoice_number"] == "INV-2026-99"
    assert data["vendor_pan"] == "ABCDE1234F"  # Extracted from GSTIN
    assert acct["tds_assessment"]["law_version"] == "Income-tax Act, 2025"
    assert acct["tds_assessment"]["provision"] == "Section 393 - Table Item for Technical Services"
    assert acct["tds_assessment"]["legacy_provision_reference"] == "Section 194J"
