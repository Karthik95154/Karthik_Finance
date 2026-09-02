import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.gst_engine import gst_engine
from app.services.tds_engine import tds_engine
from app.services.journal_generator import journal_generator
from app.services.export_service import export_service
from app.db.models import Invoice, ZohoConnection, ChartOfAccount, TaxRate, JournalEntry


@pytest.mark.asyncio
async def test_case_1_interstate_armstrong_journal_and_zoho_mapping():
    """
    TEST CASE 1 — INTERSTATE (Armstrong International style)
    Vendor state: Tamil Nadu (33)
    Buyer state: Telangana (36)
    Subtotal: ₹5,500
    IGST: 18% (₹990)
    Expected:
      Consulting Expenses DR ₹5,500
      Input IGST          DR ₹990
      Accounts Payable    CR ₹6,490
      Balanced: Debits ₹6,490 == Credits ₹6,490
    """
    vlm_data = {
        "invoice_number": "INV-2025-26-0778",
        "invoice_date": "2025-05-23",
        "due_date": "2025-05-23",
        "vendor_name": "Armstrong International",
        "vendor_gstin": "33AAVFA9162E1Z9",
        "customer_gstin": "36AAECJ6056C1ZQ",
        "subtotal": 5500.0,
        "tax_total": 990.0,
        "total_amount": 6490.0,
        "line_items": [
            {
                "line_index": 1,
                "description": "Being consulting fees for the actuarial valuation of Gratuity",
                "quantity": 1.0,
                "unit_price": 5500.0,
                "taxable_amount": 5500.0,
                "igst_rate": 18.0,
                "igst_amount": 990.0,
            }
        ],
    }

    # 1. GST Engine Supply Type Verification
    gst_res = gst_engine.evaluate_gst(vlm_data)
    assert gst_res["supply_type"] == "INTER_STATE"
    assert gst_res["calculated"]["igst_amount"] == 990.0
    assert gst_res["calculated"]["cgst_amount"] == 0.0
    assert gst_res["calculated"]["sgst_amount"] == 0.0

    # 2. Authoritative Journal Generation
    accounting_data = {
        "accounting": [
            {
                "line_index": 1,
                "source_description": "Being consulting fees for the actuarial valuation",
                "approved_account_id": "4076465000000033052",
                "approved_account_name": "Consulting Expenses",
            }
        ],
        "tds": {"applicable": False, "tds_section": None, "rate": 0.0},
    }

    journal = journal_generator.generate_journal(
        invoice_data=vlm_data,
        accounting_classification=accounting_data,
        gst_result=gst_res,
    )

    assert journal["status"] == "BALANCED"
    assert journal["total_debit"] == 6490.0
    assert journal["total_credit"] == 6490.0
    assert journal["difference"] == 0.0

    lines = {l["line_type"]: l for l in journal["lines"]}
    assert lines["EXPENSE"]["debit"] == 5500.0
    assert lines["EXPENSE"]["account_name"] == "Consulting Expenses"
    assert lines["INPUT_TAX"]["debit"] == 990.0
    assert "IGST" in lines["INPUT_TAX"]["account_name"]
    assert lines["ACCOUNTS_PAYABLE"]["credit"] == 6490.0


@pytest.mark.asyncio
async def test_case_2_intrastate_with_section_393_tds_journal_and_zoho_mapping():
    """
    TEST CASE 2 — INTRASTATE + AI TDS ASSESSMENT: Section 393 / Table 6(ii) / Professional services / 10%
    Vendor state: Telangana (36)
    Buyer state: Telangana (36)
    Subtotal: ₹5,000
    CGST: 9% (₹450)
    SGST: 9% (₹450)
    TDS: 10% (₹500 strictly on first-rupee subtotal, NOT on subtotal+GST)
    Expected:
      Professional Fees   DR ₹5,000
      Input CGST          DR ₹450
      Input SGST          DR ₹450
      TDS Payable         CR ₹500
      Accounts Payable    CR ₹5,400
      Balanced: Debits ₹5,900 == Credits ₹5,900
    """
    vlm_data = {
        "invoice_number": "INV-PRO-002",
        "invoice_date": "2026-06-30",
        "due_date": "2026-06-30",
        "vendor_name": "Advocate & Legal Associates",
        "vendor_gstin": "36AAFCC6655F1ZL",
        "customer_gstin": "36AAECJ6056C1ZQ",
        "subtotal": 5000.0,
        "tax_total": 900.0,
        "total_amount": 5900.0,
        "line_items": [
            {
                "line_index": 1,
                "description": "Being Professional fee for NDA review",
                "quantity": 1.0,
                "unit_price": 5000.0,
                "taxable_amount": 5000.0,
                "cgst_rate": 9.0,
                "cgst_amount": 450.0,
                "sgst_rate": 9.0,
                "sgst_amount": 450.0,
            }
        ],
    }

    # 1. GST Engine
    gst_res = gst_engine.evaluate_gst(vlm_data)
    assert gst_res["supply_type"] == "INTRA_STATE"
    assert gst_res["calculated"]["cgst_amount"] == 450.0
    assert gst_res["calculated"]["sgst_amount"] == 450.0

    # 2. TDS Engine Calculation on Subtotal (Section 393 / Table 6(ii))
    tds_res = tds_engine.calculate_tds(
        provision="Section 393",
        section="Table 6(ii)",
        nature_of_payment="Professional services",
        base_amount=5000.0,
        rate=10.0,
    )
    assert tds_res["applicable"] is True
    assert tds_res["rate"] == 10.0
    assert tds_res["base_amount"] == 5000.0
    assert tds_res["tds_amount"] == 500.0
    assert tds_res["provision"] == "Section 393"
    assert tds_res["section"] == "Table 6(ii)"

    # 3. Journal Generation
    accounting_data = {
        "accounting": [
            {
                "line_index": 1,
                "source_description": "Being Professional fee for NDA review",
                "approved_account_id": "4076465000000000531",
                "approved_account_name": "Professional Fees",
            }
        ],
        "tds": {
            "applicable": True,
            "approved": True,
            "tds_applicable": True,
            "nature_of_payment": "Professional services",
            "tds_provision": "Section 393",
            "tds_section": "Table 6(ii)",
            "tds_rate": 10.0,
            "final_tds_amount": 500.0,
        },
    }

    journal = journal_generator.generate_journal(
        invoice_data=vlm_data,
        accounting_classification=accounting_data,
        gst_result=gst_res,
        tds_result=accounting_data["tds"],
    )

    assert journal["total_debit"] == 5900.0
    assert journal["total_credit"] == 5900.0
    assert journal["difference"] == 0.0

    lines = {l["line_type"]: l for l in journal["lines"]}
    assert lines["EXPENSE"]["debit"] == 5000.0
    assert lines["EXPENSE"]["account_name"] == "Professional Fees"
    assert lines["TDS_PAYABLE"]["credit"] == 500.0
    assert lines["ACCOUNTS_PAYABLE"]["credit"] == 5400.0


@pytest.mark.asyncio
async def test_case_3_rejection_of_synthetic_coa_fallback():
    """
    TEST CASE 3 — STRICT VALIDATION OF APPROVED ZOHO ACCOUNTS
    Ensures synthetic placeholder accounts (ACC_1, ACC_2) are rejected with
    an actionable error and not silently converted to 'Other Expenses'.
    """
    mock_invoice = Invoice(
        id=uuid4(),
        tenant_id="test-tenant",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="hash_1",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        zoho_bill_id=None,
        current_vlm_output={
            "data": {
                "vendor_name": "Test Vendor",
                "invoice_number": "INV-100",
                "invoice_date": "2026-08-31",
                "total_amount": 1000.0,
                "line_items": [
                    {"line_index": 1, "description": "Test Item", "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0}
                ]
            }
        },
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "ACC_1",
                    "approved_account_name": "General Expenses",
                }
            ]
        }
    )

    mock_db = AsyncMock()
    mock_journal = JournalEntry(
        id=uuid4(),
        invoice_id=mock_invoice.id,
        tenant_id="test-tenant",
        status="APPROVED",
        is_balanced=True,
    )
    mock_conn = ZohoConnection(
        id=uuid4(),
        tenant_id="test-tenant",
        status="CONNECTED",
        organization_id="60081887558",
    )
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_invoice)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_journal)),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[ChartOfAccount(zoho_account_id="4076465000000000531", account_name="Professional Fees")])))),
    ]

    # Mock zoho connection
    with patch("app.services.master_data_service.master_data_service.get_or_create_zoho_connection") as mock_conn_fn:
        mock_conn = MagicMock()
        mock_conn.status = "CONNECTED"
        mock_conn.organization_id = "60081887558"
        mock_conn_fn.return_value = mock_conn

        # Calling export should raise error blocking export
        with pytest.raises((ValueError, RuntimeError)) as exc_info:
            await export_service.export_invoice_to_zoho(
                invoice_id=mock_invoice.id,
                tenant_id="test-tenant",
                db=mock_db,
            )

    assert "unmapped/placeholder account" in str(exc_info.value)


@pytest.mark.asyncio
async def test_case_4_first_rupee_tds_authoritative_calculation():
    """
    TEST CASE 4 — MANDATORY FIRST-RUPEE TDS CALCULATION
    Verifies that TDS amount = approved taxable subtotal * approved TDS rate
    without any YTD threshold, cumulative previous invoice, or catch-up logic.
    """
    # Subtotal ₹100,000, Section 194J, Rate 10%
    tds_1 = tds_engine.calculate_tds(
        section="194J",
        base_amount=100000.0,
        rate=10.0,
    )
    assert tds_1["applicable"] is True
    assert tds_1["rate"] == 10.0
    assert tds_1["base_amount"] == 100000.0
    assert tds_1["tds_amount"] == 10000.0

    # Subtotal ₹5,000, Section 194C, Rate 2%
    tds_2 = tds_engine.calculate_tds(
        section="194C",
        base_amount=5000.0,
        rate=2.0,
    )
    assert tds_2["applicable"] is True
    assert tds_2["rate"] == 2.0
    assert tds_2["base_amount"] == 5000.0
    assert tds_2["tds_amount"] == 100.0

    # Subtotal ₹25,000 (below old 30k threshold), Section 194C, Rate 1% (HUF/Indiv)
    tds_3 = tds_engine.calculate_tds(
        section="194C",
        base_amount=25000.0,
        rate=1.0,
    )
    assert tds_3["applicable"] is True
    assert tds_3["rate"] == 1.0
    assert tds_3["base_amount"] == 25000.0
    assert tds_3["tds_amount"] == 250.0  # Mandatory first-rupee deduction


@pytest.mark.asyncio
async def test_case_5_zero_tax_and_intra_state_tax_group_zoho_mapping():
    """
    TEST CASE 5 — GST Tax Mapping & Zero-Tax / Tax Exemption Handling
    Verifies:
    1. Intra-state line items map to GST18 tax group ID.
    2. Zero-tax or exempt line items receive tax_exemption_code or 0% tax_id, satisfying Zoho error 110802.
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
                "vendor_name": "Mixed Supply Vendor",
                "vendor_gstin": "27ABCDE1234F1Z5",
                "customer_gstin": "27XYZAB1234F1Z9",  # Intra-state Maharashtra (27)
                "invoice_number": "INV-MIXED-001",
                "invoice_date": "2026-03-01",
                "due_date": "2026-03-31",
                "subtotal": 15000.0,
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
                "total_amount": 16800.0,
                "line_items": [
                    {
                        "line_index": 1,
                        "description": "Taxable Consulting Services",
                        "quantity": 1.0,
                        "unit_price": 10000.0,
                        "taxable_amount": 10000.0,
                        "cgst_rate": 9.0,
                        "sgst_rate": 9.0,
                        "cgst_amount": 900.0,
                        "sgst_amount": 900.0,
                    },
                    {
                        "line_index": 2,
                        "description": "Exempt Training Materials",
                        "quantity": 1.0,
                        "unit_price": 5000.0,
                        "taxable_amount": 5000.0,
                        "cgst_rate": 0.0,
                        "sgst_rate": 0.0,
                    },
                ],
            }
        },
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "460000000028001",
                    "approved_account_name": "Consulting Expense",
                },
                {
                    "line_index": 2,
                    "approved_account_id": "460000000028002",
                    "approved_account_name": "Training Expense",
                },
            ]
        },
    )

    balanced_journal = JournalEntry(
        id=uuid4(),
        invoice_id=inv_id,
        tenant_id="test-tenant",
        status="APPROVED",
        is_balanced=True,
        total_debit=16800.0,
        total_credit=16800.0,
        difference=0.0,
    )

    coa_1 = ChartOfAccount(id=uuid4(), tenant_id="test-tenant", zoho_account_id="460000000028001", account_name="Consulting Expense", is_active=True)
    coa_2 = ChartOfAccount(id=uuid4(), tenant_id="test-tenant", zoho_account_id="460000000028002", account_name="Training Expense", is_active=True)

    tax_gst18 = TaxRate(id=uuid4(), tenant_id="test-tenant", zoho_tax_id="460000000099018", tax_name="GST18", tax_percentage=18.0, tax_type="tax_group", is_active=True)
    tax_gst0 = TaxRate(id=uuid4(), tenant_id="test-tenant", zoho_tax_id="460000000099000", tax_name="GST0", tax_percentage=0.0, tax_type="GST", is_active=True)

    mock_db = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM invoices" in stmt_str or "invoices." in stmt_str:
            res.scalar_one_or_none.return_value = mock_invoice
        elif "FROM journal_entries" in stmt_str or "journal_entries." in stmt_str:
            res.scalar_one_or_none.return_value = balanced_journal
        elif "FROM chart_of_accounts" in stmt_str or "chart_of_accounts." in stmt_str:
            res.scalars.return_value.all.return_value = [coa_1, coa_2]
        elif "FROM tax_rates" in stmt_str or "tax_rates." in stmt_str:
            res.scalars.return_value.all.return_value = [tax_gst18, tax_gst0]
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    with patch("app.services.master_data_service.master_data_service.get_or_create_zoho_connection", new_callable=AsyncMock) as mock_conn, \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_vendor, \
         patch("app.services.zoho_client.zoho_client_service.find_bill_by_number", new_callable=AsyncMock) as mock_find, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_bill, \
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock) as mock_att:

        mock_conn.return_value = MagicMock(status="CONNECTED", organization_id="org_123")
        mock_vendor.return_value = {"contact_id": "vend_123"}
        mock_find.return_value = None
        mock_bill.return_value = {"bill_id": "zoho_bill_mixed_999", "bill_number": "INV-MIXED-001"}
        mock_att.return_value = "attached"

        result = await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id="test-tenant",
            user_email="finance@test.org",
            db=mock_db,
        )

        assert result["status"] == "success"
        # Verify that create_bill was called with valid tax_id on line 1 and 0% tax_id or exemption on line 2
        bill_call_args = mock_bill.call_args[1]["bill_payload"]
        lines = bill_call_args["line_items"]
        assert len(lines) == 2
        # Line 1: Taxable 18% -> tax_id mapped to GST18 tax group
        assert lines[0]["tax_id"] == "460000000099018"
        # Line 2: 0% Tax -> zero_tax_id or tax_exemption_code present (NOT omitted)
        assert lines[1].get("tax_id") == "460000000099000" or lines[1].get("tax_exemption_code") is not None


@pytest.mark.asyncio
async def test_case_6_missing_tax_mapping_raises_error_and_never_marks_exempt():
    """
    TEST CASE 6 — Missing Tax Mapping for Taxable GST Line
    Verifies:
    When a line is taxable (e.g. GST 18%) but no matching Zoho Tax exists,
    export FAILS with a clear tax mapping error and DOES NOT silently mark the line EXEMPT_SUPPLY.
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
                "vendor_name": "Taxable Vendor",
                "vendor_gstin": "27ABCDE1234F1Z5",
                "customer_gstin": "27XYZAB1234F1Z9",
                "invoice_number": "INV-UNMAPPED-TAX",
                "invoice_date": "2026-03-01",
                "due_date": "2026-03-31",
                "subtotal": 10000.0,
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
                "total_amount": 11800.0,
                "line_items": [
                    {
                        "line_index": 1,
                        "description": "Taxable Consulting",
                        "quantity": 1.0,
                        "unit_price": 10000.0,
                        "taxable_amount": 10000.0,
                        "cgst_rate": 9.0,
                        "sgst_rate": 9.0,
                        "cgst_amount": 900.0,
                        "sgst_amount": 900.0,
                    }
                ],
            }
        },
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "460000000028001",
                    "approved_account_name": "Consulting Expense",
                }
            ]
        },
    )

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

    coa_1 = ChartOfAccount(id=uuid4(), tenant_id="test-tenant", zoho_account_id="460000000028001", account_name="Consulting Expense", is_active=True)

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
            # NO TAXES in Zoho matching 18%
            res.scalars.return_value.all.return_value = []
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    with patch("app.services.master_data_service.master_data_service.get_or_create_zoho_connection", new_callable=AsyncMock) as mock_conn, \
         patch("app.services.master_data_service.master_data_service.sync_taxes", new_callable=AsyncMock) as mock_sync_taxes, \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_vendor:

        mock_conn.return_value = MagicMock(status="CONNECTED", organization_id="org_123")
        mock_sync_taxes.return_value = []
        mock_vendor.return_value = {"contact_id": "vend_123"}

        with pytest.raises(RuntimeError) as exc_info:
            await export_service.export_invoice_to_zoho(
                invoice_id=inv_id,
                tenant_id="test-tenant",
                user_email="finance@test.org",
                db=mock_db,
            )

        assert "taxable GST rate of 18.0%" in str(exc_info.value)
        assert "no matching tax or tax group was found in Zoho Books" in str(exc_info.value)


@pytest.mark.asyncio
async def test_case_7_rcm_reverse_charge_mapping():
    """
    TEST CASE 7 — Reverse Charge Mechanism (RCM) Mapping
    Verifies:
    When an invoice is under RCM (Reverse Charge), Zoho Bill payload and line items
    correctly include is_reverse_charge_applied: True.
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
                "vendor_name": "GTA Transport Provider",
                "vendor_gstin": "27ABCDE1234F1Z5",
                "customer_gstin": "27XYZAB1234F1Z9",
                "invoice_number": "INV-RCM-001",
                "invoice_date": "2026-03-01",
                "due_date": "2026-03-31",
                "subtotal": 20000.0,
                "is_reverse_charge": True,  # RCM Flag
                "total_amount": 20000.0,
                "line_items": [
                    {
                        "line_index": 1,
                        "description": "Freight & Transport GTA",
                        "quantity": 1.0,
                        "unit_price": 20000.0,
                        "taxable_amount": 20000.0,
                        "cgst_rate": 2.5,
                        "sgst_rate": 2.5,
                    }
                ],
            }
        },
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "460000000028001",
                    "approved_account_name": "Freight Expense",
                }
            ]
        },
    )

    balanced_journal = JournalEntry(
        id=uuid4(),
        invoice_id=inv_id,
        tenant_id="test-tenant",
        status="APPROVED",
        is_balanced=True,
        total_debit=20000.0,
        total_credit=20000.0,
        difference=0.0,
    )

    coa_1 = ChartOfAccount(id=uuid4(), tenant_id="test-tenant", zoho_account_id="460000000028001", account_name="Freight Expense", is_active=True)
    tax_gst5 = TaxRate(id=uuid4(), tenant_id="test-tenant", zoho_tax_id="460000000099005", tax_name="GST5", tax_percentage=5.0, tax_type="tax_group", is_active=True)

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
            res.scalars.return_value.all.return_value = [tax_gst5]
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    with patch("app.services.master_data_service.master_data_service.get_or_create_zoho_connection", new_callable=AsyncMock) as mock_conn, \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_vendor, \
         patch("app.services.zoho_client.zoho_client_service.find_bill_by_number", new_callable=AsyncMock) as mock_find, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_bill, \
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock) as mock_att:

        mock_conn.return_value = MagicMock(status="CONNECTED", organization_id="org_123")
        mock_vendor.return_value = {"contact_id": "vend_123"}
        mock_find.return_value = None
        mock_bill.return_value = {"bill_id": "zoho_bill_rcm_999", "bill_number": "INV-RCM-001"}
        mock_att.return_value = "attached"

        result = await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id="test-tenant",
            user_email="finance@test.org",
            db=mock_db,
        )

        assert result["status"] == "success"
        bill_call_args = mock_bill.call_args[1]["bill_payload"]
        assert bill_call_args.get("is_reverse_charge_applied") is True
        assert bill_call_args["line_items"][0].get("is_reverse_charge_applied") is True
        assert bill_call_args["line_items"][0]["tax_id"] == "460000000099005"


@pytest.mark.asyncio
async def test_case_8_zoho_source_of_supply_state_code_length():
    """
    TEST CASE 8 — Zoho source_of_supply & destination_of_supply formatting
    Verifies that state codes passed in the Zoho bill payload:
    1. Are <= 4 characters (standard 2-digit numeric or 2-letter alpha state code).
    2. Correctly map full state names (e.g. 'Telangana' -> '36', 'Maharashtra' -> '27').
    """
    from app.services.export_service import to_zoho_state_code
    assert to_zoho_state_code("Telangana") == "36"
    assert to_zoho_state_code("Maharashtra") == "27"
    assert to_zoho_state_code("Karnataka") == "29"
    assert to_zoho_state_code("Delhi") == "07"
    assert to_zoho_state_code("36") == "36"
    assert to_zoho_state_code("TG") == "TG"
    assert len(to_zoho_state_code("Telangana")) < 5
    assert len(to_zoho_state_code("Maharashtra")) < 5

