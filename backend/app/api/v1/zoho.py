import logging
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    AuthenticatedUser,
    get_current_user,
    require_roles,
    encrypt_secret,
)
from app.db.database import get_db
from app.db.models import ZohoConnection, ChartOfAccount, TaxRate, Vendor
from app.services.zoho_client import zoho_client_service
from app.services.master_data_service import master_data_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/zoho", tags=["Zoho Integration"])


class SelectOrgRequest(BaseModel):
    organization_id: str
    organization_name: Optional[str] = None


class ZohoStatusResponse(BaseModel):
    connected: bool
    status: str
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    api_domain: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    accounts_count: int = 0
    taxes_count: int = 0
    vendors_count: int = 0
    error_message: Optional[str] = None


@router.get("/connect")
async def get_zoho_connect_url(
    accounts_url: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE"])),
):
    """
    Returns the Zoho OAuth2 authorization URL for user login.
    Requires ADMIN or FINANCE role.
    """
    tenant_id = current_user.tenant_id

    if not settings.ZOHO_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ZOHO_CLIENT_ID is not configured in backend environment.",
        )

    chosen_redirect = redirect_uri or settings.ZOHO_REDIRECT_URI
    auth_url = zoho_client_service.get_authorization_url(
        tenant_id=tenant_id,
        accounts_url=accounts_url,
        redirect_uri=chosen_redirect,
    )
    return {
        "authorization_url": auth_url,
        "redirect_uri": chosen_redirect,
        "client_id": settings.ZOHO_CLIENT_ID,
    }


@router.get("/callback")
async def zoho_oauth_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None),  # tenant_id passed as state
    accounts_server: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Handles Zoho OAuth 2.0 redirect callback, exchanges authorization code for tokens,
    encrypts tokens at rest, and saves connection details.
    Redirects browser seamlessly back to the frontend settings/connection page.
    """
    frontend_base = "http://localhost:3000/finance/settings"
    if settings.CORS_ORIGINS and len(settings.CORS_ORIGINS) > 0:
        frontend_base = f"{settings.CORS_ORIGINS[0].rstrip('/')}/finance/settings"

    # Handle user denial or OAuth error
    if error:
        logger.warning(f"Zoho OAuth authorization error: {error}")
        return RedirectResponse(
            url=f"{frontend_base}?zoho_status=error&error_detail={urllib.parse.quote(error)}",
            status_code=302,
        )

    if not code:
        logger.warning("Zoho OAuth callback called without authorization code.")
        return RedirectResponse(
            url=f"{frontend_base}?zoho_status=error&error_detail=Missing%20authorization%20code",
            status_code=302,
        )

    tenant_id = state or settings.DEFAULT_TENANT_ID
    logger.info(f"Processing Zoho OAuth callback for tenant {tenant_id}...")

    try:
        token_data = await zoho_client_service.exchange_code_for_tokens(
            code=code,
            accounts_url=accounts_server,
        )
    except Exception as e:
        logger.error(f"OAuth token exchange failed: {e}")
        return RedirectResponse(
            url=f"{frontend_base}?zoho_status=error&error_detail={urllib.parse.quote(str(e))}",
            status_code=302,
        )

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)
    api_domain = token_data.get("api_domain", settings.ZOHO_BOOKS_API_BASE_URL)

    # Fetch or create ZohoConnection record
    connection = await master_data_service.get_or_create_zoho_connection(tenant_id, db)
    connection.encrypted_access_token = encrypt_secret(access_token)
    if refresh_token:
        connection.encrypted_refresh_token = encrypt_secret(refresh_token)
    
    connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(0, expires_in - 120))
    connection.api_domain = api_domain
    connection.status = "CONNECTED"
    connection.error_message = None
    connection.updated_at = datetime.now(timezone.utc)

    # Fetch accessible organizations
    try:
        orgs = await zoho_client_service.get_organizations(
            access_token=access_token,
            api_domain=api_domain,
        )
        if orgs and len(orgs) == 1:
            connection.organization_id = str(orgs[0].get("organization_id"))
            connection.organization_name = orgs[0].get("name")
    except Exception as e:
        logger.warning(f"Could not automatically fetch orgs: {e}")
        orgs = []

    await db.commit()
    await db.refresh(connection)

    # Trigger automatic initial sync if org was selected
    if connection.organization_id:
        try:
            await master_data_service.sync_chart_of_accounts(tenant_id, db)
            await master_data_service.sync_taxes(tenant_id, db)
            await master_data_service.sync_vendors(tenant_id, db)
        except Exception as sync_exc:
            logger.warning(f"Initial sync warning: {sync_exc}")

    # Redirect to frontend settings with success params
    return RedirectResponse(
        url=f"{frontend_base}?zoho_status=connected&org_name={urllib.parse.quote(connection.organization_name or '')}",
        status_code=302,
    )


@router.get("/organizations")
async def list_zoho_organizations(
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE"])),
    db: AsyncSession = Depends(get_db),
):
    """Lists accessible organizations for the connected Zoho account."""
    tenant_id = current_user.tenant_id
    connection = await master_data_service.get_or_create_zoho_connection(tenant_id, db)
    if connection.status != "CONNECTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zoho account is not connected. Please authenticate first via /zoho/connect.",
        )

    access_token = await zoho_client_service.get_valid_access_token(connection, db)
    orgs = await zoho_client_service.get_organizations(
        access_token=access_token,
        api_domain=connection.api_domain,
    )
    return {"organizations": orgs}


@router.post("/select-org")
async def select_zoho_organization(
    req: SelectOrgRequest,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE"])),
    db: AsyncSession = Depends(get_db),
):
    """Sets the active Zoho Organization ID and triggers an initial COA, Tax, and Vendor sync."""
    tenant_id = current_user.tenant_id
    connection = await master_data_service.get_or_create_zoho_connection(tenant_id, db)
    if connection.status != "CONNECTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zoho account is not connected.",
        )

    connection.organization_id = req.organization_id
    if req.organization_name:
        connection.organization_name = req.organization_name
    connection.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # Trigger live sync
    accounts = await master_data_service.sync_chart_of_accounts(tenant_id, db)
    taxes = await master_data_service.sync_taxes(tenant_id, db)
    vendors = await master_data_service.sync_vendors(tenant_id, db)

    return {
        "status": "success",
        "message": f"Organization '{req.organization_name or req.organization_id}' selected and synced.",
        "accounts_synced": len(accounts),
        "taxes_synced": len(taxes),
        "vendors_synced": len(vendors),
    }


@router.post("/sync")
async def trigger_zoho_sync(
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE"])),
    db: AsyncSession = Depends(get_db),
):
    """Manually triggers synchronization of Chart of Accounts, Taxes, and Vendors from Zoho Books."""
    tenant_id = current_user.tenant_id
    accounts = await master_data_service.sync_chart_of_accounts(tenant_id, db)
    taxes = await master_data_service.sync_taxes(tenant_id, db)
    vendors = await master_data_service.sync_vendors(tenant_id, db)

    return {
        "status": "success",
        "accounts_synced": len(accounts),
        "taxes_synced": len(taxes),
        "vendors_synced": len(vendors),
    }


@router.get("/status", response_model=ZohoStatusResponse)
async def get_zoho_status(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns the current Zoho connection, organization, and cache metrics."""
    tenant_id = current_user.tenant_id
    connection = await master_data_service.get_or_create_zoho_connection(tenant_id, db)

    # Count cached records
    acc_count = (
        await db.execute(
            select(ChartOfAccount).where(ChartOfAccount.tenant_id == tenant_id)
        )
    ).scalars().all()
    tax_count = (
        await db.execute(
            select(TaxRate).where(TaxRate.tenant_id == tenant_id)
        )
    ).scalars().all()
    vendor_count = (
        await db.execute(
            select(Vendor).where(Vendor.tenant_id == tenant_id)
        )
    ).scalars().all()

    # Determine accurate status
    current_status = connection.status
    if connection.status == "CONNECTED" and not connection.organization_id:
        current_status = "ORGANIZATION_REQUIRED"

    return ZohoStatusResponse(
        connected=(connection.status == "CONNECTED"),
        status=current_status,
        organization_id=connection.organization_id,
        organization_name=connection.organization_name,
        api_domain=connection.api_domain,
        token_expires_at=connection.token_expires_at,
        last_sync_at=connection.updated_at,
        accounts_count=len(acc_count),
        taxes_count=len(tax_count),
        vendors_count=len(vendor_count),
        error_message=connection.error_message,
    )


@router.get("/master-data")
@router.get("/master-data-summary")
async def get_master_data_summary(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns lists of cached Chart of Accounts, Taxes, and Vendors for inspection."""
    tenant_id = current_user.tenant_id
    accounts = (
        await db.execute(
            select(ChartOfAccount).where(ChartOfAccount.tenant_id == tenant_id).order_by(ChartOfAccount.account_name)
        )
    ).scalars().all()
    taxes = (
        await db.execute(
            select(TaxRate).where(TaxRate.tenant_id == tenant_id).order_by(TaxRate.tax_percentage)
        )
    ).scalars().all()
    vendors = (
        await db.execute(
            select(Vendor).where(Vendor.tenant_id == tenant_id).order_by(Vendor.vendor_name)
        )
    ).scalars().all()

    accounts_list = [
        {
            "id": str(a.id),
            "zoho_account_id": a.zoho_account_id,
            "account_name": a.account_name,
            "account_code": a.account_code,
            "account_type": a.account_type,
            "is_active": a.is_active,
        }
        for a in accounts
    ]
    taxes_list = [
        {
            "id": str(t.id),
            "zoho_tax_id": t.zoho_tax_id,
            "tax_name": t.tax_name,
            "tax_percentage": t.tax_percentage,
            "tax_type": t.tax_type,
            "is_active": t.is_active,
        }
        for t in taxes
    ]
    vendors_list = [
        {
            "id": str(v.id),
            "zoho_contact_id": v.zoho_contact_id,
            "vendor_name": v.vendor_name,
            "gstin": v.gstin,
            "pan": v.pan,
            "approval_status": v.approval_status,
        }
        for v in vendors
    ]

    return {
        "accounts": accounts_list,
        "chart_of_accounts": accounts_list,
        "chart_of_accounts_count": len(accounts_list),
        "taxes": taxes_list,
        "tax_rates": taxes_list,
        "tax_rates_count": len(taxes_list),
        "vendors": vendors_list,
        "vendors_count": len(vendors_list),
    }


@router.post("/disconnect")
async def disconnect_zoho(
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE"])),
    db: AsyncSession = Depends(get_db),
):
    """Disconnects Zoho integration and removes stored tokens for the tenant."""
    tenant_id = current_user.tenant_id
    connection = await master_data_service.get_or_create_zoho_connection(tenant_id, db)
    connection.status = "DISCONNECTED"
    connection.encrypted_access_token = None
    connection.encrypted_refresh_token = None
    connection.token_expires_at = None
    connection.organization_id = None
    connection.organization_name = None
    connection.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "success", "message": "Zoho connection disconnected successfully."}
