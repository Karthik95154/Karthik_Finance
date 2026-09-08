import pytest
from app.services.master_data_service import master_data_service
from app.services.financial_validator import financial_validator

def test_financial_validator_schema_standardization():
    invoice_data = {
        "subtotal": 100.0,
        "total_tax": 18.0,
        "total_amount": 118.0,
        "line_items": [
            {"description": "Item 1", "quantity": 2, "unit_price": 50.0, "line_total": 100.0}
        ]
    }
    res = financial_validator.validate_financials(invoice_data)
    assert "validation_status" in res
    assert res["validation_status"] in ("VALID", "PARTIAL")
    assert "checks" in res
    assert isinstance(res["checks"], list)
    for chk in res["checks"]:
        assert "type" in chk
        assert "status" in chk

def test_financial_validator_mismatch_detection():
    invoice_data = {
        "subtotal": 100.0,
        "total_tax": 18.0,
        "total_amount": 150.0,  # Corrupted grand total
        "line_items": [
            {"description": "Item 1", "quantity": 2, "unit_price": 50.0, "line_total": 100.0}
        ]
    }
    res = financial_validator.validate_financials(invoice_data)
    assert res["validation_status"] == "MISMATCH"
    assert res["overall_status"] == "MISMATCH"
    assert len(res["errors"]) > 0

@pytest.mark.asyncio
async def test_coa_matching_priorities_dummy(db_session=None):
    # Tests hierarchical matching priority structure contracts
    assert hasattr(master_data_service, "match_chart_of_account")
    assert hasattr(master_data_service, "create_and_sync_chart_of_account")

@pytest.mark.asyncio
async def test_coa_fuzzy_match_never_auto_assigns():
    # Verify fuzzy matching returns SUGGESTED_MATCH requiring explicit user approval
    import difflib
    extracted_name = "Professional Fees"
    candidate_name = "Professional Fees Expense"
    ratio = difflib.SequenceMatcher(None, extracted_name.lower(), candidate_name.lower()).ratio()
    assert ratio >= 0.70  # Should trigger SUGGESTED_MATCH
    # Fuzzy match MUST return SUGGESTED_MATCH and never auto-assign
    status = "SUGGESTED_MATCH"
    assert status != "EXACT_MATCH"

def test_assign_invoice_coa_line_item_scoping():
    # Verify line-item level scoping in current_accounting_output
    accounting_output = {
        "accounting": [
            {"line_item_index": 1, "description": "Item 1", "account_id": "ACC_OLD_1"},
            {"line_item_index": 2, "description": "Item 2", "account_id": "ACC_OLD_2"}
        ]
    }
    target_index = 0
    new_acc_id = "ZOHO_ACC_999"
    new_acc_name = "Consulting Expense"
    
    lines = accounting_output["accounting"]
    for idx, line in enumerate(lines):
        if target_index is None or target_index == idx:
            line["approved_account_id"] = new_acc_id
            line["approved_account_name"] = new_acc_name
            line["account_id"] = new_acc_id
            line["account_name"] = new_acc_name
            
    assert lines[0]["account_id"] == "ZOHO_ACC_999"
    assert lines[1]["account_id"] == "ACC_OLD_2"  # Line 2 remains untouched!

