import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.db.models import Invoice, ZohoConnection, ChartOfAccount, TaxRate, JournalEntry, Tenant
from app.services.export_service import export_service


@pytest.mark.asyncio
async def test_export_unapproved_invoice_rejected():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="hash_abc",
        status="COMPLETED",
        approval_status="PENDING_REVIEW",  # Not approved yet!
        export_status="NOT_EXPORTED",
    )
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result

    with pytest.raises(ValueError, match="must be APPROVED by Finance before exporting"):
        await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id="default-tenant-001",
            db=mock_db,
        )


@pytest.mark.asyncio
async def test_full_zoho_export_success_flow():
    inv_id = uuid.uuid4()
    tenant_id = "default-tenant-001"

    mock_invoice = Invoice(
        id=inv_id,
        tenant_id=tenant_id,
        file_path="uploads/invoice_test.pdf",
        file_name="invoice_test.pdf",
        file_size=5000,
        mime_type="application/pdf",
        file_hash="hash_12345",
        status="COMPLETED",
        accounting_status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        current_vlm_output={
            "data": {
                "invoice_number": "INV-ZOHO-99",
                "invoice_date": "2026-08-25",
                "due_date": "2026-09-25",
                "vendor_name": "Acme Cloud Infrastructure",
                "vendor_gstin": "27AABCA1234F1Z5",
                "vendor_pan": "AABCA1234F",
                "subtotal": 10000.0,
                "total_amount": 11800.0,
                "line_items": [
                    {
                        "description": "Cloud Servers",
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
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "4076465000000000558",
                    "approved_account_name": "Cloud Hosting & Infrastructure",
                }
            ],
            "tds": {
                "applicable": True,
                "tds_section": "194J",
                "calculated_tds_amount": 200.0,
            }
        },
    )

    mock_connection = ZohoConnection(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        organization_id="ORG_778899",
        organization_name="Test Org",
        status="CONNECTED",
        api_domain="https://www.zohoapis.in",
    )

    mock_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id=tenant_id,
        is_balanced=True,
        status="APPROVED",
    )

    coa = ChartOfAccount(id=uuid.uuid4(), tenant_id=tenant_id, zoho_account_id="4076465000000000558", account_name="Cloud Hosting & Infrastructure", is_active=True)
    tax_18 = TaxRate(zoho_tax_id="TAX_18", tax_name="GST 18%", tax_percentage=18.0, is_active=True)
    tds_tax = TaxRate(zoho_tax_id="TDS_194J", tax_name="Section 194J Technical Services (2%)", tax_percentage=2.0, tax_type="TDS", is_active=True)

    mock_tenant = Tenant(id=tenant_id, name="Test Org", slug="test-org", books_closed_through_date=None)

    mock_db = AsyncMock()
    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM invoices" in stmt_str or "invoices." in stmt_str:
            res.scalar_one_or_none.return_value = mock_invoice
        elif "FROM journal_entries" in stmt_str or "journal_entries." in stmt_str:
            res.scalar_one_or_none.return_value = mock_journal
        elif "FROM tenants" in stmt_str or "tenants." in stmt_str:
            res.scalar_one_or_none.return_value = mock_tenant
        elif "FROM zoho_connections" in stmt_str or "zoho_connections." in stmt_str:
            res.scalar_one_or_none.return_value = mock_connection
            res.scalars.return_value.all.return_value = [mock_connection]
        elif "FROM chart_of_accounts" in stmt_str or "chart_of_accounts." in stmt_str:
            res.scalars.return_value.all.return_value = [coa]
        elif "FROM tax_rates" in stmt_str or "tax_rates." in stmt_str:
            res.scalars.return_value.all.return_value = [tax_18, tds_tax]
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res
    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    with patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_search_vendor, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_create_bill, \
         patch("app.services.zoho_client.zoho_client_service.find_bill_by_number", new_callable=AsyncMock) as mock_find_bill, \
         patch("app.storage.supabase_storage.storage_service.download_file", new_callable=AsyncMock) as mock_download_file, \
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock) as mock_attach_file, \
         patch("app.services.audit_service.audit_service.log_event", new_callable=AsyncMock):

        mock_find_bill.return_value = None
        mock_search_vendor.return_value = {"contact_id": "CNT_VENDOR_555", "contact_name": "Acme Cloud Infrastructure"}
        mock_create_bill.return_value = {"bill_id": "BILL_998877", "bill_number": "INV-ZOHO-99"}
        mock_download_file.return_value = b"%PDF-1.4 dummy pdf bytes"
        mock_attach_file.return_value = {"status": "success"}

        result = await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id=tenant_id,
            db=mock_db,
        )

        assert result["status"] == "success"
        assert result["zoho_bill_id"] == "BILL_998877"
        assert result["zoho_bill_number"] == "INV-ZOHO-99"
        assert result["attachment_status"] == "attached"

        mock_search_vendor.assert_called_once()
        mock_create_bill.assert_called_once()
        mock_download_file.assert_called_once_with("uploads/invoice_test.pdf")
        mock_attach_file.assert_called_once()

        assert mock_invoice.export_status == "EXPORTED"
        assert mock_invoice.zoho_bill_id == "BILL_998877"
