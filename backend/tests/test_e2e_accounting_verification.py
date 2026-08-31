"""
End-to-End Accounting Verification Test Suite (Cases 1 to 8 + Full Lifecycle).
Simulates the entire pipeline:
Upload/VLM -> Accounting -> GST -> ITC -> TDS -> Financial Validation ->
Journal Generation -> Preview -> Approval -> Database Persistence -> Zoho Export.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.db.models import Invoice, JournalEntry, JournalLineModel, ZohoConnection, TaxRate
from app.services.gst_engine import gst_engine
from app.services.itc_engine import itc_engine
from app.services.tds_engine import tds_engine
from app.services.financial_validator import financial_validator
from app.services.journal_generator import journal_generator, sync_relational_journal
from app.api.v1.review import approve_invoice, get_journal_preview
from app.services.export_service import export_service
from app.core.security import AuthenticatedUser


@pytest.mark.asyncio
async def test_case_1_normal_intra_state_e2e():
    """CASE 1: Normal intra-state invoice (CGST + SGST). Balanced, approvable, relational DB synced, Zoho exportable."""
    vlm_payload = {
        "invoice_number": "INV-E2E-CASE1",
        "invoice_date": "2026-08-25",
        "vendor_name": "Apex Supplies Mumbai",
        "vendor_gstin": "27AAACA1234F1Z5",
        "customer_name": "Sakshi Tech Mumbai",
        "customer_gstin": "27BBBCB5678G1Z9",
        "document_type": "TAX_INVOICE",
        "subtotal": 50000.0,
        "cgst_amount": 4500.0,
        "sgst_amount": 4500.0,
        "tax_total": 9000.0,
        "total_amount": 59000.0,
        "line_items": [
            {
                "line_index": 1,
                "description": "Ergonomic Office Desks",
                "quantity": 5.0,
                "unit_price": 10000.0,
                "taxable_amount": 50000.0,
                "cgst_rate": 9.0,
                "cgst_amount": 4500.0,
                "sgst_rate": 9.0,
                "sgst_amount": 4500.0,
                "total": 59000.0,
                "business_purpose": "Office workstations for technology development team",
            }
        ]
    }

    # 1. Pipeline Stages
    accounting_data = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_3",
                "approved_account_name": "Office Furniture & Fixtures",
                "business_purpose": "Office workstations for technology development team",
            }
        ],
        "recipient_business_activity": "Software Product Development & IT Services",
    }
    gst_res = gst_engine.evaluate_gst(vlm_payload)
    itc_res = itc_engine.evaluate_itc(vlm_payload, accounting_data)
    fin_val_res = financial_validator.validate_invoice(vlm_payload, gst_res)

    assert gst_res["supply_type"] == "INTRA_STATE"
    assert itc_res["status"] == "ELIGIBLE"
    assert itc_res["eligible_itc"] == 9000.0
    assert fin_val_res["overall_status"] == "PASSED"

    # 2. Preview Journal
    preview = journal_generator.generate_journal(
        invoice_data=vlm_payload,
        accounting_classification=accounting_data,
        gst_result=gst_res,
        itc_result=itc_res,
        financial_validation_result=fin_val_res,
    )
    assert preview["validation"]["balanced"] is True
    assert preview["total_debit"] == 59000.0
    assert preview["total_credit"] == 59000.0

    # 3. Approval Flow Simulation
    inv_id = uuid.uuid4()
    mock_inv = Invoice(
        id=inv_id,
        tenant_id="tenant-e2e",
        status="COMPLETED",
        approval_status="PENDING_REVIEW",
        current_vlm_output={"data": vlm_payload},
        current_accounting_output=accounting_data,
        gst_result=gst_res,
        itc_result=itc_res,
        financial_validation_result=fin_val_res,
    )

    persisted_lines = []
    mock_db = MagicMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_inv
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    
    def capture_add(obj):
        if isinstance(obj, JournalLineModel):
            persisted_lines.append(obj)
    mock_db.add = MagicMock(side_effect=capture_add)

    user = AuthenticatedUser(id=str(uuid.uuid4()), email="finance@tenant-e2e.com", tenant_id="tenant-e2e", role="FINANCE")

    with patch("app.services.audit_service.audit_service.log_event", new_callable=AsyncMock):
        app_res = await approve_invoice(invoice_id=inv_id, current_user=user, db=mock_db)

    assert app_res["approval_status"] == "APPROVED"
    assert app_res["is_balanced"] is True

    # 4. JSONB == Relational DB Check
    jsonb_journal = mock_inv.journal_entry
    assert jsonb_journal["total_debit"] == 59000.0
    assert jsonb_journal["total_credit"] == 59000.0
    assert len(persisted_lines) == len(jsonb_journal["lines"])

    # 5. Zoho Export Payload Alignment Check
    mock_connection = ZohoConnection(id=uuid.uuid4(), tenant_id="tenant-e2e", status="CONNECTED", organization_id="ORG_1")
    mock_db_export = AsyncMock()
    mock_db_export.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_inv)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=JournalEntry(id=uuid.uuid4(), invoice_id=inv_id, is_balanced=True, status="APPROVED"))),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_connection)),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[TaxRate(zoho_tax_id="TAX_18", tax_percentage=18.0)])))),
    ]

    with patch("app.services.zoho_client.zoho_client_service.search_vendor", new_callable=AsyncMock) as mock_vend, \
         patch("app.services.zoho_client.zoho_client_service.create_bill", new_callable=AsyncMock) as mock_create_bill, \
         patch("app.storage.supabase_storage.storage_service.download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock), \
         patch("app.services.audit_service.audit_service.log_event", new_callable=AsyncMock):

        mock_vend.return_value = {"contact_id": "VEND_1"}
        mock_create_bill.return_value = {"bill_id": "BILL_CASE1", "bill_number": "INV-E2E-CASE1"}
        mock_dl.return_value = b"bytes"

        zoho_res = await export_service.export_invoice_to_zoho(invoice_id=inv_id, tenant_id="tenant-e2e", db=mock_db_export)
        assert zoho_res["zoho_bill_id"] == "BILL_CASE1"


@pytest.mark.asyncio
async def test_case_2_inter_state_e2e():
    """CASE 2: Inter-state invoice (IGST). Balanced, approvable, correctly books Input IGST."""
    vlm_payload = {
        "invoice_number": "INV-E2E-CASE2",
        "invoice_date": "2026-08-25",
        "vendor_name": "Cloud Providers Bangalore",
        "vendor_gstin": "29AAACA1234F1Z5",  # Karnataka
        "buyer_gstin": "27BBBCB5678G1Z9",   # Maharashtra
        "subtotal": 80000.0,
        "igst_amount": 14400.0,
        "tax_total": 14400.0,
        "total_amount": 94400.0,
        "line_items": [
            {
                "description": "Cloud Dedicated Servers",
                "taxable_amount": 80000.0,
                "igst_rate": 18.0,
                "igst_amount": 14400.0,
                "total": 94400.0,
            }
        ]
    }
    accounting_data = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_1",
                "approved_account_name": "Cloud Hosting & Infrastructure",
            }
        ]
    }
    gst_res = gst_engine.evaluate_gst(vlm_payload)
    itc_res = itc_engine.evaluate_itc(vlm_payload, accounting_data)
    fin_val_res = financial_validator.validate_invoice(vlm_payload, gst_res)

    assert gst_res["supply_type"] == "INTER_STATE"
    assert itc_res["status"] == "ELIGIBLE"
    assert itc_res["eligible_itc"] == 14400.0

    journal = journal_generator.generate_journal(
        invoice_data=vlm_payload,
        accounting_classification=accounting_data,
        gst_result=gst_res,
        itc_result=itc_res,
        financial_validation_result=fin_val_res,
    )
    assert journal["validation"]["balanced"] is True
    assert journal["total_debit"] == 94400.0
    assert journal["total_credit"] == 94400.0

    igst_lines = [l for l in journal["lines"] if l["account_id"] == "TAX_INP_IGST"]
    assert len(igst_lines) == 1
    assert igst_lines[0]["debit"] == 14400.0


@pytest.mark.asyncio
async def test_case_3_blocked_itc_e2e():
    """CASE 3: Blocked ITC invoice (Section 17(5)). Debits TAX_BLOCKED expense, 0 input tax asset."""
    vlm_payload = {
        "invoice_number": "INV-E2E-CASE3",
        "invoice_date": "2026-08-25",
        "vendor_name": "Grand Palace Hotel Mumbai",
        "vendor_gstin": "27AAACH1234F1Z5",
        "buyer_gstin": "27BBBCB5678G1Z9",
        "subtotal": 20000.0,
        "cgst_amount": 1800.0,
        "sgst_amount": 1800.0,
        "tax_total": 3600.0,
        "total_amount": 23600.0,
        "line_items": [
            {
                "description": "Executive Annual Family Vacation Suite & Food",
                "taxable_amount": 20000.0,
                "cgst_amount": 1800.0,
                "sgst_amount": 1800.0,
                "total": 23600.0,
            }
        ]
    }
    accounting_data = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_4",
                "approved_account_name": "Travel & Entertainment",
            }
        ]
    }
    gst_res = gst_engine.evaluate_gst(vlm_payload)
    itc_res = itc_engine.evaluate_itc(vlm_payload, accounting_data)

    assert itc_res["status"] == "INELIGIBLE"
    assert itc_res["blocked_itc"] == 3600.0
    assert itc_res["eligible_itc"] == 0.0

    journal = journal_generator.generate_journal(
        invoice_data=vlm_payload,
        accounting_classification=accounting_data,
        gst_result=gst_res,
        itc_result=itc_res,
    )
    assert journal["validation"]["balanced"] is True
    assert journal["total_debit"] == 23600.0
    assert journal["total_credit"] == 23600.0

    # Ensure no input tax asset
    assert len([l for l in journal["lines"] if l["line_type"] == "INPUT_TAX"]) == 0
    blocked_line = next(l for l in journal["lines"] if l["account_id"] == "TAX_BLOCKED")
    assert blocked_line["debit"] == 3600.0
    assert blocked_line["line_type"] == "EXPENSE"


@pytest.mark.asyncio
async def test_case_4_tds_invoice_e2e():
    """CASE 4: TDS invoice. Creates TDS_PAYABLE credit and reduces Accounts Payable correctly."""
    vlm_payload = {
        "invoice_number": "INV-E2E-CASE4",
        "invoice_date": "2026-08-25",
        "vendor_name": "KPMG Corporate Advisory",
        "vendor_gstin": "27AAACK1234F1Z5",
        "buyer_gstin": "27BBBCB5678G1Z9",
        "subtotal": 200000.0,
        "cgst_amount": 18000.0,
        "sgst_amount": 18000.0,
        "tax_total": 36000.0,
        "total_amount": 236000.0,
        "line_items": [
            {
                "description": "Financial & Tax Audit Advisory",
                "taxable_amount": 200000.0,
                "cgst_amount": 18000.0,
                "sgst_amount": 18000.0,
                "total": 236000.0,
            }
        ]
    }
    accounting_data = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_5",
                "approved_account_name": "Consulting & Legal Fees",
            }
        ],
        "tds": {
            "applicable": True,
            "tds_applicable": True,
            "is_approved": True,
            "tds_section": "194J",
            "final_tds_amount": 20000.0,  # 10% on 200,000
        }
    }
    gst_res = gst_engine.evaluate_gst(vlm_payload)
    itc_res = itc_engine.evaluate_itc(vlm_payload, accounting_data)

    journal = journal_generator.generate_journal(
        invoice_data=vlm_payload,
        accounting_classification=accounting_data,
        gst_result=gst_res,
        itc_result=itc_res,
    )
    assert journal["validation"]["balanced"] is True
    assert journal["total_debit"] == 236000.0
    assert journal["total_credit"] == 236000.0

    tds_line = next(l for l in journal["lines"] if l["line_type"] == "TDS_PAYABLE")
    ap_line = next(l for l in journal["lines"] if l["line_type"] == "ACCOUNTS_PAYABLE")

    assert tds_line["credit"] == 20000.0
    assert ap_line["credit"] == 216000.0  # 236,000 - 20,000


@pytest.mark.asyncio
async def test_case_5_financial_mismatch_blocks_approval():
    """CASE 5: Financial validation MISMATCH sets REVIEW_REQUIRED and blocks approval with 400."""
    vlm_payload = {
        "invoice_number": "INV-E2E-CASE5",
        "subtotal": 10000.0,
        "tax_total": 1800.0,
        "total_amount": 50000.0,  # Extreme mismatch
        "line_items": [{"description": "Item", "taxable_amount": 10000.0}],
    }
    accounting_data = {"accounting": [{"line_index": 1, "approved_account_id": "ACC_1", "approved_account_name": "Exp"}]}
    fin_val_res = {"overall_status": "MISMATCH", "errors": ["Total mismatch 50000 vs 11800"]}

    inv_id = uuid.uuid4()
    mock_inv = Invoice(
        id=inv_id,
        tenant_id="tenant-e2e",
        approval_status="PENDING_REVIEW",
        financial_validation_result=fin_val_res,
        current_vlm_output={"data": vlm_payload},
        current_accounting_output=accounting_data,
    )

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_inv
    mock_db.execute.return_value = mock_res
    user = AuthenticatedUser(id=str(uuid.uuid4()), email="finance@tenant-e2e.com", tenant_id="tenant-e2e", role="FINANCE")

    with pytest.raises(HTTPException) as exc_info:
        await approve_invoice(invoice_id=inv_id, current_user=user, db=mock_db)

    assert exc_info.value.status_code == 400
    assert "Stage 5 Financial Validation reported MISMATCH" in exc_info.value.detail


@pytest.mark.asyncio
async def test_case_6_itc_review_required():
    """CASE 6: ITC REVIEW_REQUIRED does not book unverified tax as eligible asset."""
    vlm_payload = {
        "invoice_number": "INV-E2E-CASE6",
        "subtotal": 50000.0,
        "tax_total": 9000.0,
        "cgst_amount": 4500.0,
        "sgst_amount": 4500.0,
        "total_amount": 59000.0,
        "line_items": [{"description": "Ambiguous Service", "taxable_amount": 50000.0}],
    }
    accounting_data = {"accounting": [{"line_index": 1, "approved_account_id": "ACC_1", "approved_account_name": "Exp"}]}
    itc_res = {
        "status": "REVIEW_REQUIRED",
        "eligible_itc": 0.0,
        "blocked_itc": 0.0,
        "reversal_itc": 0.0,
        "review_amount": 9000.0,
        "net_itc_available": 0.0,
    }

    journal = journal_generator.generate_journal(
        invoice_data=vlm_payload,
        accounting_classification=accounting_data,
        itc_result=itc_res,
    )

    assert journal["status"] == "REVIEW_REQUIRED"
    # Zero Input GST assets
    assert len([l for l in journal["lines"] if l["line_type"] == "INPUT_TAX"]) == 0


@pytest.mark.asyncio
async def test_case_7_shipping_other_charges_roundoff():
    """CASE 7: Shipping + other charges + round-off all reflected in balanced journal."""
    vlm_payload = {
        "invoice_number": "INV-E2E-CASE7",
        "subtotal": 2000.0,
        "shipping_charges": 200.0,
        "other_charges": 100.0,
        "round_off": 0.40,
        "tax_total": 360.0,
        "igst_amount": 360.0,
        "total_amount": 2660.40,
        "line_items": [{"description": "Components", "taxable_amount": 2000.0}],
    }
    accounting_data = {"accounting": [{"line_index": 1, "approved_account_id": "ACC_1", "approved_account_name": "Exp"}]}
    gst_res = {"supply_type": "INTER_STATE", "calculated": {"igst_amount": 360.0}}
    itc_res = {"status": "ELIGIBLE", "eligible_itc": 360.0}

    journal = journal_generator.generate_journal(
        invoice_data=vlm_payload,
        accounting_classification=accounting_data,
        gst_result=gst_res,
        itc_result=itc_res,
    )

    assert journal["validation"]["balanced"] is True
    assert journal["total_debit"] == 2660.40
    assert journal["total_credit"] == 2660.40

    acc_ids = [l["account_id"] for l in journal["lines"]]
    assert "ACC_12" in acc_ids  # Shipping
    assert "EXP_OTHER_CHARGES" in acc_ids  # Other charges
    assert "ROUND_OFF" in acc_ids  # Round-off


@pytest.mark.asyncio
async def test_case_8_previously_failing_armstrong_bug():
    """CASE 8: Previously failing ₹5,500 expense + ₹990 IGST = ₹6,490 must balance in Preview & Approval."""
    vlm_payload = {
        "invoice_number": "INV-2025-26-0778",
        "vendor_name": "Armstrong Technologies",
        "subtotal": 5500.0,
        "tax_total": 990.0,
        "igst_amount": 990.0,
        "total_amount": 6490.0,
        "line_items": [{"description": "Technical Consulting", "taxable_amount": 5500.0}],
    }
    accounting_data = {
        "accounting": [
            {
                "line_index": 1,
                "approved_account_id": "ACC_5",
                "approved_account_name": "Consulting & Professional Services",
            }
        ]
    }
    gst_res = {"supply_type": "INTER_STATE", "calculated": {"igst_amount": 990.0}}
    itc_res = {"status": "ELIGIBLE", "eligible_itc": 990.0}

    # 1. Preview
    preview = journal_generator.generate_journal_entry(
        invoice_data=vlm_payload,
        accounting_data=accounting_data,
        gst_result=gst_res,
        itc_result=itc_res,
        require_approved=False,
    )
    assert preview["is_balanced"] is True
    assert preview["total_debit"] == 6490.0
    assert preview["total_credit"] == 6490.0

    # 2. Approval
    approval = journal_generator.generate_journal_entry(
        invoice_data=vlm_payload,
        accounting_data=accounting_data,
        gst_result=gst_res,
        itc_result=itc_res,
        require_approved=True,
    )
    assert approval["is_balanced"] is True
    assert approval["total_debit"] == 6490.0
    assert approval["total_credit"] == 6490.0

    # Identity check
    assert preview["total_debit"] == approval["total_debit"]
    assert preview["total_credit"] == approval["total_credit"]
