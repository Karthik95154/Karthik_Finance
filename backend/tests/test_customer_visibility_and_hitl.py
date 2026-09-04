import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.database import get_db
from app.core.security import create_access_token
from app.db.models import Invoice, HitlReview


@pytest.fixture
def finance_token():
    return create_access_token(
        user_id="fin_user_1",
        email="finance@sakshi.ai",
        tenant_id="default-tenant-001",
        role="FINANCE",
    )


@pytest.fixture
def customer_token():
    return create_access_token(
        user_id="cust_user_1",
        email="customer@client.com",
        tenant_id="default-tenant-001",
        role="CUSTOMER",
    )


def create_mock_invoice(inv_id, status, approval_status):
    return Invoice(
        id=inv_id,
        tenant_id="default-tenant-001",
        user_id=None,
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        file_size=1024,
        mime_type="application/pdf",
        file_hash=f"hash-{inv_id}",
        status=status,
        approval_status=approval_status,
        accounting_status="COMPLETED" if approval_status == "APPROVED" else "PENDING",
        raw_vlm_output={"data": {"invoice_number": "INV-100", "total_amount": 1180.0, "vendor_name": "Test Vendor"}},
        current_vlm_output={"data": {"invoice_number": "INV-100", "total_amount": 1180.0, "vendor_name": "Test Vendor"}},
        accounting_output={"accounting": [{"line_index": 1, "approved_account_id": "ACC_1"}]},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_backend_1_customer_list_blocks_pending_review(customer_token):
    """BACKEND TEST 1: Invoice with approval_status = PENDING_REVIEW must NOT be returned to CUSTOMER."""
    inv_id = uuid.uuid4()
    mock_inv = create_mock_invoice(inv_id, status="PROCESSING_VLM", approval_status="PENDING_REVIEW")

    mock_db = AsyncMock()
    mock_res = MagicMock()
    # When query has WHERE approval_status == 'APPROVED', non-approved returns empty list
    mock_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {customer_token}"}
            res = await client.get("/api/v1/invoices", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert len(data) == 0
            # Verify that query filtered by APPROVED
            called_stmt = str(mock_db.execute.call_args[0][0])
            assert "invoices.approval_status = :approval_status_1" in called_stmt
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_backend_2_customer_list_blocks_final_hitl_review(customer_token):
    """BACKEND TEST 2: Invoice in FINAL_HITL_REVIEW must NOT be returned to CUSTOMER."""
    inv_id = uuid.uuid4()
    mock_inv = create_mock_invoice(inv_id, status="FINAL_HITL_REVIEW", approval_status="PENDING_REVIEW")

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {customer_token}"}
            res = await client.get("/api/v1/invoices", headers=headers)
            assert res.status_code == 200
            assert len(res.json()) == 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_backend_3_customer_list_blocks_pending_finance_approval(customer_token):
    """BACKEND TEST 3: Invoice with PENDING_FINANCE_APPROVAL must NOT be returned to CUSTOMER."""
    inv_id = uuid.uuid4()
    mock_inv = create_mock_invoice(inv_id, status="HITL_COMPLETED", approval_status="PENDING_FINANCE_APPROVAL")

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {customer_token}"}
            res = await client.get("/api/v1/invoices", headers=headers)
            assert res.status_code == 200
            assert len(res.json()) == 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_backend_4_customer_list_returns_approved_invoice(customer_token):
    """BACKEND TEST 4: Invoice with approval_status = APPROVED IS returned to CUSTOMER."""
    inv_id = uuid.uuid4()
    mock_inv = create_mock_invoice(inv_id, status="COMPLETED", approval_status="APPROVED")

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [mock_inv]
    mock_db.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {customer_token}"}
            res = await client.get("/api/v1/invoices", headers=headers)
            assert res.status_code == 200
            items = res.json()
            assert len(items) == 1
            assert items[0]["id"] == str(inv_id)
            assert items[0]["approval_status"] == "APPROVED"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_backend_5_customer_detail_blocked_for_non_approved(customer_token):
    """BACKEND TEST 5: GET /api/v1/invoices/{id} for non-approved invoice returns 403 Forbidden."""
    inv_id = uuid.uuid4()
    mock_inv = create_mock_invoice(inv_id, status="FINAL_HITL_REVIEW", approval_status="PENDING_REVIEW")

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_inv
    mock_db.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {customer_token}"}
            res = await client.get(f"/api/v1/invoices/{inv_id}", headers=headers)
            assert res.status_code == 403
            assert "awaiting internal Finance review" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_backend_6_customer_detail_allowed_for_approved(customer_token):
    """BACKEND TEST 6: GET /api/v1/invoices/{id} for APPROVED invoice returns 200 OK."""
    inv_id = uuid.uuid4()
    mock_inv = create_mock_invoice(inv_id, status="COMPLETED", approval_status="APPROVED")

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_inv
    mock_db.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {customer_token}"}
            res = await client.get(f"/api/v1/invoices/{inv_id}", headers=headers)
            assert res.status_code == 200
            assert res.json()["id"] == str(inv_id)
            assert res.json()["approval_status"] == "APPROVED"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_backend_7_hitl_approval_1(finance_token, customer_token):
    """
    BACKEND TEST 7: HITL Approval #1 (Extraction):
    - Records extraction HITL approval
    - Updates VLM/current extraction data
    - Moves status to ACCOUNTING_PROCESSING
    - Does NOT make invoice customer-visible (approval_status remains PENDING_REVIEW)
    """
    inv_id = uuid.uuid4()
    mock_inv = create_mock_invoice(inv_id, status="HITL_REVIEW", approval_status="PENDING_REVIEW")

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_inv
    mock_db.execute.return_value = mock_res
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {finance_token}"}
            payload = {"corrected_data": {"data": {"invoice_number": "INV-EDITED", "total_amount": 2000.0}}}
            res = await client.post(f"/api/v1/invoices/{inv_id}/hitl/extraction/approve", headers=headers, json=payload)
            assert res.status_code == 200

            # Verify state after Approval #1
            assert mock_inv.status == "ACCOUNTING_PROCESSING"
            assert mock_inv.approval_status == "PENDING_REVIEW"
            assert mock_inv.current_vlm_output == payload["corrected_data"]

            # Verify customer still blocked on detail
            cust_headers = {"Authorization": f"Bearer {customer_token}"}
            cust_res = await client.get(f"/api/v1/invoices/{inv_id}", headers=cust_headers)
            assert cust_res.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_backend_8_hitl_approval_2(finance_token, customer_token):
    """
    BACKEND TEST 8: HITL Approval #2 (Accounting):
    - Records final finance HITL review
    - Sets approval_status == "APPROVED" and status == "COMPLETED"
    - Customer list and detail endpoints can now return it
    """
    inv_id = uuid.uuid4()
    mock_inv = create_mock_invoice(inv_id, status="FINAL_HITL_REVIEW", approval_status="PENDING_REVIEW")

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_inv
    mock_db.execute.return_value = mock_res
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {finance_token}"}
            payload = {"final_accounting": {"accounting": [{"line_index": 1, "approved_account_id": "ACC_FIN"}]}, "final_journal": {}}
            res = await client.post(f"/api/v1/invoices/{inv_id}/hitl/final/approve", headers=headers, json=payload)
            assert res.status_code == 200

            # Verify state after Approval #2
            assert mock_inv.approval_status == "APPROVED"
            assert mock_inv.status == "COMPLETED"

            # Customer detail is now accessible!
            cust_headers = {"Authorization": f"Bearer {customer_token}"}
            cust_res = await client.get(f"/api/v1/invoices/{inv_id}", headers=cust_headers)
            assert cust_res.status_code == 200
            assert cust_res.json()["approval_status"] == "APPROVED"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_backend_9_customer_visibility_complete_flow(finance_token, customer_token):
    """
    BACKEND TEST 9: Complete Lifecycle Visibility Verification:
    - Before Approval #1: CUSTOMER cannot see invoice (in list or detail).
    - Between Approval #1 and Approval #2: CUSTOMER cannot see invoice (in list or detail).
    - After Approval #2: CUSTOMER can see invoice in list and detail.
    """
    inv_id = uuid.uuid4()
    mock_inv = create_mock_invoice(inv_id, status="HITL_REVIEW", approval_status="PENDING_REVIEW")

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_inv

    def dynamic_scalars():
        # Returns invoice in list query ONLY if approval_status == APPROVED
        if mock_inv.approval_status == "APPROVED":
            return MagicMock(all=MagicMock(return_value=[mock_inv]))
        return MagicMock(all=MagicMock(return_value=[]))

    mock_res.scalars.side_effect = dynamic_scalars
    mock_db.execute.return_value = mock_res
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            fin_headers = {"Authorization": f"Bearer {finance_token}"}
            cust_headers = {"Authorization": f"Bearer {customer_token}"}

            # Phase 1: Before Approval #1 (State: HITL_REVIEW)
            res_list_1 = await client.get("/api/v1/invoices", headers=cust_headers)
            assert len(res_list_1.json()) == 0
            res_detail_1 = await client.get(f"/api/v1/invoices/{inv_id}", headers=cust_headers)
            assert res_detail_1.status_code == 403

            # Execute HITL Approval #1
            res_app_1 = await client.post(
                f"/api/v1/invoices/{inv_id}/hitl/extraction/approve",
                headers=fin_headers,
                json={"corrected_data": {"data": {"total_amount": 1000.0}}}
            )
            assert res_app_1.status_code == 200

            # Phase 2: Between Approval #1 and Approval #2 (State: ACCOUNTING_PROCESSING / FINAL_HITL_REVIEW)
            mock_inv.status = "FINAL_HITL_REVIEW"  # Pipeline simulated finish
            res_list_2 = await client.get("/api/v1/invoices", headers=cust_headers)
            assert len(res_list_2.json()) == 0
            res_detail_2 = await client.get(f"/api/v1/invoices/{inv_id}", headers=cust_headers)
            assert res_detail_2.status_code == 403

            # Execute HITL Approval #2
            res_app_2 = await client.post(
                f"/api/v1/invoices/{inv_id}/hitl/final/approve",
                headers=fin_headers,
                json={"final_accounting": {"accounting": []}, "final_journal": {}}
            )
            assert res_app_2.status_code == 200
            assert mock_inv.approval_status == "APPROVED"

            # Phase 3: After Approval #2 (State: COMPLETED, approval_status: APPROVED)
            res_list_3 = await client.get("/api/v1/invoices", headers=cust_headers)
            assert len(res_list_3.json()) == 1
            assert res_list_3.json()[0]["id"] == str(inv_id)

            res_detail_3 = await client.get(f"/api/v1/invoices/{inv_id}", headers=cust_headers)
            assert res_detail_3.status_code == 200
            assert res_detail_3.json()["id"] == str(inv_id)
            assert res_detail_3.json()["approval_status"] == "APPROVED"
    finally:
        app.dependency_overrides.clear()
