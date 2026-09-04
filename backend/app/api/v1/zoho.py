import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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


ZOHO_STATE_MAX_AGE_SECONDS = 900  # 15 minutes


def generate_signed_zoho_state(tenant_id: str, frontend_url: str = "http://localhost:3000", user_id: Optional[str] = None) -> str:
    """Generates an HMAC-SHA256 signed OAuth state token containing tenant_id, user_id, frontend_url, timestamp, and nonce."""
    secret = settings.AUTH_SECRET_KEY or "fallback-zoho-state-signing-key-production"
    state_payload = {
        "tenant_id": tenant_id,
        "user_id": str(user_id) if user_id else "",
        "frontend_url": frontend_url,
        "ts": int(time.time()),
        "nonce": uuid.uuid4().hex[:12],
    }
    payload_json = json.dumps(state_payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("utf-8")
    sig = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_signed_zoho_state(signed_state: Optional[str]) -> Dict[str, Any]:
    """
    Verifies the HMAC-SHA256 signature, structure, and expiration of the Zoho OAuth state parameter.
    Raises ValueError on any integrity, expiration, or format failure.
    """
    if not signed_state or "." not in signed_state:
        raise ValueError("Missing or malformed OAuth state parameter.")

    parts = signed_state.split(".")
    if len(parts) != 2:
        raise ValueError("Malformed OAuth state structure.")

    payload_b64, signature = parts[0], parts[1]
    secret = settings.AUTH_SECRET_KEY or "fallback-zoho-state-signing-key-production"
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        raise ValueError("Invalid OAuth state cryptographic signature.")

    try:
        payload_json = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
        payload = json.loads(payload_json)
    except Exception:
        raise ValueError("Could not decode OAuth state payload.")

    tenant_id = payload.get("tenant_id")
    ts = payload.get("ts")

    if not tenant_id or not ts:
        raise ValueError("OAuth state is missing required fields.")

    now = int(time.time())
    if now - int(ts) > ZOHO_STATE_MAX_AGE_SECONDS or int(ts) > now + 60:
        raise ValueError("OAuth state has expired. Please initiate connection again.")

    return payload


@router.get("/connect")
async def get_zoho_connect_url(
    request: Request,
    accounts_url: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE", "FINANCE_MANAGER", "DATA_REVIEWER"])),
):
    """
    Returns the Zoho OAuth2 authorization URL for user login with cryptographically signed state.
    """
    tenant_id = current_user.tenant_id
    user_id = current_user.id

    # Extract dynamic frontend URL to support dev tunnels smoothly
    origin = request.headers.get("origin") or request.headers.get("referer")
    if origin:
        from urllib.parse import urlparse
        parsed = urlparse(origin)
        frontend_url = f"{parsed.scheme}://{parsed.netloc}"
    else:
        frontend_url = settings.FRONTEND_URL.rstrip('/')

    state_param = generate_signed_zoho_state(tenant_id=tenant_id, user_id=user_id, frontend_url=frontend_url)

    if not settings.ZOHO_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ZOHO_CLIENT_ID is not configured in backend environment.",
        )

    chosen_redirect = redirect_uri or settings.ZOHO_REDIRECT_URI
    auth_url = zoho_client_service.get_authorization_url(
        tenant_id=state_param,
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
    request: Request,
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    accounts_server: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Handles Zoho OAuth 2.0 redirect callback, verifies cryptographic state signature,
    exchanges authorization code for tokens, encrypts tokens at rest, and saves user connection details.
    Redirects browser seamlessly back to the frontend settings/connection page.
    """
    frontend_base = f"{settings.FRONTEND_URL.rstrip('/')}/integrations"

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

    # Verify cryptographic HMAC signature on state parameter
    try:
        state_data = verify_signed_zoho_state(state)
        tenant_id = state_data["tenant_id"]
        user_id = state_data.get("user_id")
        if state_data.get("frontend_url"):
            frontend_base = f"{state_data['frontend_url'].rstrip('/')}/integrations"
    except ValueError as val_err:
        logger.warning(f"Zoho OAuth state verification failed: {val_err}")
        return RedirectResponse(
            url=f"{frontend_base}?zoho_status=error&error_detail={urllib.parse.quote(str(val_err))}",
            status_code=302,
        )

    logger.info(f"Processing Zoho OAuth callback for tenant {tenant_id} (user {user_id})...")

    # Determine redirect URI dynamically matching how the browser was routed
    callback_redirect_uri = str(request.url).split("?")[0]

    try:
        try:
            token_data = await zoho_client_service.exchange_code_for_tokens(
                code=code,
                redirect_uri=callback_redirect_uri,
                accounts_url=accounts_server,
            )
        except Exception:
            token_data = await zoho_client_service.exchange_code_for_tokens(
                code=code,
                redirect_uri=settings.ZOHO_REDIRECT_URI,
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

    # Fetch or create ZohoConnection record strictly for the verified tenant_id and user_id
    connection = await master_data_service.get_or_create_zoho_connection(tenant_id, db, user_id=user_id)
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
            await master_data_service.sync_chart_of_accounts(tenant_id, db, user_id=user_id)
            await master_data_service.sync_taxes(tenant_id, db, user_id=user_id)
            await master_data_service.sync_vendors(tenant_id, db, user_id=user_id)
        except Exception as sync_exc:
            logger.warning(f"Initial sync warning: {sync_exc}")

    # Redirect to frontend settings with success params
    return RedirectResponse(
        url=f"{frontend_base}?zoho_status=connected&org_name={urllib.parse.quote(connection.organization_name or '')}",
        status_code=302,
    )


@router.get("/organizations")
async def list_zoho_organizations(
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE", "FINANCE_MANAGER", "DATA_REVIEWER"])),
    db: AsyncSession = Depends(get_db),
):
    """Lists accessible organizations for the connected user's Zoho account."""
    tenant_id = current_user.tenant_id
    connection = await master_data_service.get_or_create_zoho_connection(tenant_id, db, user_id=current_user.id)
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
@router.post("/select-organization")
async def select_zoho_organization(
    req: SelectOrgRequest,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE", "FINANCE_MANAGER", "DATA_REVIEWER"])),
    db: AsyncSession = Depends(get_db),
):
    """Sets the active Zoho Organization ID and triggers an initial COA, Tax, and Vendor sync for the user."""
    tenant_id = current_user.tenant_id
    connection = await master_data_service.get_or_create_zoho_connection(tenant_id, db, user_id=current_user.id)
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
    accounts = await master_data_service.sync_chart_of_accounts(tenant_id, db, user_id=current_user.id)
    taxes = await master_data_service.sync_taxes(tenant_id, db, user_id=current_user.id)
    vendors = await master_data_service.sync_vendors(tenant_id, db, user_id=current_user.id)

    return {
        "status": "success",
        "message": f"Organization '{req.organization_name or req.organization_id}' selected and synced.",
        "accounts_synced": len(accounts),
        "taxes_synced": len(taxes),
        "vendors_synced": len(vendors),
    }


@router.post("/sync")
async def trigger_zoho_sync(
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE", "FINANCE_MANAGER", "DATA_REVIEWER"])),
    db: AsyncSession = Depends(get_db),
):
    """Manually triggers synchronization of Chart of Accounts, Taxes, and Vendors from Zoho Books for the authenticated user."""
    tenant_id = current_user.tenant_id
    accounts = await master_data_service.sync_chart_of_accounts(tenant_id, db, user_id=current_user.id)
    taxes = await master_data_service.sync_taxes(tenant_id, db, user_id=current_user.id)
    vendors = await master_data_service.sync_vendors(tenant_id, db, user_id=current_user.id)

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
    """Returns the current Zoho connection, organization, and cache metrics for the authenticated user."""
    tenant_id = current_user.tenant_id
    connection = await master_data_service.get_or_create_zoho_connection(tenant_id, db, user_id=current_user.id)

    # Count cached records for this tenant
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
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE", "FINANCE_MANAGER", "DATA_REVIEWER"])),
    db: AsyncSession = Depends(get_db),
):
    """Disconnects Zoho integration and removes stored tokens for the user."""
    tenant_id = current_user.tenant_id
    connection = await master_data_service.get_or_create_zoho_connection(tenant_id, db, user_id=current_user.id)
    connection.status = "DISCONNECTED"
    connection.encrypted_access_token = None
    connection.encrypted_refresh_token = None
    connection.token_expires_at = None
    connection.organization_id = None
    connection.organization_name = None
    connection.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "success", "message": "Zoho connection disconnected successfully."}
