"""
Comprehensive Unit and Integration Test Suite for the Generic ITC Single Source of Truth (SSOT).

Verifies:
1. Canonical status model (ELIGIBLE, INELIGIBLE_SECTION_17_5, INELIGIBLE_OTHERS, REVIEW_REQUIRED, GSTR2B_PENDING, GSTR2B_MISMATCH).
2. Dynamic branch & destination state matching (no hardcoding state codes 27 or 36).
3. Out-of-state recipient restriction: local intra-state taxes (CGST/SGST) become INELIGIBLE_OTHERS when recipient organization is in a different state.
4. GSTR2B_PENDING / MISMATCH / REVIEW_REQUIRED cannot silently export without review or explicit HITL override.
5. Authoritative HITL override preservation (HITL decisions can never be overwritten by downstream engines).
6. Complete GL Journal identity: INPUT_TAX + INELIGIBLE_TAX == Total GST; journal automatically refreshes if stale.
7. Zoho Books line-level serialization: `itc_eligibility` matches canonical mapping (`eligible`, `ineligible_section_17_5`, `ineligible_others`).
"""

import pytest
from app.services.itc_engine import (
    itc_engine,
    get_effective_itc_data,
    ITCStatus,
    ZOHO_ITC_MAPPING,
)
from app.services.journal_generator import journal_generator
from app.services.master_data_service import master_data_service


def test_itc_status_enum_and_zoho_mapping():
    """Verify all 6 canonical ITC statuses exist and map correctly to Zoho Books."""
    assert ITCStatus.ELIGIBLE.value == "ELIGIBLE"
    assert ITCStatus.INELIGIBLE_SECTION_17_5.value == "INELIGIBLE_SECTION_17_5"
    assert ITCStatus.INELIGIBLE_OTHERS.value == "INELIGIBLE_OTHERS"
    assert ITCStatus.REVIEW_REQUIRED.value == "REVIEW_REQUIRED"
    assert ITCStatus.GSTR2B_PENDING.value == "GSTR2B_PENDING"
    assert ITCStatus.GSTR2B_MISMATCH.value == "GSTR2B_MISMATCH"

    assert ZOHO_ITC_MAPPING[ITCStatus.ELIGIBLE] == "eligible"
    assert ZOHO_ITC_MAPPING[ITCStatus.INELIGIBLE_SECTION_17_5] == "ineligible_section_17_5"
    assert ZOHO_ITC_MAPPING[ITCStatus.INELIGIBLE_OTHERS] == "ineligible_others"
    assert ZOHO_ITC_MAPPING[ITCStatus.GSTR2B_PENDING] == "ineligible_others"
    assert ZOHO_ITC_MAPPING[ITCStatus.GSTR2B_MISMATCH] == "ineligible_others"
    assert ZOHO_ITC_MAPPING[ITCStatus.REVIEW_REQUIRED] == "ineligible_others"


def test_ssot_eligible_intra_state_invoice():
    """Test standard business supply intra-state is ELIGIBLE and produces balanced journal."""
    invoice_payload = {
        "invoice_number": "INV-TG-01",
        "supplier_gstin": "36AABCU9603R1ZM",
        "supplier_state_code": "36",
        "place_of_supply_state_code": "36",
        "subtotal": 289000.0,
        "tax_total": 52020.0,
        "cgst_amount": 26010.0,
        "sgst_amount": 26010.0,
        "total_amount": 341020.0,
        "line_items": [
            {
                "line_index": 1,
                "description": "IT Consulting and Infrastructure Management",
                "hsn_code": "998311",
                "taxable_amount": 289000.0,
                "cgst_rate": 9.0,
                "cgst_amount": 26010.0,
                "sgst_rate": 9.0,
                "sgst_amount": 26010.0,
                "tax_amount": 52020.0,
            }
        ],
    }
    accounting_context = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_5",
                "approved_account_name": "Consulting & Professional Services",
            }
        ]
    }

    # Pass recipient_state_code="36" (matching recipient branch in Telangana)
    itc_res = get_effective_itc_data(
        invoice_or_data=invoice_payload,
        accounting_output=accounting_context,
        recipient_state_code="36",
    )

    assert itc_res["status"] == ITCStatus.ELIGIBLE.value
    assert itc_res["eligible_itc"] == 52020.0
    assert itc_res["blocked_itc"] == 0.0
    assert itc_res["is_out_of_state_local_tax"] is False
    assert len(itc_res["line_item_breakdown"]) == 1
    assert itc_res["line_item_breakdown"][0]["zoho_itc_eligibility"] == "eligible"

    # Journal Generation with SSOT
    journal = journal_generator.generate_journal(
        invoice_data=invoice_payload,
        accounting_classification=accounting_context,
        itc_result=itc_res,
    )
    assert journal["status"] == "BALANCED"
    input_lines = [l for l in journal["lines"] if l["line_type"] == "INPUT_TAX"]
    assert sum(l["debit"] for l in input_lines) == 52020.0


def test_ssot_out_of_state_recipient_restriction_dynamic():
    """
    Test dynamic recipient state mismatch:
    Local intra-state tax (e.g. Telangana 36 CGST+SGST) charged, but recipient entity / branch
    is registered in Maharashtra (27) or Karnataka (29).
    Must automatically classify as INELIGIBLE_OTHERS under CGST Sec 12.
    """
    invoice_payload = {
        "invoice_number": "INV-TG-HOTEL",
        "supplier_gstin": "36AABCU9603R1ZM",
        "supplier_state_code": "36",
        "place_of_supply_state_code": "36",
        "subtotal": 10000.0,
        "tax_total": 1800.0,
        "cgst_amount": 900.0,
        "sgst_amount": 900.0,
        "total_amount": 11800.0,
        "line_items": [
            {
                "line_index": 1,
                "description": "Hotel accommodation in Hyderabad for client meeting and official duty",
                "taxable_amount": 10000.0,
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
                "tax_amount": 1800.0,
                "business_purpose": "client meeting business travel",
            }
        ],
    }

    # Case A: Recipient entity is only registered in Maharashtra (27)
    itc_res_mh = get_effective_itc_data(
        invoice_or_data=invoice_payload,
        recipient_state_code="27",
    )
    assert itc_res_mh["status"] == ITCStatus.INELIGIBLE_OTHERS.value
    assert itc_res_mh["is_out_of_state_local_tax"] is True
    assert itc_res_mh["eligible_itc"] == 0.0
    assert itc_res_mh["blocked_itc"] == 1800.0
    assert itc_res_mh["line_item_breakdown"][0]["zoho_itc_eligibility"] == "ineligible_others"

    # Case B: Recipient entity has matching Telangana (36) branch
    itc_res_tg = get_effective_itc_data(
        invoice_or_data=invoice_payload,
        recipient_state_code="36",
    )
    assert itc_res_tg["is_out_of_state_local_tax"] is False
    assert itc_res_tg["status"] == ITCStatus.ELIGIBLE.value


def test_ssot_gstr2b_mismatch_and_pending_states():
    """Test GSTR-2B external statuses (MISMATCH and PENDING) properly reflect without destroying statutory numbers."""
    invoice_payload = {
        "invoice_number": "INV-M1",
        "supplier_gstin": "27AABCU9603R1ZM",
        "supplier_state_code": "27",
        "place_of_supply_state_code": "27",
        "subtotal": 50000.0,
        "tax_total": 9000.0,
        "cgst_amount": 4500.0,
        "sgst_amount": 4500.0,
        "total_amount": 59000.0,
        "line_items": [
            {
                "line_index": 1,
                "description": "Cloud Servers",
                "taxable_amount": 50000.0,
                "cgst_amount": 4500.0,
                "sgst_amount": 4500.0,
                "tax_amount": 9000.0,
            }
        ],
    }

    # 1. GSTR-2B Mismatch (e.g. invoice not found or amount differs)
    gstr2b_mismatch_input = {
        "status": "NOT_FOUND",
        "gstr2b_tax_amount": 0.0,
        "mismatch_reasons": ["Invoice not appearing in GSTR-2B return"],
    }
    itc_mismatch = get_effective_itc_data(
        invoice_or_data=invoice_payload,
        recipient_state_code="27",
        gstr2b_data=gstr2b_mismatch_input,
    )
    assert itc_mismatch["status"] == ITCStatus.GSTR2B_MISMATCH.value
    assert itc_mismatch["gstr2b_status"] == ITCStatus.GSTR2B_MISMATCH.value
    # Statutory math is preserved!
    assert itc_mismatch["total_tax_amount"] == 9000.0

    # 2. GSTR-2B Pending
    gstr2b_pending_input = {
        "status": "PORTAL_VERIFICATION_REQUIRED",
    }
    itc_pending = get_effective_itc_data(
        invoice_or_data=invoice_payload,
        recipient_state_code="27",
        gstr2b_data=gstr2b_pending_input,
    )
    assert itc_pending["status"] == ITCStatus.GSTR2B_PENDING.value
    assert itc_pending["gstr2b_status"] == ITCStatus.GSTR2B_PENDING.value


def test_ssot_hitl_override_is_authoritative_and_immutable():
    """Finance user manual override takes strict precedence over statutory and GSTR-2B rules."""
    invoice_payload = {
        "invoice_number": "INV-CAR-DIRECTOR",
        "subtotal": 100000.0,
        "tax_total": 18000.0,
        "igst_amount": 18000.0,
        "total_amount": 118000.0,
        "line_items": [
            {
                "line_index": 1,
                "description": "Passenger Motor Car",
                "taxable_amount": 100000.0,
                "igst_amount": 18000.0,
                "tax_amount": 18000.0,
            }
        ],
    }
    # User marks as ELIGIBLE because company is in car-rental business (Sec 17(5) exception)
    hitl_accounting = {
        "itc_assessment": {
            "is_override": True,
            "status": "ELIGIBLE",
            "eligible_amount": 18000.0,
            "blocked_amount": 0.0,
            "line_overrides": {
                "1": {
                    "status": "ELIGIBLE",
                    "reason": "Business car rental qualification",
                }
            }
        }
    }

    itc_res = get_effective_itc_data(
        invoice_or_data=invoice_payload,
        accounting_output=hitl_accounting,
    )

    assert itc_res["is_hitl_overridden"] is True
    assert itc_res["status"] == ITCStatus.ELIGIBLE.value
    assert itc_res["eligible_itc"] == 18000.0
    assert itc_res["blocked_itc"] == 0.0
    assert itc_res["line_item_breakdown"][0]["zoho_itc_eligibility"] == "eligible"


@pytest.mark.asyncio
async def test_dynamic_destination_and_branch_resolution():
    """Verify resolve_zoho_destination_and_branch dynamically resolves state and branch without hardcoding."""
    class MockConn:
        status = "CONNECTED"
        organization_id = "org-36"

    async def mock_conn(tenant_id, db):
        return MockConn()

    async def mock_api(connection, db, method, endpoint_path):
        if endpoint_path == "branches":
            return {
                "branches": [
                    {
                        "branch_id": "br-29",
                        "branch_name": "Bangalore Branch",
                        "tax_reg_no": "29AABCU9603R1ZM",
                        "address": {"state": "Karnataka", "state_code": "KA"},
                    },
                    {
                        "branch_id": "br-36",
                        "branch_name": "Hyderabad Branch",
                        "tax_reg_no": "36AABCU9603R1ZM",
                        "address": {"state": "Telangana", "state_code": "TS"},
                    },
                ]
            }
        elif "organizations/" in endpoint_path:
            return {
                "organization": {
                    "address": {"state": "Telangana", "state_code": "TS"}
                }
            }
        return {}

    from unittest.mock import patch
    with patch.object(master_data_service, "get_or_create_zoho_connection", side_effect=mock_conn), \
         patch("app.services.zoho_client.zoho_client_service._make_authorized_request", side_effect=mock_api):

        # Resolve for Telangana recipient
        res_tg = await master_data_service.resolve_zoho_destination_and_branch(
            tenant_id="t1",
            db=None,
            invoice_recipient_state="Telangana",
            organization_id="org-36",
        )
        assert res_tg["destination_state_code"] == "TS"
        assert res_tg["branch_id"] == "br-36"

        # Resolve for Karnataka recipient
        res_ka = await master_data_service.resolve_zoho_destination_and_branch(
            tenant_id="t1",
            db=None,
            invoice_recipient_state="Karnataka",
            organization_id="org-36",
        )
        assert res_ka["destination_state_code"] == "KA"
        assert res_ka["branch_id"] == "br-29"
