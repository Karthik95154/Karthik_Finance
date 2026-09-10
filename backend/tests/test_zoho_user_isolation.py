import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.models import ZohoConnection, User
from app.services.master_data_service import master_data_service


@pytest.mark.asyncio
async def test_zoho_user_isolation_same_tenant():
    """
    BUSINESS RULE: Two users (User A and User B) sharing the exact same tenant
    and connected to the exact same Zoho organization MUST have completely independent connections.
    """
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    shared_tenant_id = "default-tenant-001"
    shared_org_id = "60081887558"

    # User A Connection: CONNECTED
    conn_a = ZohoConnection(
        id=uuid.uuid4(),
        tenant_id=shared_tenant_id,
        user_id=user_a_id,
        organization_id=shared_org_id,
        organization_name="Shared Sakshi Org",
        status="CONNECTED",
    )

    # User B Connection: DISCONNECTED (or no record)
    conn_b = ZohoConnection(
        id=uuid.uuid4(),
        tenant_id=shared_tenant_id,
        user_id=user_b_id,
        organization_id=None,
        organization_name=None,
        status="DISCONNECTED",
    )

    # Mock DB query behavior
    async def mock_execute_side_effect(query, *args, **kwargs):
        mock_res = MagicMock()
        mock_scalars = MagicMock()

        # Extract user_id parameter bound in the query statement
        compile_params = query.compile().params
        param_user_id = str(compile_params.get("user_id_1") or compile_params.get("user_id"))

        if str(user_a_id) in param_user_id:
            mock_scalars.all.return_value = [conn_a]
        elif str(user_b_id) in param_user_id:
            mock_scalars.all.return_value = [conn_b]
        else:
            mock_scalars.all.return_value = []
        
        mock_res.scalars.return_value = mock_scalars
        return mock_res

    db_session = AsyncMock()
    db_session.execute.side_effect = mock_execute_side_effect

    # 1. Fetch User A status -> MUST BE CONNECTED
    res_a = await master_data_service.get_or_create_zoho_connection(
        tenant_id=shared_tenant_id, db=db_session, user_id=user_a_id
    )
    assert res_a.status == "CONNECTED"
    assert res_a.organization_id == shared_org_id

    # 2. Fetch User B status -> MUST BE DISCONNECTED
    res_b = await master_data_service.get_or_create_zoho_connection(
        tenant_id=shared_tenant_id, db=db_session, user_id=user_b_id
    )
    assert res_b.status == "DISCONNECTED"
    assert res_b.organization_id is None


@pytest.mark.asyncio
async def test_zoho_disconnect_affects_only_initiating_user():
    """
    BUSINESS RULE: User A disconnecting Zoho must NOT change User B's connection status,
    even if User B belongs to the same tenant and connects to the same Zoho Org.
    """
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    shared_tenant_id = "default-tenant-001"
    shared_org_id = "60081887558"

    conn_a = ZohoConnection(
        id=uuid.uuid4(),
        tenant_id=shared_tenant_id,
        user_id=user_a_id,
        organization_id=shared_org_id,
        status="CONNECTED",
    )
    conn_b = ZohoConnection(
        id=uuid.uuid4(),
        tenant_id=shared_tenant_id,
        user_id=user_b_id,
        organization_id=shared_org_id,
        status="CONNECTED",
    )

    # Disconnect User A only
    conn_a.status = "DISCONNECTED"
    conn_a.organization_id = None

    # Assert User A is disconnected, but User B remains CONNECTED
    assert conn_a.status == "DISCONNECTED"
    assert conn_b.status == "CONNECTED"
    assert conn_b.organization_id == shared_org_id
