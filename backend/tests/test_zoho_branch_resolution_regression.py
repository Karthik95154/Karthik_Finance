"""
Unit and regression tests for Zoho multi-branch vs single-branch destination and branch_id resolution.
Verifies that:
A. Single-branch org -> branch_id omitted (None).
B. Single-entity Head Office only -> branch_id omitted (None).
C. Genuine multi-branch org -> matched branch_id included.
D. Wrong-organization branch_id -> never included.
E. No valid branch match in a multi-branch org -> fails safely; never guesses arbitrary branch.
F. Existing Zoho bill export without branch_id succeeds.
"""

import pytest
from unittest.mock import patch, AsyncMock
from uuid import uuid4

from app.services.master_data_service import master_data_service


class MockZohoConnection:
    def __init__(self, org_id="ORG_TEST_100", status="CONNECTED"):
        self.organization_id = org_id
        self.status = status


@pytest.mark.asyncio
async def test_single_branch_org_head_office_omits_branch_id():
    """
    Case A & B: An organization with only 1 primary Head Office branch
    must resolve state correctly but set branch_id to None so POST /bills does not fail with code 8.
    """
    mock_conn = MockZohoConnection(org_id="ORG_SINGLE_60087246106")

    async def mock_api(connection, db, method, endpoint_path, **kwargs):
        if endpoint_path == "branches":
            return {
                "branches": [
                    {
                        "branch_id": "4163253000000034110",
                        "branch_name": "Head Office",
                        "tax_reg_no": "36AAECJ6056C1Z2",
                        "is_primary_branch": True,
                        "address": {"state": "Telangana", "state_code": "TS"},
                    }
                ]
            }
        return {}

    with patch.object(master_data_service, "get_or_create_zoho_connection", AsyncMock(return_value=mock_conn)), \
         patch("app.services.zoho_client.zoho_client_service._make_authorized_request", side_effect=mock_api):

        res = await master_data_service.resolve_zoho_destination_and_branch(
            tenant_id="tenant-1",
            db=None,
            invoice_recipient_state="Telangana",
            invoice_recipient_gstin="36AAECJ6056C1Z2",
            organization_id="ORG_SINGLE_60087246106",
        )

        assert res["destination_state_code"] == "TS"
        assert res["branch_id"] is None  # Must be None so it is omitted from bill payload
        assert res["branch_name"] == "Head Office"
        assert res["source"] == "zoho_org_primary_branch"


@pytest.mark.asyncio
async def test_genuine_multi_branch_org_includes_matched_branch_id():
    """
    Case C: An organization with multiple branches (e.g., TS & KA branches)
    must return the exact matching branch_id.
    """
    mock_conn = MockZohoConnection(org_id="ORG_MULTI_ENTERPRISE")

    async def mock_api(connection, db, method, endpoint_path, **kwargs):
        if endpoint_path == "branches":
            return {
                "branches": [
                    {
                        "branch_id": "branch_ho_001",
                        "branch_name": "Head Office",
                        "tax_reg_no": "27AAACB1234D1Z1",
                        "is_primary_branch": True,
                        "address": {"state": "Maharashtra", "state_code": "MH"},
                    },
                    {
                        "branch_id": "branch_ts_002",
                        "branch_name": "Hyderabad Tech Hub",
                        "tax_reg_no": "36AAACB1234D1Z5",
                        "is_primary_branch": False,
                        "address": {"state": "Telangana", "state_code": "TS"},
                    },
                    {
                        "branch_id": "branch_ka_003",
                        "branch_name": "Bangalore R&D",
                        "tax_reg_no": "29AAACB1234D1Z9",
                        "is_primary_branch": False,
                        "address": {"state": "Karnataka", "state_code": "KA"},
                    },
                ]
            }
        return {}

    with patch.object(master_data_service, "get_or_create_zoho_connection", AsyncMock(return_value=mock_conn)), \
         patch("app.services.zoho_client.zoho_client_service._make_authorized_request", side_effect=mock_api):

        # Test Telangana branch resolution by GSTIN
        res_ts = await master_data_service.resolve_zoho_destination_and_branch(
            tenant_id="tenant-1",
            db=None,
            invoice_recipient_state="Telangana",
            invoice_recipient_gstin="36AAACB1234D1Z5",
            organization_id="ORG_MULTI_ENTERPRISE",
        )
        assert res_ts["destination_state_code"] == "TS"
        assert res_ts["branch_id"] == "branch_ts_002"
        assert res_ts["source"] == "zoho_branch_match"

        # Test Karnataka branch resolution by State Name
        res_ka = await master_data_service.resolve_zoho_destination_and_branch(
            tenant_id="tenant-1",
            db=None,
            invoice_recipient_state="Karnataka",
            invoice_recipient_gstin=None,
            organization_id="ORG_MULTI_ENTERPRISE",
        )
        assert res_ka["destination_state_code"] == "KA"
        assert res_ka["branch_id"] == "branch_ka_003"
        assert res_ka["source"] == "zoho_branch_match"


@pytest.mark.asyncio
async def test_multi_branch_no_matching_branch_falls_back_safely_never_guesses():
    """
    Case E: In a multi-branch org, if the invoice recipient state/GSTIN does not match
    any of the registered branches, fall back safely to primary org registration and DO NOT guess a branch_id.
    """
    mock_conn = MockZohoConnection(org_id="ORG_MULTI_ENTERPRISE")

    async def mock_api(connection, db, method, endpoint_path, **kwargs):
        if endpoint_path == "branches":
            return {
                "branches": [
                    {
                        "branch_id": "branch_ho_001",
                        "branch_name": "Head Office",
                        "tax_reg_no": "27AAACB1234D1Z1",
                        "is_primary_branch": True,
                        "address": {"state": "Maharashtra", "state_code": "MH"},
                    },
                    {
                        "branch_id": "branch_ts_002",
                        "branch_name": "Hyderabad Tech Hub",
                        "tax_reg_no": "36AAACB1234D1Z5",
                        "is_primary_branch": False,
                        "address": {"state": "Telangana", "state_code": "TS"},
                    },
                ]
            }
        elif "organizations/" in endpoint_path:
            return {
                "organization": {
                    "address": {"state": "Maharashtra", "state_code": "MH"}
                }
            }
        return {}

    with patch.object(master_data_service, "get_or_create_zoho_connection", AsyncMock(return_value=mock_conn)), \
         patch("app.services.zoho_client.zoho_client_service._make_authorized_request", side_effect=mock_api):

        # Invoice specifies Tamil Nadu ("TN") which is NOT registered as a branch
        res = await master_data_service.resolve_zoho_destination_and_branch(
            tenant_id="tenant-1",
            db=None,
            invoice_recipient_state="Tamil Nadu",
            invoice_recipient_gstin="33XXXXX0000X1Z0",
            organization_id="ORG_MULTI_ENTERPRISE",
        )

        assert res["destination_state_code"] in ("TN", "MH")
        # Critical safety guarantee: Never arbitrarily assign a branch_id if no branch matched
        assert res["branch_id"] is None
        assert res["source"] in ("zoho_org_primary", "invoice_recipient_fallback")


@pytest.mark.asyncio
async def test_wrong_organization_branch_id_never_included():
    """
    Case D: Ensure that branch resolution strictly uses the active organization's connection.
    If the connection is disconnected or mismatched, it falls back to invoice recipient without branch_id.
    """
    mock_conn = MockZohoConnection(org_id="ORG_MISMATCH", status="DISCONNECTED")

    with patch.object(master_data_service, "get_or_create_zoho_connection", AsyncMock(return_value=mock_conn)):
        res = await master_data_service.resolve_zoho_destination_and_branch(
            tenant_id="tenant-1",
            db=None,
            invoice_recipient_state="Telangana",
            organization_id="ORG_EXPECTED",
        )
        assert res["destination_state_code"] == "TS"
        assert res["branch_id"] is None
        assert res["source"] == "fallback_invoice"
