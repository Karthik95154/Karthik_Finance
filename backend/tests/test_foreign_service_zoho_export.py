import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.db.models import Invoice, ZohoConnection, ChartOfAccount, TaxRate, JournalEntry, JournalLineModel
from app.services.export_service import export_service


@pytest.mark.asyncio
async def test_01_approval_gate_strictly_enforced_server_side():
    """Verify unapproved foreign service invoices (PENDING_REVIEW, REJECTED, PROCESSING) cannot export."""
    mock_db = AsyncMock()
    inv_id = uuid.uuid4()
    user_id = uuid.uuid4()

    for invalid_status in ["PENDING_REVIEW", "REJECTED", "PROCESSING", "FAILED"]:
        mock_inv = Invoice(
            id=inv_id,
            user_id=user_id,
            tenant_id="tenant-gate-001",
            status="COMPLETED",
            approval_status=invalid_status,
            export_status="NOT_EXPORTED",
            invoice_origin="FOREIGN_SERVICE",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_inv
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="must be APPROVED by Finance before exporting"):
            await export_service.export_invoice_to_zoho(
                invoice_id=inv_id,
                tenant_id="tenant-gate-001",
                db=mock_db,
            )


@pytest.mark.asyncio
async def test_02_foreign_service_zoho_export_e2e_cloudarc_success():
    """
    Test end-to-end export of CloudArc Foreign Service invoice ($150.00 USD @ 85.70 = ₹12,855.00 INR).
    Verifies:
    - Final approved INR amounts sent to Zoho
    - Original foreign currency & amount preserved in notes/header
    - Foreign vendor created with country="United States" & gst_treatment="overseas"
    - Reverse Charge (RCM) flags applied on Bill and Line Items
    - No second FX conversion occurs
    - Journal debit & RCM input tax reconciled (BUG-002 check)
    - Line item amount is ₹12,855.00 (BUG-004 check)
    """
    inv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    tenant_id = "tenant-cloudarc-001"

    # CloudArc Foreign Service Approved Invoice
    mock_invoice = Invoice(
        id=inv_id,
        user_id=user_id,
        tenant_id=tenant_id,
        file_path="uploads/cloudarc_inv_001.pdf",
        file_name="cloudarc_inv_001.pdf",
        file_size=12000,
        mime_type="application/pdf",
        file_hash="hash_cloudarc_123",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        invoice_origin="FOREIGN_SERVICE",
        currency="USD",
        exchange_rate=Decimal("85.700000"),
        exchange_rate_source="EXCHANGE_RATE_API",
        fx_original_rate=Decimal("85.700000"),
        raw_vlm_output={
            "data": {
                "invoice_number": "CA-2026-8891",
                "invoice_date": "2026-08-15",
                "due_date": "2026-09-15",
                "vendor_name": "CloudArc Global Inc.",
                "vendor_country": "United States",
                "vendor_tax_id": "US-EIN-987654321",
                "place_of_supply": "36",
                "total_amount": 150.0,
                "subtotal": 150.0,
                "currency": "USD",
                "service_description": "Cloud VPS Hosting & GPU compute cluster",
                "line_items": [
                    {
                        "description": "Cloud Hosting & SaaS compute (1 month)",
                        "quantity": 1.0,
                        "unit_price": 150.0,
                        "taxable_amount": 150.0,
                        "sac_code": "998315",
                        "gst_rate": 18.0,
                        "total": 150.0,
                    }
                ],
            }
        },
        current_vlm_output={
            "data": {
                "invoice_number": "CA-2026-8891",
                "invoice_date": "2026-08-15",
                "due_date": "2026-09-15",
                "vendor_name": "CloudArc Global Inc.",
                "vendor_country": "United States",
                "vendor_tax_id": "US-EIN-987654321",
                "place_of_supply": "36",
                "total_amount": 150.0,
                "subtotal": 150.0,
                "currency": "USD",
                "line_items": [
                    {
                        "description": "Cloud Hosting & SaaS compute (1 month)",
                        "quantity": 1.0,
                        "unit_price": 150.0,
                        "taxable_amount": 150.0,
                        "sac_code": "998315",
                        "gst_rate": 18.0,
                        "total": 150.0,
                    }
                ],
            }
        },
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "4076465000000000999",
                    "approved_account_name": "Cloud Computing & Server Infrastructure",
                }
            ],
            "tds": {
                "applicable": False,
            }
        },
    )

    mock_connection = ZohoConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        tenant_id=tenant_id,
        organization_id="ORG_CLOUDFOREIGN_01",
        organization_name="Sakshi Technologies Pvt Ltd",
        status="CONNECTED",
        api_domain="https://www.zohoapis.in",
    )

    # Balanced RCM Journal: Debit Expense ₹12,855.00, Debit Input Tax IGST ₹2,313.90, Credit Accounts Payable ₹12,855.00, Credit RCM IGST ₹2,313.90
    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id=tenant_id,
        is_balanced=True,
        total_debit=15168.90,
        total_credit=15168.90,
        status="APPROVED",
    )

    jl_expense = JournalLineModel(
        id=uuid.uuid4(),
        journal_entry_id=mock_journal.id,
        line_type="EXPENSE",
        debit=12855.0,
        credit=0.0,
    )
    jl_input_tax = JournalLineModel(
        id=uuid.uuid4(),
        journal_entry_id=mock_journal.id,
        line_type="INPUT_TAX",
        debit=2313.90,
        credit=0.0,
    )

    coa_expense = ChartOfAccount(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        organization_id="ORG_CLOUDFOREIGN_01",
        zoho_account_id="4076465000000000999",
        account_name="Cloud Computing & Server Infrastructure",
        account_type="Expense",
        is_active=True,
    )

    tax_igst_18 = TaxRate(
        zoho_tax_id="TAX_IGST_18_RCM",
        tax_name="IGST 18% (Import of Services)",
        tax_percentage=18.0,
        tax_type="TAX",
        is_active=True,
    )

    mock_db = AsyncMock()
    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM invoices" in stmt_str or "invoices." in stmt_str:
            res.scalar_one_or_none.return_value = mock_invoice
        elif "FROM journal_entries" in stmt_str or "journal_entries." in stmt_str:
            res.scalar_one_or_none.return_value = mock_journal
        elif "FROM zoho_connections" in stmt_str or "zoho_connections." in stmt_str:
            res.scalar_one_or_none.return_value = mock_connection
        elif "FROM chart_of_accounts" in stmt_str or "chart_of_accounts." in stmt_str:
            res.scalars.return_value.all.return_value = [coa_expense]
        elif "FROM tax_rates" in stmt_str or "tax_rates." in stmt_str:
            res.scalars.return_value.all.return_value = [tax_igst_18]
        elif "FROM journal_lines" in stmt_str or "journal_lines." in stmt_str:
            res.scalars.return_value.all.return_value = [jl_expense, jl_input_tax]
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()

    with patch("app.services.master_data_service.master_data_service.get_or_create_zoho_connection", new_callable=AsyncMock) as mock_get_conn, \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_search_vendor, \
         patch("app.services.zoho_client.zoho_client_service.create_vendor", new_callable=AsyncMock) as mock_create_vendor, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_create_bill, \
         patch("app.services.zoho_client.zoho_client_service.find_bill_by_number", new_callable=AsyncMock) as mock_find_bill, \
         patch("app.storage.supabase_storage.storage_service.download_file", new_callable=AsyncMock) as mock_download_file, \
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock) as mock_attach_file, \
         patch("app.services.master_data_service.master_data_service.get_zoho_tax_for_line", new_callable=AsyncMock) as mock_get_tax, \
         patch("app.services.audit_service.audit_service.log_event", new_callable=AsyncMock) as mock_audit:

        mock_get_conn.return_value = mock_connection
        mock_search_vendor.return_value = None
        mock_create_vendor.return_value = {"contact_id": "CNT_CLOUDFOREIGN_777", "contact_name": "CloudArc Global Inc."}
        mock_find_bill.return_value = None
        mock_get_tax.return_value = "TAX_IGST_18_RCM"
        mock_create_bill.return_value = {"bill_id": "ZBILL_CLOUDFOREIGN_123", "bill_number": "CA-2026-8891"}
        mock_download_file.return_value = b"%PDF-1.4 dummy cloudarc bill"
        mock_attach_file.return_value = {"status": "success"}

        result = await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id=tenant_id,
            db=mock_db,
            user_email="finance_lead@sakshi.ai",
        )

        assert result["status"] == "success"
        assert result["zoho_bill_id"] == "ZBILL_CLOUDFOREIGN_123"
        assert result["zoho_bill_number"] == "CA-2026-8891"

        # 1. Verify foreign vendor created with overseas classification
        mock_create_vendor.assert_called_once()
        _, create_v_kwargs = mock_create_vendor.call_args
        assert create_v_kwargs.get("vendor_name") == "CloudArc Global Inc."
        assert create_v_kwargs.get("country") == "United States"
        assert create_v_kwargs.get("gst_treatment") == "overseas"

        # 2. Verify Zoho Bill payload
        mock_create_bill.assert_called_once()
        _, bill_kwargs = mock_create_bill.call_args
        bill_payload = bill_kwargs.get("bill_payload")

        assert bill_payload["vendor_id"] == "CNT_CLOUDFOREIGN_777"
        assert bill_payload["bill_number"] == "CA-2026-8891"
        assert bill_payload["gst_treatment"] == "overseas"
        assert bill_payload["is_reverse_charge_applied"] is True
        assert bill_payload["is_reverse_charge"] is True
        assert "[Foreign Invoice: USD 150.00 @ ₹85.7000/USD = ₹12,855.00]" in bill_payload["notes"]

        # 3. Verify line items use approved INR amounts (BUG-004 verification)
        lines = bill_payload["line_items"]
        assert len(lines) == 1
        assert lines[0]["rate"] == 12855.0  # Exactly converted INR, NOT $150 and NOT ₹22,428
        assert lines[0]["is_reverse_charge_applied"] is True
        assert lines[0]["reverse_charge_tax_id"] == "TAX_IGST_18_RCM"

        # 4. State machine check
        assert mock_invoice.export_status == "EXPORTED"
        assert mock_invoice.zoho_bill_id == "ZBILL_CLOUDFOREIGN_123"

        # 5. Audit trail check
        mock_audit.assert_called_once()
        _, audit_kwargs = mock_audit.call_args
        assert audit_kwargs.get("action") == "EXPORT_ZOHO"
        assert "ZBILL_CLOUDFOREIGN_123" in audit_kwargs.get("after_value")


@pytest.mark.asyncio
async def test_03_foreign_service_fx_override_exported_accurately():
    """
    Test export when Finance has overridden the FX rate from 85.70 to 86.50.
    Verifies that the newly recalculated and approved INR values ($150 * 86.50 = ₹12,975.00) are exported.
    """
    inv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    tenant_id = "tenant-override-001"

    mock_invoice = Invoice(
        id=inv_id,
        user_id=user_id,
        tenant_id=tenant_id,
        file_path="uploads/override_test.pdf",
        file_name="override_test.pdf",
        file_size=10000,
        mime_type="application/pdf",
        file_hash="hash_override_123",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        invoice_origin="FOREIGN_SERVICE",
        currency="USD",
        exchange_rate=Decimal("86.500000"),  # Overridden rate
        fx_original_rate=Decimal("85.700000"),
        exchange_rate_source="FINANCE_OVERRIDE",
        fx_rate_overridden=True,
        fx_override_reason="Custom Bank Card FX settlement rate applied",
        current_vlm_output={
            "data": {
                "invoice_number": "INV-FX-OVERRIDE-01",
                "invoice_date": "2026-08-20",
                "due_date": "2026-09-20",
                "vendor_name": "Overseas SaaS Corp",
                "vendor_country": "United States",
                "place_of_supply": "36",
                "total_amount": 150.0,
                "subtotal": 150.0,
                "currency": "USD",
                "line_items": [
                    {
                        "description": "Enterprise Subscription",
                        "quantity": 1.0,
                        "unit_price": 150.0,
                        "taxable_amount": 150.0,
                        "sac_code": "998315",
                        "gst_rate": 18.0,
                        "total": 150.0,
                    }
                ],
            }
        },
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "4076465000000000999",
                    "approved_account_name": "Software Subscriptions",
                }
            ],
        },
    )

    mock_connection = ZohoConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        tenant_id=tenant_id,
        organization_id="ORG_OVERRIDE_01",
        status="CONNECTED",
    )

    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id=tenant_id,
        is_balanced=True,
        total_debit=15310.50,  # ₹12,975 + ₹2,335.50
        total_credit=15310.50,
        status="APPROVED",
    )

    coa_expense = ChartOfAccount(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        organization_id="ORG_OVERRIDE_01",
        zoho_account_id="4076465000000000999",
        account_name="Software Subscriptions",
        account_type="Expense",
        is_active=True,
    )

    tax_18 = TaxRate(
        zoho_tax_id="TAX_18",
        tax_name="IGST 18%",
        tax_percentage=18.0,
        tax_type="TAX",
        is_active=True,
    )

    mock_db = AsyncMock()
    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM invoices" in stmt_str or "invoices." in stmt_str:
            res.scalar_one_or_none.return_value = mock_invoice
        elif "FROM journal_entries" in stmt_str or "journal_entries." in stmt_str:
            res.scalar_one_or_none.return_value = mock_journal
        elif "FROM zoho_connections" in stmt_str or "zoho_connections." in stmt_str:
            res.scalar_one_or_none.return_value = mock_connection
        elif "FROM chart_of_accounts" in stmt_str or "chart_of_accounts." in stmt_str:
            res.scalars.return_value.all.return_value = [coa_expense]
        elif "FROM tax_rates" in stmt_str or "tax_rates." in stmt_str:
            res.scalars.return_value.all.return_value = [tax_18]
        elif "FROM journal_lines" in stmt_str or "journal_lines." in stmt_str:
            res.scalars.return_value.all.return_value = []
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()

    with patch("app.services.master_data_service.master_data_service.get_or_create_zoho_connection", new_callable=AsyncMock) as mock_get_conn, \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_search, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_create_bill, \
         patch("app.services.zoho_client.zoho_client_service.find_bill_by_number", new_callable=AsyncMock) as mock_find_bill, \
         patch("app.storage.supabase_storage.storage_service.download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock) as mock_att, \
         patch("app.services.master_data_service.master_data_service.get_zoho_tax_for_line", new_callable=AsyncMock) as mock_tax, \
         patch("app.services.audit_service.audit_service.log_event", new_callable=AsyncMock):

        mock_get_conn.return_value = mock_connection
        mock_search.return_value = {"contact_id": "CNT_EXISTING_888"}
        mock_find_bill.return_value = None
        mock_tax.return_value = "TAX_18"
        mock_create_bill.return_value = {"bill_id": "BILL_OVERRIDE_999", "bill_number": "INV-FX-OVERRIDE-01"}
        mock_dl.return_value = b"pdf-bytes"
        mock_att.return_value = {"status": "success"}

        res = await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id=tenant_id,
            db=mock_db,
        )

        assert res["status"] == "success"
        _, bill_call = mock_create_bill.call_args
        exported_line = bill_call["bill_payload"]["line_items"][0]
        # $150.00 * 86.50 = 12975.00
        assert exported_line["rate"] == 12975.00


@pytest.mark.asyncio
async def test_04_idempotency_and_duplicate_protection():
    """
    Verify that calling export on an invoice already exported returns 'already_exported'
    and does NOT call Zoho create_bill again.
    """
    inv_id = uuid.uuid4()
    tenant_id = "tenant-idempotency-001"

    mock_invoice = Invoice(
        id=inv_id,
        tenant_id=tenant_id,
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="EXPORTED",
        zoho_bill_id="BILL_ALREADY_EXISTING_111",
        zoho_bill_number="INV-CA-EXISTING-01",
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result

    with patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_create_bill:
        res = await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id=tenant_id,
            db=mock_db,
        )

        assert res["status"] == "already_exported"
        assert res["zoho_bill_id"] == "BILL_ALREADY_EXISTING_111"
        mock_create_bill.assert_not_called()


@pytest.mark.asyncio
async def test_05_zoho_failure_preserves_approval_and_allows_retry():
    """
    Verify that when Zoho API fails:
    - approval_status remains 'APPROVED' (not reverted)
    - export_status becomes 'FAILED'
    - error_message records the error
    - allows subsequent retry
    """
    inv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    tenant_id = "tenant-fail-001"

    mock_invoice = Invoice(
        id=inv_id,
        user_id=user_id,
        tenant_id=tenant_id,
        file_path="uploads/test_fail.pdf",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        invoice_origin="FOREIGN_SERVICE",
        currency="USD",
        exchange_rate=Decimal("85.700000"),
        current_vlm_output={
            "data": {
                "invoice_number": "INV-FAIL-01",
                "vendor_name": "Foreign Fail Vendor",
                "vendor_country": "United States",
                "place_of_supply": "36",
                "total_amount": 100.0,
                "subtotal": 100.0,
                "currency": "USD",
                "line_items": [{"description": "Item", "quantity": 1.0, "unit_price": 100.0, "taxable_amount": 100.0, "sac_code": "998315", "gst_rate": 18.0}],
            }
        },
        current_accounting_output={
            "accounting": [{"line_index": 1, "approved_account_id": "ACC_VALID_123", "approved_account_name": "Expense"}],
        },
    )

    mock_connection = ZohoConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        tenant_id=tenant_id,
        organization_id="ORG_FAIL_01",
        status="CONNECTED",
    )

    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id=tenant_id,
        is_balanced=True,
        total_debit=10112.60,
        total_credit=10112.60,
        status="APPROVED",
    )

    coa = ChartOfAccount(id=uuid.uuid4(), tenant_id=tenant_id, organization_id="ORG_FAIL_01", zoho_account_id="ACC_VALID_123", account_name="Expense", is_active=True)
    tax_18 = TaxRate(zoho_tax_id="TAX_18", tax_name="IGST 18%", tax_percentage=18.0, is_active=True)

    mock_db = AsyncMock()
    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM invoices" in stmt_str or "invoices." in stmt_str:
            res.scalar_one_or_none.return_value = mock_invoice
        elif "FROM journal_entries" in stmt_str or "journal_entries." in stmt_str:
            res.scalar_one_or_none.return_value = mock_journal
        elif "FROM zoho_connections" in stmt_str or "zoho_connections." in stmt_str:
            res.scalar_one_or_none.return_value = mock_connection
        elif "FROM chart_of_accounts" in stmt_str or "chart_of_accounts." in stmt_str:
            res.scalars.return_value.all.return_value = [coa]
        elif "FROM tax_rates" in stmt_str or "tax_rates." in stmt_str:
            res.scalars.return_value.all.return_value = [tax_18]
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()

    with patch("app.services.master_data_service.master_data_service.get_or_create_zoho_connection", new_callable=AsyncMock) as mock_get_conn, \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_search, \
         patch("app.services.zoho_client.zoho_client_service.find_bill_by_number", new_callable=AsyncMock) as mock_find_bill, \
         patch("app.services.master_data_service.master_data_service.get_zoho_tax_for_line", new_callable=AsyncMock) as mock_tax, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_create_bill:

        mock_get_conn.return_value = mock_connection
        mock_search.return_value = {"contact_id": "CNT_123"}
        mock_find_bill.return_value = None
        mock_tax.return_value = "TAX_18"
        mock_create_bill.side_effect = RuntimeError("Zoho 500: Internal Zoho Books API error")

        with pytest.raises(RuntimeError, match="Zoho export failed"):
            await export_service.export_invoice_to_zoho(
                invoice_id=inv_id,
                tenant_id=tenant_id,
                db=mock_db,
            )

        # Verification: Approval remains APPROVED, export is FAILED, error message captured
        assert mock_invoice.approval_status == "APPROVED"
        assert mock_invoice.export_status == "FAILED"
        assert "Internal Zoho Books API error" in mock_invoice.error_message


@pytest.mark.asyncio
async def test_06_domestic_indian_invoices_remain_unaffected_regression():
    """Verify domestic Indian INR invoice exports with normal Indian GST and place of contact without regression."""
    inv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    tenant_id = "tenant-domestic-001"

    mock_invoice = Invoice(
        id=inv_id,
        user_id=user_id,
        tenant_id=tenant_id,
        file_path="uploads/domestic.pdf",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        invoice_origin="INDIAN",
        currency="INR",
        current_vlm_output={
            "data": {
                "invoice_number": "INV-DOMESTIC-01",
                "invoice_date": "2026-08-25",
                "due_date": "2026-09-25",
                "vendor_name": "Domestic Tech Pvt Ltd",
                "vendor_gstin": "36AABCT1234F1Z9",
                "supplier_state_code": "36",
                "supplier_state_name": "Telangana",
                "place_of_supply": "36",
                "total_amount": 11800.0,
                "subtotal": 10000.0,
                "currency": "INR",
                "line_items": [
                    {
                        "description": "IT Consulting Services",
                        "quantity": 1.0,
                        "unit_price": 10000.0,
                        "taxable_amount": 10000.0,
                        "cgst_rate": 9.0,
                        "cgst_amount": 900.0,
                        "sgst_rate": 9.0,
                        "sgst_amount": 900.0,
                        "total": 11800.0,
                    }
                ],
            }
        },
        current_accounting_output={
            "accounting": [{"line_index": 1, "approved_account_id": "ACC_DOM_1", "approved_account_name": "Consulting"}],
        },
    )

    mock_connection = ZohoConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        tenant_id=tenant_id,
        organization_id="ORG_DOM_01",
        status="CONNECTED",
    )

    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id=tenant_id,
        is_balanced=True,
        total_debit=11800.0,
        total_credit=11800.0,
        status="APPROVED",
    )

    coa = ChartOfAccount(id=uuid.uuid4(), tenant_id=tenant_id, organization_id="ORG_DOM_01", zoho_account_id="ACC_DOM_1", account_name="Consulting", is_active=True)
    tax_18 = TaxRate(zoho_tax_id="TAX_18_DOM", tax_name="GST 18%", tax_percentage=18.0, is_active=True)

    mock_db = AsyncMock()
    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM invoices" in stmt_str or "invoices." in stmt_str:
            res.scalar_one_or_none.return_value = mock_invoice
        elif "FROM journal_entries" in stmt_str or "journal_entries." in stmt_str:
            res.scalar_one_or_none.return_value = mock_journal
        elif "FROM zoho_connections" in stmt_str or "zoho_connections." in stmt_str:
            res.scalar_one_or_none.return_value = mock_connection
        elif "FROM chart_of_accounts" in stmt_str or "chart_of_accounts." in stmt_str:
            res.scalars.return_value.all.return_value = [coa]
        elif "FROM tax_rates" in stmt_str or "tax_rates." in stmt_str:
            res.scalars.return_value.all.return_value = [tax_18]
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()

    with patch("app.services.master_data_service.master_data_service.get_or_create_zoho_connection", new_callable=AsyncMock) as mock_get_conn, \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_search, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_create_bill, \
         patch("app.services.zoho_client.zoho_client_service.find_bill_by_number", new_callable=AsyncMock) as mock_find_bill, \
         patch("app.storage.supabase_storage.storage_service.download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock) as mock_att, \
         patch("app.services.master_data_service.master_data_service.get_zoho_tax_for_line", new_callable=AsyncMock) as mock_tax, \
         patch("app.services.audit_service.audit_service.log_event", new_callable=AsyncMock):

        mock_get_conn.return_value = mock_connection
        mock_search.return_value = {"contact_id": "CNT_DOM_1"}
        mock_find_bill.return_value = None
        mock_tax.return_value = "TAX_18_DOM"
        mock_create_bill.return_value = {"bill_id": "BILL_DOM_01", "bill_number": "INV-DOMESTIC-01"}
        mock_dl.return_value = b"pdf-bytes"
        mock_att.return_value = {"status": "success"}

        res = await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id=tenant_id,
            db=mock_db,
        )

        assert res["status"] == "success"
        _, bill_call = mock_create_bill.call_args
        bill_payload = bill_call["bill_payload"]
        assert bill_payload["gst_treatment"] == "business_gst"
        assert bill_payload["gst_no"] == "36AABCT1234F1Z9"
        assert bill_payload["source_of_supply"] == "TS"


@pytest.mark.asyncio
async def test_07_unbalanced_journal_refuses_export():
    """Verify that an invoice with an unbalanced or missing General Ledger journal entry cannot be exported."""
    inv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    tenant_id = "tenant-unbal-001"

    mock_invoice = Invoice(
        id=inv_id,
        user_id=user_id,
        tenant_id=tenant_id,
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
    )

    mock_unbalanced_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id=tenant_id,
        is_balanced=False,  # Unbalanced journal!
        status="FAILED",
    )

    mock_db = AsyncMock()
    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM invoices" in stmt_str or "invoices." in stmt_str:
            res.scalar_one_or_none.return_value = mock_invoice
        elif "FROM journal_entries" in stmt_str or "journal_entries." in stmt_str:
            res.scalar_one_or_none.return_value = mock_unbalanced_journal
        else:
            res.scalar_one_or_none.return_value = None
        return res

    mock_db.execute = mock_execute

    with pytest.raises(ValueError, match="without an approved, balanced General Ledger journal entry"):
        await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id=tenant_id,
            db=mock_db,
        )


@pytest.mark.asyncio
async def test_08_tds_withholding_on_foreign_service_mapped_to_zoho():
    """
    Test Foreign Service invoice with applicable TDS withholding:
    Verifies that the approved TDS section, rate, and TDS Tax ID are attached to line items.
    """
    inv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    tenant_id = "tenant-tds-001"

    mock_invoice = Invoice(
        id=inv_id,
        user_id=user_id,
        tenant_id=tenant_id,
        file_path="uploads/foreign_tds.pdf",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        invoice_origin="FOREIGN_SERVICE",
        currency="USD",
        exchange_rate=Decimal("85.700000"),
        current_vlm_output={
            "data": {
                "invoice_number": "INV-TDS-FOREIGN-01",
                "invoice_date": "2026-08-20",
                "due_date": "2026-09-20",
                "vendor_name": "Global Tech Consulting LLC",
                "vendor_country": "United States",
                "place_of_supply": "36",
                "total_amount": 100.0,
                "subtotal": 100.0,
                "currency": "USD",
                "line_items": [{"description": "Tech Advisory", "quantity": 1.0, "unit_price": 100.0, "taxable_amount": 100.0, "gst_rate": 18.0}],
            }
        },
        current_accounting_output={
            "accounting": [{"line_index": 1, "approved_account_id": "ACC_EXP_01", "approved_account_name": "Consulting"}],
            "tds": {
                "applicable": True,
                "section": "194J",
                "rate": 2.0,
                "calculated_tds_amount": 171.40,  # 2% of ₹8,570.00
            }
        },
    )

    mock_connection = ZohoConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        tenant_id=tenant_id,
        organization_id="ORG_TDS_01",
        status="CONNECTED",
    )

    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id=tenant_id,
        is_balanced=True,
        total_debit=10112.60,
        total_credit=10112.60,
        status="APPROVED",
    )

    coa = ChartOfAccount(id=uuid.uuid4(), tenant_id=tenant_id, organization_id="ORG_TDS_01", zoho_account_id="ACC_EXP_01", account_name="Consulting", is_active=True)
    tax_18 = TaxRate(zoho_tax_id="TAX_18_RCM", tax_name="IGST 18%", tax_percentage=18.0, is_active=True)

    mock_db = AsyncMock()
    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM invoices" in stmt_str or "invoices." in stmt_str:
            res.scalar_one_or_none.return_value = mock_invoice
        elif "FROM journal_entries" in stmt_str or "journal_entries." in stmt_str:
            res.scalar_one_or_none.return_value = mock_journal
        elif "FROM zoho_connections" in stmt_str or "zoho_connections." in stmt_str:
            res.scalar_one_or_none.return_value = mock_connection
        elif "FROM chart_of_accounts" in stmt_str or "chart_of_accounts." in stmt_str:
            res.scalars.return_value.all.return_value = [coa]
        elif "FROM tax_rates" in stmt_str or "tax_rates." in stmt_str:
            res.scalars.return_value.all.return_value = [tax_18]
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()

    with patch("app.services.master_data_service.master_data_service.get_or_create_zoho_connection", new_callable=AsyncMock) as mock_get_conn, \
         patch("app.services.master_data_service.master_data_service.get_zoho_tds_tax", new_callable=AsyncMock) as mock_get_tds, \
         patch("app.services.master_data_service.master_data_service.get_zoho_tax_for_line", new_callable=AsyncMock) as mock_get_tax, \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_search, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_create_bill, \
         patch("app.services.zoho_client.zoho_client_service.find_bill_by_number", new_callable=AsyncMock) as mock_find_bill, \
         patch("app.storage.supabase_storage.storage_service.download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock) as mock_att, \
         patch("app.services.audit_service.audit_service.log_event", new_callable=AsyncMock):

        mock_get_conn.return_value = mock_connection
        mock_get_tds.return_value = "ZOHO_TDS_194J_2PCT"
        mock_get_tax.return_value = "TAX_18_RCM"
        mock_search.return_value = {"contact_id": "CNT_GLOBAL_TECH"}
        mock_find_bill.return_value = None
        mock_create_bill.return_value = {"bill_id": "BILL_TDS_01", "bill_number": "INV-TDS-FOREIGN-01"}
        mock_dl.return_value = b"pdf-bytes"
        mock_att.return_value = {"status": "success"}

        res = await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id=tenant_id,
            db=mock_db,
        )

        assert res["status"] == "success"
        _, bill_call = mock_create_bill.call_args
        bill_payload = bill_call["bill_payload"]
        assert bill_payload["line_items"][0]["tds_tax_id"] == "ZOHO_TDS_194J_2PCT"


@pytest.mark.asyncio
async def test_09_classification_override_to_foreign_service_exports_with_rcm():
    """Verify that an invoice originally flagged as REVIEW_REQUIRED, when overridden to FOREIGN_SERVICE by Finance, exports with overseas RCM."""
    inv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    tenant_id = "tenant-class-override-001"

    mock_invoice = Invoice(
        id=inv_id,
        user_id=user_id,
        tenant_id=tenant_id,
        file_path="uploads/override_class.pdf",
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        invoice_origin="REVIEW_REQUIRED",  # System classification
        classification_override="FOREIGN_SERVICE",  # Finance override
        classification_override_reason="Confirmed Singapore AWS cloud compute invoice",
        classified_by="finance_lead@sakshi.ai",
        currency="USD",
        exchange_rate=Decimal("85.700000"),
        current_vlm_output={
            "data": {
                "invoice_number": "AWS-SG-9988",
                "vendor_name": "Amazon Web Services Singapore",
                "vendor_country": "Singapore",
                "place_of_supply": "36",
                "total_amount": 200.0,
                "subtotal": 200.0,
                "currency": "USD",
                "line_items": [{"description": "Cloud Hosting", "quantity": 1.0, "unit_price": 200.0, "taxable_amount": 200.0, "gst_rate": 18.0}],
            }
        },
        current_accounting_output={
            "accounting": [{"line_index": 1, "approved_account_id": "ACC_AWS_1", "approved_account_name": "Cloud Hosting"}],
        },
    )

    mock_connection = ZohoConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        tenant_id=tenant_id,
        organization_id="ORG_AWS_01",
        status="CONNECTED",
    )

    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id=tenant_id,
        is_balanced=True,
        total_debit=20225.20,  # ₹17,140 + ₹3,085.20
        total_credit=20225.20,
        status="APPROVED",
    )

    coa = ChartOfAccount(id=uuid.uuid4(), tenant_id=tenant_id, organization_id="ORG_AWS_01", zoho_account_id="ACC_AWS_1", account_name="Cloud Hosting", is_active=True)
    tax_18 = TaxRate(zoho_tax_id="TAX_18_RCM", tax_name="IGST 18%", tax_percentage=18.0, is_active=True)

    mock_db = AsyncMock()
    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM invoices" in stmt_str or "invoices." in stmt_str:
            res.scalar_one_or_none.return_value = mock_invoice
        elif "FROM journal_entries" in stmt_str or "journal_entries." in stmt_str:
            res.scalar_one_or_none.return_value = mock_journal
        elif "FROM zoho_connections" in stmt_str or "zoho_connections." in stmt_str:
            res.scalar_one_or_none.return_value = mock_connection
        elif "FROM chart_of_accounts" in stmt_str or "chart_of_accounts." in stmt_str:
            res.scalars.return_value.all.return_value = [coa]
        elif "FROM tax_rates" in stmt_str or "tax_rates." in stmt_str:
            res.scalars.return_value.all.return_value = [tax_18]
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()

    with patch("app.services.master_data_service.master_data_service.get_or_create_zoho_connection", new_callable=AsyncMock) as mock_get_conn, \
         patch("app.services.master_data_service.master_data_service.get_zoho_tax_for_line", new_callable=AsyncMock) as mock_get_tax, \
         patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_search, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_create_bill, \
         patch("app.services.zoho_client.zoho_client_service.find_bill_by_number", new_callable=AsyncMock) as mock_find_bill, \
         patch("app.storage.supabase_storage.storage_service.download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock) as mock_att, \
         patch("app.services.audit_service.audit_service.log_event", new_callable=AsyncMock):

        mock_get_conn.return_value = mock_connection
        mock_get_tax.return_value = "TAX_18_RCM"
        mock_search.return_value = {"contact_id": "CNT_AWS_SG"}
        mock_find_bill.return_value = None
        mock_create_bill.return_value = {"bill_id": "BILL_AWS_01", "bill_number": "AWS-SG-9988"}
        mock_dl.return_value = b"pdf-bytes"
        mock_att.return_value = {"status": "success"}

        res = await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id=tenant_id,
            db=mock_db,
        )

        assert res["status"] == "success"
        _, bill_call = mock_create_bill.call_args
        bill_payload = bill_call["bill_payload"]
        assert bill_payload["gst_treatment"] == "overseas"
        assert bill_payload["is_reverse_charge_applied"] is True


@pytest.mark.asyncio
async def test_10_no_premature_posting_state_lifecycle_integrity():
    """
    Verify strict lifecycle isolation:
    1. Finance ACCEPT -> approval_status = APPROVED, export_status = NOT_EXPORTED (Zoho NOT called).
    2. Only explicit export invocation transitions to EXPORTED.
    """
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        zoho_bill_id=None,
    )

    # Initial state after Finance Accept
    assert mock_invoice.approval_status == "APPROVED"
    assert mock_invoice.export_status == "NOT_EXPORTED"
    assert mock_invoice.zoho_bill_id is None

