import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from typing import Dict, Any

from app.db.models import Invoice, ZohoConnection, TaxRate, Tenant
from app.services.tds_engine import get_effective_tds_data, tds_engine
from app.services.master_data_service import master_data_service
from app.services.export_service import export_service
from app.services.journal_generator import journal_generator


def test_get_effective_tds_data_prioritizes_tds_assessment():
    """
    TEST 1 & TEST 2:
    Verifies that get_effective_tds_data strictly prioritizes tds_assessment.tds_applicable == false
    over legacy tds.applicable == true or legacy rates.
    """
    # Case 1: tds_assessment is False, legacy tds is True
    accounting_payload = {
        "tds_assessment": {
            "tds_applicable": False,
            "nature_of_payment": "Purchase of goods",
            "tds_rate": None,
            "tds_section": None,
        },
        "tds": {
            "applicable": True,
            "rate": 0.1,
            "reason": "Purchase of Goods TDS (0.1%)",
        },
    }
    effective = get_effective_tds_data(accounting_payload)
    assert effective["applicable"] is False
    assert effective["rate"] is None
    assert effective["tds_amount"] is None

    # Case 2: tds_assessment is False, legacy tds has 10% rate and 194J section
    accounting_payload_2 = {
        "tds_assessment": {
            "tds_applicable": False,
            "nature_of_payment": "Professional services",
            "tds_rate": None,
            "tds_section": None,
        },
        "tds": {
            "applicable": True,
            "rate": 10.0,
            "section": "194J",
            "provision": "Table 6",
            "nature_of_payment": "Professional services",
        },
    }
    effective_2 = get_effective_tds_data(accounting_payload_2)
    assert effective_2["applicable"] is False
    assert effective_2["rate"] is None


@pytest.mark.asyncio
async def test_master_data_exact_tds_resolution_and_zero_fallback():
    """
    TEST 3, TEST 4, TEST 6, TEST 9:
    Verifies that get_zoho_tds_tax resolves ONLY exact rate-compatible taxes,
    never falls back to tds_taxes[0], and returns None when exact match does not exist.
    """
    tenant_id = "test-tenant"
    mock_db = AsyncMock()

    mock_conn = ZohoConnection(id=uuid4(), tenant_id=tenant_id, organization_id="org_123", status="CONNECTED")
    mock_tds_taxes = [
        TaxRate(id=uuid4(), tenant_id=tenant_id, zoho_tax_id="ZOHO_TDS_COMM_2", tax_name="Commission or Brokerage (2%)", tax_percentage=2.0, tax_type="TDS", is_active=True),
        TaxRate(id=uuid4(), tenant_id=tenant_id, zoho_tax_id="ZOHO_TDS_PROF_10", tax_name="Professional Fees (10%)", tax_percentage=10.0, tax_type="TDS", is_active=True),
    ]
    async def mock_exec_tds(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM zoho_connections" in stmt_str or "zoho_connections." in stmt_str:
            res.scalars.return_value.all.return_value = [mock_conn]
            res.scalar_one_or_none.return_value = mock_conn
        elif "FROM tax_rates" in stmt_str or "tax_rates." in stmt_str:
            res.scalars.return_value.all.return_value = mock_tds_taxes
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res
    mock_db.execute = mock_exec_tds

    # TEST 3: Exact match for 10% Professional
    res_10 = await master_data_service.get_zoho_tds_tax(
        tenant_id=tenant_id,
        section="194J",
        nature_of_payment="Professional services",
        rate=10.0,
        db=mock_db,
    )
    assert res_10 == "ZOHO_TDS_PROF_10"

    # TEST 4 & TEST 6: Invoice requires 0.1% for Purchase of Goods (194Q)
    # MUST NOT return 2% Commission or 10% Professional Fees! Must return None.
    res_01 = await master_data_service.get_zoho_tds_tax(
        tenant_id=tenant_id,
        section="194Q",
        nature_of_payment="Purchase of goods",
        rate=0.1,
        db=mock_db,
    )
    assert res_01 is None

    # TEST 5: Rate is None / missing
    res_none = await master_data_service.get_zoho_tds_tax(
        tenant_id=tenant_id,
        section=None,
        nature_of_payment="Services",
        rate=None,
        db=mock_db,
    )
    assert res_none is None


@pytest.mark.asyncio
async def test_export_service_tds_not_applicable_never_sends_tds_tax_id():
    """
    TEST 1 & TEST 10:
    Verifies that when tds_assessment.tds_applicable is False (even if legacy tds.applicable is True),
    export_invoice_to_zoho NEVER sends tds_tax_id in line items and applies 0 TDS.
    """
    inv_id = uuid4()
    tenant_id = "test-tenant"

    mock_invoice = Invoice(
        id=inv_id,
        tenant_id=tenant_id,
        approval_status="APPROVED",
        current_vlm_output={
            "data": {
                "invoice_number": "INV-2026-TDS-TEST-01",
                "invoice_date": "2026-08-31",
                "subtotal": 151200.0,
                "total_amount": 178416.0,
                "vendor_name": "Deccan Precision Components Pvt. Ltd.",
                "vendor_gstin": "36AADCD5678N1Z3",
                "line_items": [
                    {"description": "CNC brackets", "quantity": 500, "unit_price": 210, "taxable_amount": 105000.0, "igst_rate": 18.0},
                    {"description": "Steel shafts", "quantity": 120, "unit_price": 385, "taxable_amount": 46200.0, "igst_rate": 18.0},
                ],
            }
        },
        current_accounting_output={
            "tds_assessment": {
                "tds_applicable": False,
                "nature_of_payment": "Purchase of goods",
                "tds_rate": None,
                "tds_section": None,
            },
            "tds": {
                "applicable": True,
                "rate": 0.1,
            },
            "accounting": [
                {"line_index": 1, "approved_account_id": "4076465000000000567"},
                {"line_index": 2, "approved_account_id": "4076465000000000567"},
            ],
        },
        journal_entry={"status": "APPROVED", "approval_status": "APPROVED"},
    )

    mock_conn = ZohoConnection(id=uuid4(), tenant_id=tenant_id, organization_id="org_123", status="CONNECTED")
    mock_journal = MagicMock(is_balanced=True, status="APPROVED")
    mock_tenant = Tenant(id=tenant_id, name="Test Org", slug="test-org", books_closed_through_date=None)
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_invoice)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_journal)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
    ])
    mock_db.commit = AsyncMock()

    with patch.object(master_data_service, "get_or_create_zoho_connection", return_value=mock_conn), \
         patch.object(master_data_service, "get_cached_chart_of_accounts", return_value=[{"account_id": "4076465000000000567"}]), \
         patch.object(master_data_service, "get_zoho_tax_for_line", return_value="ZOHO_IGST18"), \
         patch("app.services.zoho_client.zoho_client_service.find_bill_by_number", new_callable=AsyncMock, return_value=None), \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", return_value={"contact_id": "CNT_VENDOR_01"}), \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_create_bill, \
         patch("app.services.audit_service.audit_service.log_event", new_callable=AsyncMock):

        mock_create_bill.return_value = {"bill_id": "ZOHO_BILL_999", "bill_number": "INV-2026-TDS-TEST-01"}

        result = await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id=tenant_id,
            db=mock_db,
            user_email="finance@test.org",
        )

        assert result["status"] == "success"
        sent_bill = mock_create_bill.call_args[1]["bill_payload"]

        # Assert zero TDS: No line item contains tds_tax_id
        for line in sent_bill["line_items"]:
            assert "tds_tax_id" not in line


@pytest.mark.asyncio
async def test_export_service_missing_tds_tax_raises_blocking_error():
    """
    TEST 4, TEST 6:
    When tds_applicable is True (e.g. 0.1%), but Zoho has no 0.1% TDS tax,
    export_invoice_to_zoho raises a clear ValueError and NEVER falls back to 2%.
    """
    inv_id = uuid4()
    tenant_id = "test-tenant"

    mock_invoice = Invoice(
        id=inv_id,
        tenant_id=tenant_id,
        approval_status="APPROVED",
        current_vlm_output={
            "data": {
                "invoice_number": "INV-2026-TDS-TEST-02",
                "subtotal": 151200.0,
                "total_amount": 178416.0,
                "vendor_name": "Deccan Precision Components Pvt. Ltd.",
                "vendor_gstin": "36AADCD5678N1Z3",
                "line_items": [
                    {"description": "CNC brackets", "quantity": 500, "unit_price": 210, "taxable_amount": 105000.0, "igst_rate": 18.0},
                ],
            }
        },
        current_accounting_output={
            "tds_assessment": {
                "tds_applicable": True,
                "nature_of_payment": "Purchase of goods",
                "tds_rate": 0.1,
                "tds_section": "194Q",
            },
            "accounting": [
                {"line_index": 1, "approved_account_id": "4076465000000000567"},
            ],
        },
        journal_entry={"status": "APPROVED", "approval_status": "APPROVED"},
    )

    mock_conn = ZohoConnection(id=uuid4(), tenant_id=tenant_id, organization_id="org_123", status="CONNECTED")
    mock_journal = MagicMock(is_balanced=True, status="APPROVED")
    mock_tenant = Tenant(id=tenant_id, name="Test Org", slug="test-org", books_closed_through_date=None)
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_invoice)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_journal)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
    ])
    mock_db.commit = AsyncMock()

    with patch.object(master_data_service, "get_or_create_zoho_connection", return_value=mock_conn), \
         patch.object(master_data_service, "get_cached_chart_of_accounts", return_value=[{"account_id": "4076465000000000567"}]), \
         patch.object(master_data_service, "get_zoho_tax_for_line", return_value="ZOHO_IGST18"), \
         patch.object(master_data_service, "get_zoho_tds_tax", return_value=None), \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", return_value={"contact_id": "CNT_VENDOR_01"}):

        with pytest.raises(RuntimeError) as excinfo:
            await export_service.export_invoice_to_zoho(
                invoice_id=inv_id,
                tenant_id=tenant_id,
                db=mock_db,
                user_email="finance@test.org",
            )
        assert "no matching active TDS tax was found in Zoho Books" in str(excinfo.value)


def test_journal_generation_consistency_with_authoritative_tds():
    """
    TEST 7 & TEST 8:
    Verifies that journal_generator produces NO TDS liability line when tds_applicable is False,
    and produces a balanced TDS liability line when tds_applicable is True.
    """
    invoice_data = {
        "vendor_name": "Deccan Precision Components Pvt. Ltd.",
        "subtotal": 151200.0,
        "total_amount": 178416.0,
        "line_items": [
            {"description": "CNC brackets", "taxable_amount": 151200.0},
        ],
    }
    gst_result = {
        "supply_type": "INTER_STATE",
        "calculated": {"igst_amount": 27216.0},
    }

    # Case A: TDS is NOT applicable
    accounting_no_tds = {
        "accounting": [{"line_index": 1, "account_id": "ACC_COGS", "account_name": "Cost of Goods Sold"}],
        "tds_assessment": {
            "tds_applicable": False,
            "tds_rate": None,
        },
    }
    journal_no_tds = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting_no_tds,
        gst_result=gst_result,
    )
    # Verify no TDS liability line
    tds_lines_no = [l for l in journal_no_tds["lines"] if l.get("line_type") == "TDS_PAYABLE"]
    assert len(tds_lines_no) == 0
    # AP line has full gross obligation (₹178,416.00)
    ap_line_no = [l for l in journal_no_tds["lines"] if l.get("line_type") == "ACCOUNTS_PAYABLE"][0]
    assert ap_line_no["credit"] == 178416.0

    # Case B: TDS IS applicable (10% on ₹151,200 = ₹15,120.00)
    accounting_with_tds = {
        "accounting": [{"line_index": 1, "account_id": "ACC_COGS", "account_name": "Cost of Goods Sold"}],
        "tds_assessment": {
            "tds_applicable": True,
            "tds_section": "194J",
            "tds_rate": 10.0,
            "nature_of_payment": "Professional services",
            "is_approved": True,
        },
    }
    journal_with_tds = journal_generator.generate_journal(
        invoice_data=invoice_data,
        accounting_classification=accounting_with_tds,
        gst_result=gst_result,
    )
    tds_lines_yes = [l for l in journal_with_tds["lines"] if l.get("line_type") == "TDS_PAYABLE"]
    assert len(tds_lines_yes) == 1
    assert tds_lines_yes[0]["credit"] == 15120.0
    # AP line is net: 178416.0 - 15120.0 = 163296.0
    ap_line_yes = [l for l in journal_with_tds["lines"] if l.get("line_type") == "ACCOUNTS_PAYABLE"][0]
    assert ap_line_yes["credit"] == 163296.0
    # Balanced check
    assert journal_with_tds["validation"]["balanced"] is True
