import pytest
import pytest_asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from sqlalchemy import select

from app.db.models import Invoice, HitlReview
from app.core.security import create_access_token
from app.main import app
from app.db.database import AsyncSessionLocal

@pytest.fixture
def admin_token():
    return create_access_token(
        user_id="admin-001", email="admin@sakshi.ai", tenant_id="tenant-1", role="ADMIN"
    )

@pytest.fixture
def data_reviewer_token():
    return create_access_token(
        user_id="dr-001", email="dr@sakshi.ai", tenant_id="tenant-1", role="DATA_REVIEWER"
    )

@pytest.fixture
def viewer_token():
    return create_access_token(
        user_id="v-001", email="v@sakshi.ai", tenant_id="tenant-1", role="VIEWER"
    )

@pytest.fixture
def finance_token():
    return create_access_token(
        user_id="f-001", email="f@sakshi.ai", tenant_id="tenant-1", role="FINANCE_REVIEWER"
    )

@pytest_asyncio.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session

@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_hitl_extraction_workflow(client: AsyncClient, db_session, admin_token, viewer_token, finance_token):
    from app.db.models import Tenant
    t_res = await db_session.execute(select(Tenant).where(Tenant.id == "tenant-1"))
    tenant = t_res.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(id="tenant-1", name="Test Tenant 1", slug="tenant-1")
        db_session.add(tenant)
        await db_session.commit()

    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id="tenant-1",
        file_path="mock.pdf",
        file_name="mock.pdf",
        file_size=100,
        mime_type="application/pdf",
        file_hash="hash" + str(uuid.uuid4()),
        status="UPLOADED"
    )
    db_session.add(invoice)
    await db_session.commit()

    invoice.raw_vlm_output = {"data": {"total_amount": 10000}}
    invoice.current_vlm_output = {"data": {"total_amount": 10000}}
    invoice.status = "HITL_REVIEW"
    await db_session.commit()
    
    assert invoice.accounting_output is None
    
    resp = await client.post(
        f"/api/v1/invoices/{invoice.id}/hitl/extraction/approve",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"corrected_data": {"data": {"total_amount": 10500, "subtotal": 10500, "tax_total": 0}}}
    )
    assert resp.status_code == 403

    resp = await client.post(
        f"/api/v1/invoices/{invoice.id}/hitl/extraction/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"corrected_data": {"data": {"total_amount": 10500, "subtotal": 10500, "tax_total": 0}}}
    )
    assert resp.status_code == 200

    await db_session.refresh(invoice)
    assert invoice.status in ("ACCOUNTING_PROCESSING", "FINAL_HITL_REVIEW")
    assert invoice.raw_vlm_output["data"]["total_amount"] == 10000 
    assert invoice.current_vlm_output["data"]["total_amount"] == 10500 
    
    hitl_q = await db_session.execute(select(HitlReview).where(HitlReview.invoice_id == invoice.id))
    reviews = hitl_q.scalars().all()
    assert len(reviews) == 1
    assert reviews[0].stage == "EXTRACTION"

    resp2 = await client.post(
        f"/api/v1/invoices/{invoice.id}/hitl/extraction/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"corrected_data": {"data": {"total_amount": 10500}}}
    )
    assert resp2.status_code == 409

    invoice.status = "FINAL_HITL_REVIEW"
    invoice.accounting_output = {"mock": "data"}
    await db_session.commit()
    
    resp_v = await client.post(
        f"/api/v1/invoices/{invoice.id}/hitl/final/approve",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"final_accounting": {}, "final_journal": {}}
    )
    assert resp_v.status_code == 403

    resp_f = await client.post(
        f"/api/v1/invoices/{invoice.id}/hitl/final/approve",
        headers={"Authorization": f"Bearer {finance_token}"},
        json={"final_accounting": {"corrected": True}, "final_journal": {}}
    )
    assert resp_f.status_code == 200

    await db_session.refresh(invoice)
    assert invoice.status in ("APPROVED", "HITL_COMPLETED")
    assert invoice.current_accounting_output["corrected"] is True
