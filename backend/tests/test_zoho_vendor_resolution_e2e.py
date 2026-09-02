import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from app.db.models import Invoice, JournalEntry, ChartOfAccount, TaxRate, ZohoConnection
from app.services.zoho_client import zoho_client_service
from app.services.export_service import export_service
from app.services.invoice_processing import get_effective_invoice_data


@pytest.mark.asyncio
async def test_search_vendor_strict_matching_and_no_arbitrary_fallback():
    """
    Verifies search_vendor:
    1. Matches by exact GSTIN.
    2. Matches by exact or normalized vendor name.
    3. Returns None (never contacts[0]) when searching for an unknown vendor.
    """
    mock_conn = ZohoConnection(id=uuid4(), tenant_id="t1", organization_id="org_1", status="CONNECTED")
    mock_db = AsyncMock()

    zoho_contacts_in_org = [
        {
            "contact_id": "CNT_ADVOCATE_111",
            "contact_name": "Advocate Legal Consultants pvt ltd",
            "company_name": "Advocate Legal Consultants pvt ltd",
            "gst_no": "27AAACA0000A1Z5",
            "pan_no": "AAACA0000A",
        },
        {
            "contact_id": "CNT_ARAVALLI_222",
            "contact_name": "Aravalli Software Systems Pvt. Ltd.",
            "company_name": "Aravalli Software Systems Pvt. Ltd.",
            "gst_no": "36AACCA1234M1Z8",
            "pan_no": "AACCA1234M",
        }
    ]

    with patch.object(zoho_client_service, "_make_authorized_request", new_callable=AsyncMock) as mock_req:
        # Scenario A: Exact GSTIN match for Aravalli
        mock_req.return_value = {"contacts": zoho_contacts_in_org}
        found = await zoho_client_service.search_vendor(
            connection=mock_conn,
            db=mock_db,
            gstin="36AACCA1234M1Z8",
            vendor_name="Aravalli Software Systems Pvt. Ltd.",
        )
        assert found is not None
        assert found["contact_id"] == "CNT_ARAVALLI_222"
        assert found["contact_name"] == "Aravalli Software Systems Pvt. Ltd."

        # Scenario B: Searching for an unknown vendor "Quantum Dynamics India"
        # Even though Zoho returns the contact list, search_vendor MUST NOT return Advocate Legal Consultants!
        mock_req.return_value = {"contacts": zoho_contacts_in_org}
        not_found = await zoho_client_service.search_vendor(
            connection=mock_conn,
            db=mock_db,
            gstin="29XYZPQ9999Z1Z1",
            vendor_name="Quantum Dynamics India Pvt Ltd",
        )
        assert not_found is None  # Must be None so create_vendor can be called!


@pytest.mark.asyncio
async def test_vendor_taken_from_authoritative_saved_data_and_updates_on_edit():
    """
    Verifies that:
    1. Export uses authoritative current_vlm_output rather than raw_vlm_output.
    2. Editing the vendor on the extraction page creates/exports with the new vendor.
    3. raw_vlm_output remains completely unchanged.
    """
    inv_id = uuid4()
    original_raw = {
        "data": {
            "vendor_name": "Original OCR Vendor Ltd",
            "vendor_gstin": "27AAAAA1111A1Z1",
            "invoice_number": "INV-ORIG-001",
            "invoice_date": "2026-08-31",
            "due_date": "2026-09-30",
            "line_items": [
                {
                    "description": "IT Consulting",
                    "quantity": 1.0,
                    "unit_price": 10000.0,
                    "taxable_amount": 10000.0,
                    "gst_rate": 18.0,
                }
            ],
            "subtotal": 10000.0,
            "tax_total": 1800.0,
            "total_amount": 11800.0,
        }
    }

    edited_current = {
        "data": {
            "vendor_name": "Aravalli Software Systems Pvt. Ltd.",
            "vendor_gstin": "36AACCA1234M1Z8",
            "vendor_address": "6th Floor, Divyasree Chambers, Raidurg, Hyderabad, TG 500081",
            "buyer_name": "Konkan Retail Ventures Pvt. Ltd.",
            "buyer_gstin": "27AAAA0000A1Z5",
            "place_of_supply": "27 - Maharashtra",
            "invoice_number": "INV-2026-1587",
            "invoice_date": "2026-08-31",
            "due_date": "2026-09-30",
            "line_items": [
                {
                    "description": "Cloud ERP implementation & configuration services",
                    "quantity": 1.0,
                    "unit_price": 10000.0,
                    "taxable_amount": 10000.0,
                    "gst_rate": 18.0,
                }
            ],
            "subtotal": 10000.0,
            "tax_total": 1800.0,
            "total_amount": 11800.0,
        }
    }

    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="test-tenant",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        financial_validation_result={"overall_status": "PASSED"},
        raw_vlm_output=original_raw,
        current_vlm_output=edited_current,
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "4076465000000212005",
                    "approved_account_name": "PROFESSIONAL EXPENSE",
                }
            ]
        },
    )

    # Verify get_effective_invoice_data uses authoritative current_vlm_output
    eff_data = get_effective_invoice_data(mock_invoice)
    assert eff_data["vendor_name"] == "Aravalli Software Systems Pvt. Ltd."
    assert eff_data["vendor_gstin"] == "36AACCA1234M1Z8"
    assert eff_data["invoice_number"] == "INV-2026-1587"
    # Verify raw_vlm_output remains completely unchanged
    assert mock_invoice.raw_vlm_output["data"]["vendor_name"] == "Original OCR Vendor Ltd"

    balanced_journal = JournalEntry(
        id=uuid4(),
        invoice_id=inv_id,
        tenant_id="test-tenant",
        status="APPROVED",
        is_balanced=True,
        total_debit=11800.0,
        total_credit=11800.0,
        difference=0.0,
    )

    coa_1 = ChartOfAccount(
        id=uuid4(),
        tenant_id="test-tenant",
        zoho_account_id="4076465000000212005",
        account_name="PROFESSIONAL EXPENSE",
        is_active=True,
    )
    tax_igst18 = TaxRate(
        id=uuid4(),
        tenant_id="test-tenant",
        zoho_tax_id="4076465000000088015",
        tax_name="IGST18",
        tax_percentage=18.0,
        tax_type="tax",
        is_active=True,
    )

    mock_db = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM invoices" in stmt_str or "invoices." in stmt_str:
            res.scalar_one_or_none.return_value = mock_invoice
        elif "FROM journal_entries" in stmt_str or "journal_entries." in stmt_str:
            res.scalar_one_or_none.return_value = balanced_journal
        elif "FROM chart_of_accounts" in stmt_str or "chart_of_accounts." in stmt_str:
            res.scalars.return_value.all.return_value = [coa_1]
        elif "FROM tax_rates" in stmt_str or "tax_rates." in stmt_str:
            res.scalars.return_value.all.return_value = [tax_igst18]
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    with patch("app.services.master_data_service.master_data_service.get_or_create_zoho_connection", new_callable=AsyncMock) as mock_conn, \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_search, \
         patch("app.services.zoho_client.zoho_client_service.create_vendor", new_callable=AsyncMock) as mock_create, \
         patch("app.services.zoho_client.zoho_client_service.find_bill_by_number", new_callable=AsyncMock) as mock_find, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_bill, \
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock) as mock_att:

        mock_conn.return_value = MagicMock(status="CONNECTED", organization_id="org_123")
        # Vendor not found in Zoho -> Must trigger create_vendor with exact edited vendor details
        mock_search.return_value = None
        mock_create.return_value = {"contact_id": "NEW_CNT_ARAVALLI_999", "contact_name": "Aravalli Software Systems Pvt. Ltd."}
        mock_find.return_value = None
        mock_bill.return_value = {"bill_id": "zoho_bill_777", "bill_number": "INV-2026-1587"}
        mock_att.return_value = "attached"

        result = await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id="test-tenant",
            user_email="finance@test.org",
            db=mock_db,
        )

        assert result["status"] == "success"

        # Verify search_vendor was called with the EDITED vendor name and GSTIN
        mock_search.assert_called_once()
        search_args = mock_search.call_args[1]
        assert search_args["vendor_name"] == "Aravalli Software Systems Pvt. Ltd."
        assert search_args["gstin"] == "36AACCA1234M1Z8"

        # Verify create_vendor was called with the exact EDITED vendor name and address
        mock_create.assert_called_once()
        create_args = mock_create.call_args[1]
        assert create_args["vendor_name"] == "Aravalli Software Systems Pvt. Ltd."
        assert create_args["gstin"] == "36AACCA1234M1Z8"
        assert create_args["address"] == "6th Floor, Divyasree Chambers, Raidurg, Hyderabad, TG 500081"
        assert create_args["state_name"] == "Telangana"

        # Verify create_bill was called with the newly created vendor's contact_id
        mock_bill.assert_called_once()
        bill_payload = mock_bill.call_args[1]["bill_payload"]
        assert bill_payload["vendor_id"] == "NEW_CNT_ARAVALLI_999"
        assert bill_payload["bill_number"] == "INV-2026-1587"
        assert bill_payload["source_of_supply"] == "36"
        assert bill_payload["destination_of_supply"] == "27"


@pytest.mark.asyncio
async def test_unresolved_vendor_creation_failure_raises_blocking_error():
    """
    Verifies that if a vendor cannot be found and cannot be created in Zoho,
    the export raises a clear blocking error and NEVER falls back to a default/hardcoded vendor.
    """
    inv_id = uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="test-tenant",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        financial_validation_result={"overall_status": "PASSED"},
        current_vlm_output={
            "data": {
                "vendor_name": "Unresolvable Vendor Ltd",
                "vendor_gstin": "27AAAAA0000A1Z5",
                "invoice_number": "INV-FAIL-001",
                "invoice_date": "2026-08-31",
                "due_date": "2026-09-30",
                "line_items": [{"description": "Item", "quantity": 1.0, "unit_price": 100.0, "taxable_amount": 100.0}],
                "subtotal": 100.0,
                "tax_total": 18.0,
                "total_amount": 118.0,
            }
        },
        current_accounting_output={
            "accounting": [{"line_index": 1, "approved_account_id": "4076465000000212005"}]
        },
    )

    balanced_journal = JournalEntry(
        id=uuid4(),
        invoice_id=inv_id,
        tenant_id="test-tenant",
        status="APPROVED",
        is_balanced=True,
        total_debit=118.0,
        total_credit=118.0,
        difference=0.0,
    )

    coa_1 = ChartOfAccount(id=uuid4(), tenant_id="test-tenant", zoho_account_id="4076465000000212005", account_name="PROFESSIONAL EXPENSE", is_active=True)
    tax_1 = TaxRate(id=uuid4(), tenant_id="test-tenant", zoho_tax_id="4076465000000088015", tax_name="IGST18", tax_percentage=18.0, tax_type="tax", is_active=True)

    mock_db = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM invoices" in stmt_str or "invoices." in stmt_str:
            res.scalar_one_or_none.return_value = mock_invoice
        elif "FROM journal_entries" in stmt_str or "journal_entries." in stmt_str:
            res.scalar_one_or_none.return_value = balanced_journal
        elif "FROM chart_of_accounts" in stmt_str or "chart_of_accounts." in stmt_str:
            res.scalars.return_value.all.return_value = [coa_1]
        elif "FROM tax_rates" in stmt_str or "tax_rates." in stmt_str:
            res.scalars.return_value.all.return_value = [tax_1]
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    with patch("app.services.master_data_service.master_data_service.get_or_create_zoho_connection", new_callable=AsyncMock) as mock_conn, \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_search, \
         patch("app.services.zoho_client.zoho_client_service.create_vendor", new_callable=AsyncMock) as mock_create, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_bill:

        mock_conn.return_value = MagicMock(status="CONNECTED", organization_id="org_123")
        mock_search.return_value = None
        # create_vendor returns empty dict (failure)
        mock_create.return_value = {}

        with pytest.raises(RuntimeError) as exc_info:
            await export_service.export_invoice_to_zoho(
                invoice_id=inv_id,
                tenant_id="test-tenant",
                user_email="finance@test.org",
                db=mock_db,
            )

        assert "could not be confidently matched or created in Zoho Books" in str(exc_info.value)
        # Verify bill creation was NEVER attempted
        mock_bill.assert_not_called()


@pytest.mark.asyncio
async def test_normalized_vendor_name_resolution():
    """
    Verifies that search_vendor matches contacts with subtle legal suffix variations
    (e.g. 'Aravalli Software Systems Pvt Ltd' vs 'Aravalli Software Systems Private Limited').
    """
    mock_conn = ZohoConnection(id=uuid4(), tenant_id="t1", organization_id="org_1", status="CONNECTED")
    mock_db = AsyncMock()

    zoho_contacts = [
        {
            "contact_id": "CNT_ZOHO_MATCH_777",
            "contact_name": "Aravalli Software Systems Private Limited",
            "company_name": "Aravalli Software Systems Private Limited",
            "gst_no": "",
        }
    ]

    with patch.object(zoho_client_service, "_make_authorized_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"contacts": zoho_contacts}

        matched = await zoho_client_service.search_vendor(
            connection=mock_conn,
            db=mock_db,
            vendor_name="Aravalli Software Systems Pvt. Ltd.",
        )
        assert matched is not None
        assert matched["contact_id"] == "CNT_ZOHO_MATCH_777"


@pytest.mark.asyncio
async def test_api_vendor_status_and_add_to_zoho_flow():
    """
    Verifies that:
    1. get_invoice_vendor_status correctly returns NOT_FOUND when vendor does not exist.
    2. add_vendor_to_zoho creates the vendor in Zoho with authoritative invoice data and associates contact_id.
    """
    from app.api.v1.review import get_invoice_vendor_status, add_vendor_to_zoho
    from app.core.security import AuthenticatedUser

    inv_id = uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="test-tenant",
        current_vlm_output={
            "data": {
                "vendor_name": "Aravalli Software Systems Pvt. Ltd.",
                "vendor_gstin": "36AACCA1234M1Z8",
                "vendor_pan": "AACCA1234M",
                "vendor_address": "6th Floor, Divyasree Chambers, Raidurg, Hyderabad, TG 500081",
                "vendor_email": "billing@aravallisoft.in",
            }
        },
    )

    mock_user = AuthenticatedUser(
        id=str(uuid4()),
        tenant_id="test-tenant",
        email="finance@test.org",
        role="FINANCE",
    )

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_invoice)))
    mock_db.commit = AsyncMock()

    with patch("app.services.master_data_service.master_data_service.get_or_create_zoho_connection", new_callable=AsyncMock) as mock_conn, \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_search, \
         patch("app.services.zoho_client.zoho_client_service.create_vendor", new_callable=AsyncMock) as mock_create:

        mock_conn.return_value = MagicMock(status="CONNECTED", organization_id="org_123")
        mock_search.return_value = None
        mock_create.return_value = {"contact_id": "NEW_CNT_123", "contact_name": "Aravalli Software Systems Pvt. Ltd."}

        # Step 1: Check status -> Returns NOT_FOUND
        status_res = await get_invoice_vendor_status(
            invoice_id=inv_id,
            current_user=mock_user,
            db=mock_db,
        )
        assert status_res["match_status"] == "NOT_FOUND"
        assert status_res["requires_action"] is True
        assert status_res["invoice_vendor"]["vendor_name"] == "Aravalli Software Systems Pvt. Ltd."

        # Step 2: Call add_vendor_to_zoho -> Creates vendor and stores ID in invoice
        add_res = await add_vendor_to_zoho(
            invoice_id=inv_id,
            current_user=mock_user,
            db=mock_db,
        )
        assert add_res["status"] == "success"
        assert add_res["contact_id"] == "NEW_CNT_123"
        assert mock_invoice.current_vlm_output["data"]["zoho_vendor_id"] == "NEW_CNT_123"


def test_normalize_indian_state_all_formats():
    """
    Tests normalization of various Indian state strings, abbreviations, and GST codes
    into Zoho-compatible representations without hardcoding.
    """
    from app.services.gst_engine import normalize_indian_state

    # Telangana
    assert normalize_indian_state("Telangana") == ("TS", "36", "Telangana")
    assert normalize_indian_state("TG") == ("TS", "36", "Telangana")
    assert normalize_indian_state("TS") == ("TS", "36", "Telangana")
    assert normalize_indian_state("36") == ("TS", "36", "Telangana")
    assert normalize_indian_state("36 - Telangana") == ("TS", "36", "Telangana")

    # Maharashtra
    assert normalize_indian_state("Maharashtra") == ("MH", "27", "Maharashtra")
    assert normalize_indian_state("MH") == ("MH", "27", "Maharashtra")
    assert normalize_indian_state("27") == ("MH", "27", "Maharashtra")

    # Karnataka
    assert normalize_indian_state("Karnataka") == ("KA", "29", "Karnataka")
    assert normalize_indian_state("KA") == ("KA", "29", "Karnataka")
    assert normalize_indian_state("29") == ("KA", "29", "Karnataka")

    # Andhra Pradesh (Zoho code is AD)
    assert normalize_indian_state("Andhra Pradesh") == ("AD", "37", "Andhra Pradesh")
    assert normalize_indian_state("AP") == ("AD", "37", "Andhra Pradesh")
    assert normalize_indian_state("AD") == ("AD", "37", "Andhra Pradesh")
    assert normalize_indian_state("37") == ("AD", "37", "Andhra Pradesh")

    # Tamil Nadu
    assert normalize_indian_state("Tamil Nadu") == ("TN", "33", "Tamil Nadu")
    assert normalize_indian_state("TN") == ("TN", "33", "Tamil Nadu")
    assert normalize_indian_state("33") == ("TN", "33", "Tamil Nadu")

    # Delhi
    assert normalize_indian_state("Delhi") == ("DL", "07", "Delhi")
    assert normalize_indian_state("New Delhi") == ("DL", "07", "Delhi")
    assert normalize_indian_state("DL") == ("DL", "07", "Delhi")
    assert normalize_indian_state("07") == ("DL", "07", "Delhi")

    # Gujarat
    assert normalize_indian_state("Gujarat") == ("GJ", "24", "Gujarat")
    assert normalize_indian_state("GJ") == ("GJ", "24", "Gujarat")

    # Fallback to GSTIN when state_input is None
    assert normalize_indian_state(None, gstin="36AACCA1234M1Z8") == ("TS", "36", "Telangana")
    assert normalize_indian_state(None, gstin="27AAAA0000A1Z5") == ("MH", "27", "Maharashtra")
    assert normalize_indian_state(None, gstin="37AAAA0000A1Z5") == ("AD", "37", "Andhra Pradesh")


@pytest.mark.asyncio
async def test_create_vendor_payload_uses_valid_zoho_state_code():
    """
    Verifies that create_vendor sends valid 2-letter Zoho state codes (e.g. 'TS', 'MH', 'AD')
    in place_of_contact and billing_address.state_code to prevent Zoho error 118068.
    """
    mock_conn = ZohoConnection(id=uuid4(), tenant_id="t1", organization_id="org_1", status="CONNECTED")
    mock_db = AsyncMock()

    with patch.object(zoho_client_service, "_make_authorized_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"contact": {"contact_id": "CNT_NEW_TELANGANA"}}

        # Test Case 1: Vendor in Telangana with state_name="TG"
        await zoho_client_service.create_vendor(
            connection=mock_conn,
            db=mock_db,
            vendor_name="Aravalli Software Systems Pvt. Ltd.",
            gstin="36AACCA1234M1Z8",
            pan="AACCA1234M",
            address="6th Floor, Divyasree Chambers, Raidurg, Hyderabad, TG 500081",
            state_name="TG",
        )

        call_args = mock_req.call_args[1]
        sent_payload = call_args["json_data"]

        # MUST be valid 2-letter Zoho state code ("TS"), NEVER full name or invalid abbreviation
        assert sent_payload["place_of_contact"] == "TS"
        assert sent_payload["billing_address"]["state_code"] == "TS"
        assert sent_payload["billing_address"]["state"] == "Telangana"
        assert sent_payload["gst_no"] == "36AACCA1234M1Z8"
        assert sent_payload["gst_treatment"] == "business_gst"

        # Test Case 2: Vendor in Maharashtra with state_name="Maharashtra"
        mock_req.return_value = {"contact": {"contact_id": "CNT_NEW_MAHA"}}
        await zoho_client_service.create_vendor(
            connection=mock_conn,
            db=mock_db,
            vendor_name="Konkan Retail Ventures Pvt. Ltd.",
            gstin="27AAAA0000A1Z5",
            address="Unit 412, Solitaire Corporate Park, Andheri East, Mumbai, MH 400093",
            state_name="Maharashtra",
        )

        call_args_maha = mock_req.call_args[1]
        maha_payload = call_args_maha["json_data"]
        assert maha_payload["place_of_contact"] == "MH"
        assert maha_payload["billing_address"]["state_code"] == "MH"
        assert maha_payload["billing_address"]["state"] == "Maharashtra"

        # Test Case 3: Vendor in Andhra Pradesh with state_name="AP"
        mock_req.return_value = {"contact": {"contact_id": "CNT_NEW_AP"}}
        await zoho_client_service.create_vendor(
            connection=mock_conn,
            db=mock_db,
            vendor_name="Visakha Logistics",
            gstin="37AAAA0000A1Z5",
            state_name="AP",
        )

        call_args_ap = mock_req.call_args[1]
        ap_payload = call_args_ap["json_data"]
        assert ap_payload["place_of_contact"] == "AD"
        assert ap_payload["billing_address"]["state_code"] == "AD"
        assert ap_payload["billing_address"]["state"] == "Andhra Pradesh"



