import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.db.database import get_db
from app.db.models import Invoice, JournalEntry, ChartOfAccount, Tenant
from app.core.security import create_access_token


@pytest.fixture
def auth_headers():
    token = create_access_token(
        user_id=str(uuid.uuid4()),
        email="finance@default-org.com",
        tenant_id="default-tenant-001",
        role="FINANCE",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_journal_preview_not_found(auth_headers):
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            inv_id = str(uuid.uuid4())
            response = await client.get(f"/api/v1/invoices/{inv_id}/journal-preview", headers=auth_headers)
            assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_approve_invoice_flow(auth_headers):
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="dummyhash",
        status="COMPLETED",
        accounting_status="COMPLETED",
        approval_status="PENDING_REVIEW",
        current_vlm_output={
            "data": {
                "vendor_name": "Test Vendor",
                "vendor_gstin": "27ABCDE1234F1Z5",
                "total_amount": 1180.0,
                "subtotal": 1000.0,
                "cgst_amount": 90.0,
                "sgst_amount": 90.0,
                "line_items": [
                    {
                        "description": "Test Services",
                        "taxable_amount": 1000.0,
                        "cgst_amount": 90.0,
                        "sgst_amount": 90.0,
                        "total": 1180.0,
                    }
                ]
            }
        },
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "ACC_OFFICE_1",
                    "approved_account_name": "Office Expense",
                }
            ]
        },
    )

    mock_tenant = Tenant(id="default-tenant-001", name="Test Org", slug="test-org", books_closed_through_date=None)
    mock_db = AsyncMock()
    async def mock_exec_approve(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM invoices" in stmt_str or "invoices." in stmt_str:
            res.scalar_one_or_none.return_value = mock_invoice
        elif "FROM tenants" in stmt_str or "tenants." in stmt_str:
            res.scalar_one_or_none.return_value = mock_tenant
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res
    mock_db.execute = mock_exec_approve
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/api/v1/invoices/{str(inv_id)}/approve", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["approval_status"] == "APPROVED"
            assert data["is_balanced"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_reject_invoice_flow(auth_headers):
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="dummyhash",
        status="COMPLETED",
        approval_status="PENDING_REVIEW",
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/invoices/{str(inv_id)}/reject",
                json={"reason": "Incorrect vendor GSTIN provided"},
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["approval_status"] == "REJECTED"
            assert data["reason"] == "Incorrect vendor GSTIN provided"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_update_extraction_revalidates_and_preserves_raw_vlm(auth_headers):
    inv_id = uuid.uuid4()
    original_raw = {
        "data": {
            "vendor_name": "ABC Ltd",
            "vendor_gstin": "27ABCDE1234F1Z5",
            "subtotal": 1000.0,
            "cgst_amount": 90.0,
            "sgst_amount": 90.0,
            "total_amount": 1180.0,
            "line_items": [
                {
                    "description": "Consulting Services",
                    "taxable_amount": 1000.0,
                    "cgst_rate": 9.0,
                    "cgst_amount": 90.0,
                    "sgst_rate": 9.0,
                    "sgst_amount": 90.0,
                    "total": 1180.0,
                }
            ]
        }
    }
    
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="dummyhash",
        status="COMPLETED",
        accounting_status="COMPLETED",
        approval_status="PENDING_REVIEW",
        raw_vlm_output=original_raw,
        current_vlm_output=original_raw,
        accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "ACC_CONSULTING_1",
                    "approved_account_name": "Professional Fees",
                }
            ]
        },
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # User edits subtotal to 10500 and tax to 945 each, total to 12390
            updated_payload = {
                "current_vlm_output": {
                    "data": {
                        "vendor_name": "ABC Ltd Edited",
                        "vendor_gstin": "27ABCDE1234F1Z5",
                        "subtotal": 10500.0,
                        "cgst_amount": 945.0,
                        "sgst_amount": 945.0,
                        "tax_total": 1890.0,
                        "total_amount": 12390.0,
                        "line_items": [
                            {
                                "description": "Consulting Services (Revised)",
                                "taxable_amount": 10500.0,
                                "cgst_rate": 9.0,
                                "cgst_amount": 945.0,
                                "sgst_rate": 9.0,
                                "sgst_amount": 945.0,
                                "total": 12390.0,
                            }
                        ]
                    }
                }
            }
            response = await client.put(f"/api/v1/invoices/{str(inv_id)}", json=updated_payload, headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            
            # 1. raw_vlm_output remains completely untouched
            assert mock_invoice.raw_vlm_output["data"]["subtotal"] == 1000.0
            
            # 2. current_vlm_output is updated with authoritative customer data
            assert mock_invoice.current_vlm_output["data"]["subtotal"] == 10500.0
            assert mock_invoice.current_vlm_output["data"]["vendor_name"] == "ABC Ltd Edited"
            
            # 3. Stage 5 Financial Validation re-evaluated automatically
            assert mock_invoice.financial_validation_result is not None
            assert mock_invoice.financial_validation_result.get("overall_status") == "PASSED"
            
            # 4. Stage 6 Journal Entry updated with authoritative data
            assert mock_invoice.journal_entry is not None
            assert mock_invoice.journal_entry.get("total_debit") == 12390.0
            assert mock_invoice.journal_entry.get("total_credit") == 12390.0
            assert mock_invoice.journal_entry.get("difference") == 0.0
            assert mock_invoice.journal_entry.get("validation", {}).get("balanced") is True
            # Stale journal protection sets approval_status to PENDING
            assert mock_invoice.journal_entry.get("approval_status") == "PENDING"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_approve_journal_flow(auth_headers):
    inv_id = uuid.uuid4()
    balanced_journal = {
        "status": "BALANCED",
        "approval_status": "PENDING",
        "total_debit": 1180.0,
        "total_credit": 1180.0,
        "difference": 0.0,
        "is_balanced": True,
        "validation": {"balanced": True, "errors": [], "warnings": []},
        "lines": [
            {
                "account_id": "ACC_1",
                "account_name": "Office Expense",
                "line_type": "EXPENSE",
                "debit": 1000.0,
                "credit": 0.0,
            },
            {
                "account_id": "ACC_GST",
                "account_name": "Input CGST",
                "line_type": "INPUT_TAX",
                "debit": 90.0,
                "credit": 0.0,
            },
            {
                "account_id": "ACC_GST",
                "account_name": "Input SGST",
                "line_type": "INPUT_TAX",
                "debit": 90.0,
                "credit": 0.0,
            },
            {
                "account_id": "ACC_AP",
                "account_name": "Accounts Payable",
                "line_type": "ACCOUNTS_PAYABLE",
                "debit": 0.0,
                "credit": 1180.0,
            },
        ],
    }

    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="dummyhash",
        status="COMPLETED",
        accounting_status="COMPLETED",
        approval_status="PENDING_REVIEW",
        journal_entry=balanced_journal,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/invoices/{str(inv_id)}/journal/approve",
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["journal_status"] == "APPROVED"
            assert data["approval_status"] == "APPROVED"
            assert data["is_balanced"] is True
            assert mock_invoice.journal_entry["status"] == "APPROVED"
            assert mock_invoice.journal_entry["approval_status"] == "APPROVED"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_unbalanced_journal_cannot_be_approved(auth_headers):
    inv_id = uuid.uuid4()
    unbalanced_journal = {
        "status": "UNBALANCED",
        "approval_status": "PENDING",
        "total_debit": 1000.0,
        "total_credit": 1180.0,
        "difference": 180.0,
        "is_balanced": False,
        "validation": {"balanced": False, "errors": ["Debits != Credits"], "warnings": []},
        "lines": [],
    }

    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="dummyhash",
        status="COMPLETED",
        approval_status="PENDING_REVIEW",
        journal_entry=unbalanced_journal,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/invoices/{str(inv_id)}/journal/approve",
                headers=auth_headers,
            )
            assert response.status_code == 400
            assert "Cannot approve journal: Journal is unbalanced" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_stale_journal_protection_on_edit(auth_headers):
    inv_id = uuid.uuid4()
    approved_journal = {
        "status": "APPROVED",
        "approval_status": "APPROVED",
        "approved_by": "finance@default-org.com",
        "total_debit": 1180.0,
        "total_credit": 1180.0,
        "difference": 0.0,
        "is_balanced": True,
        "validation": {"balanced": True, "errors": [], "warnings": []},
    }

    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="dummyhash",
        status="COMPLETED",
        accounting_status="COMPLETED",
        approval_status="APPROVED",
        journal_entry=approved_journal,
        current_vlm_output={"data": {"subtotal": 1000.0, "total_amount": 1180.0, "vendor_name": "Test"}},
        raw_vlm_output={"data": {"subtotal": 1000.0, "total_amount": 1180.0, "vendor_name": "Test"}},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # User edits invoice data after approval
            edit_payload = {
                "current_vlm_output": {
                    "data": {
                        "vendor_name": "Updated Vendor",
                        "subtotal": 2000.0,
                        "cgst_amount": 180.0,
                        "sgst_amount": 180.0,
                        "total_amount": 2360.0,
                        "line_items": [
                            {
                                "description": "Updated Item",
                                "taxable_amount": 2000.0,
                                "cgst_rate": 9.0,
                                "cgst_amount": 180.0,
                                "sgst_rate": 9.0,
                                "sgst_amount": 180.0,
                                "total": 2360.0,
                            }
                        ],
                    }
                }
            }
            response = await client.put(f"/api/v1/invoices/{str(inv_id)}", json=edit_payload, headers=auth_headers)
            assert response.status_code == 200
            
            # Stale journal protection verified:
            # 1. Invoice approval status resets to PENDING_REVIEW
            assert mock_invoice.approval_status == "PENDING_REVIEW"
            # 2. Journal status resets to BALANCED and approval_status resets to PENDING
            assert mock_invoice.journal_entry["approval_status"] == "PENDING"
            assert mock_invoice.journal_entry["status"] == "BALANCED"
            assert mock_invoice.journal_entry["approved_by"] is None
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_itc_review_required_allows_zoho_export(auth_headers):
    inv_id = uuid.uuid4()
    balanced_journal = JournalEntry(
        id=uuid.uuid4(),
        invoice_id=inv_id,
        tenant_id="default-tenant-001",
        status="APPROVED",
        is_balanced=True,
        total_debit=1180.0,
        total_credit=1180.0,
        difference=0.0,
    )

    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="dummyhash",
        status="COMPLETED",
        accounting_status="COMPLETED",
        approval_status="APPROVED",
        export_status="NOT_EXPORTED",
        financial_validation_result={"overall_status": "PASSED"},
        itc_result={
            "status": "REVIEW_REQUIRED",
            "total_tax_amount": 180.0,
            "review_amount": 180.0,
            "reason": "Statutory document verification required under CGST Rule 36(4)",
        },
        journal_entry={
            "status": "APPROVED",
            "approval_status": "APPROVED",
            "is_balanced": True,
            "total_debit": 1180.0,
            "total_credit": 1180.0,
        },
        current_vlm_output={
            "data": {
                "vendor_name": "Test Tech Vendor",
                "vendor_gstin": "27ABCDE1234F1Z5",
                "invoice_number": "INV-2026-999",
                "invoice_date": "2026-03-01",
                "due_date": "2026-03-31",
                "subtotal": 1000.0,
                "cgst_amount": 90.0,
                "sgst_amount": 90.0,
                "total_amount": 1180.0,
            }
        },
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "460000000028001",
                    "approved_account_name": "Software & Tech Expense",
                }
            ]
        },
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_coa = ChartOfAccount(
        id=uuid.uuid4(),
        tenant_id="default-tenant-001",
        zoho_account_id="460000000028001",
        account_name="Software & Tech Expense",
        account_type="expense",
        is_active=True,
    )

    mock_db = AsyncMock()

    mock_tenant = Tenant(id="default-tenant-001", name="Test Org", slug="test-org", books_closed_through_date=None)
    async def mock_execute(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM invoices" in stmt_str or "invoices." in stmt_str:
            res.scalar_one_or_none.return_value = mock_invoice
        elif "FROM journal_entries" in stmt_str or "journal_entries." in stmt_str:
            res.scalar_one_or_none.return_value = balanced_journal
        elif "FROM tenants" in stmt_str or "tenants." in stmt_str:
            res.scalar_one_or_none.return_value = mock_tenant
        elif "FROM chart_of_accounts" in stmt_str or "chart_of_accounts." in stmt_str:
            res.scalars.return_value.all.return_value = [mock_coa]
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
         patch("app.services.zoho_client.zoho_client_service.attach_file_to_bill", new_callable=AsyncMock) as mock_att, \
         patch("app.services.master_data_service.master_data_service.get_zoho_tax_for_line", new_callable=AsyncMock) as mock_tax:
        
        mock_conn.return_value = MagicMock(status="CONNECTED", organization_id="org_123")
        mock_vendor.return_value = {"contact_id": "vend_123"}
        mock_find.return_value = None
        mock_tax.return_value = "tax_18"
        mock_bill.return_value = {"bill_id": "zoho_bill_999", "bill_number": "BILL-999"}
        mock_att.return_value = "attached"

        from app.services.export_service import export_service
        result = await export_service.export_invoice_to_zoho(
            invoice_id=inv_id,
            tenant_id="default-tenant-001",
            user_email="finance@default-org.com",
            db=mock_db,
        )

        assert result["status"] == "success"
        assert result["zoho_bill_id"] == "zoho_bill_999"
        assert mock_invoice.export_status == "EXPORTED"


@pytest.mark.asyncio
async def test_approve_tds_flow(auth_headers):
    inv_id = uuid.uuid4()
    mock_invoice = Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        file_hash="dummyhash",
        status="COMPLETED",
        accounting_status="COMPLETED",
        approval_status="PENDING_REVIEW",
        current_vlm_output={
            "data": {
                "vendor_name": "Consulting Partner",
                "subtotal": 50000.0,
                "cgst_amount": 4500.0,
                "sgst_amount": 4500.0,
                "total_amount": 59000.0,
            }
        },
        current_accounting_output={
            "accounting": [
                {
                    "line_index": 1,
                    "approved_account_id": "ACC_CONSULT",
                    "approved_account_name": "Professional Fees",
                }
            ],
            "tds": {
                "applicable": True,
                "tds_applicable": True,
                "tds_section": "194J",
                "nature_of_payment": "Professional Fees",
                "tds_rate": 10.0,
                "tds_base_amount": 50000.0,
                "proposed_tds_amount": 5000.0,
                "is_approved": False,
                "approval_status": "PENDING",
            }
        },
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invoice
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/invoices/{str(inv_id)}/tds/approve",
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["tds"]["is_approved"] is True
            assert data["tds"]["approval_status"] == "APPROVED"
            assert mock_invoice.current_accounting_output["tds"]["is_approved"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)


