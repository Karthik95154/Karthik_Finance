import logging
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import encrypt_secret, decrypt_secret
from app.db.models import ZohoConnection

logger = logging.getLogger(__name__)


class ZohoClientService:
    def __init__(self):
        self.client_id = settings.ZOHO_CLIENT_ID
        self.client_secret = settings.ZOHO_CLIENT_SECRET
        self.redirect_uri = settings.ZOHO_REDIRECT_URI
        self.accounts_url = settings.ZOHO_ACCOUNTS_URL.rstrip("/")
        self.default_api_url = settings.ZOHO_BOOKS_API_BASE_URL.rstrip("/")

    def get_authorization_url(
        self,
        tenant_id: str,
        redirect_uri: Optional[str] = None,
        scope: str = "ZohoBooks.fullaccess.all,ZohoBooks.settings.READ,ZohoBooks.contacts.READ,ZohoBooks.contacts.CREATE,ZohoBooks.bills.CREATE,ZohoBooks.bills.READ",
        accounts_url: Optional[str] = None,
    ) -> str:
        """Constructs the Zoho OAuth 2.0 authorization URL for user login."""
        base_accounts = (accounts_url or self.accounts_url).rstrip("/")
        params = {
            "scope": scope,
            "client_id": self.client_id,
            "response_type": "code",
            "access_type": "offline",
            "redirect_uri": redirect_uri or self.redirect_uri,
            "prompt": "consent",
            "state": tenant_id,
        }
        return f"{base_accounts}/oauth/v2/auth?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_tokens(
        self,
        code: str,
        redirect_uri: Optional[str] = None,
        accounts_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Exchanges an OAuth authorization code for Access & Refresh tokens."""
        base_accounts = (accounts_url or self.accounts_url).rstrip("/")
        token_url = f"{base_accounts}/oauth/v2/token"

        payload = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri or self.redirect_uri,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(token_url, data=payload)
            if response.status_code != 200:
                logger.error(f"Zoho token exchange failed [{response.status_code}]: {response.text}")
                raise RuntimeError(f"Failed to exchange Zoho auth code: {response.text}")

            data = response.json()
            if "error" in data:
                logger.error(f"Zoho token error response: {data}")
                raise RuntimeError(f"Zoho OAuth error: {data.get('error')}")

            return data

    async def refresh_access_token(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
    ) -> str:
        """
        Uses the encrypted refresh token to obtain a new access token and updates
        the database connection record.
        """
        if not connection.encrypted_refresh_token:
            raise ValueError("No refresh token available on Zoho connection.")

        refresh_token = decrypt_secret(connection.encrypted_refresh_token)
        base_accounts = self.accounts_url
        if connection.api_domain and ".com" in connection.api_domain:
            base_accounts = "https://accounts.zoho.com"
        elif connection.api_domain and ".in" in connection.api_domain:
            base_accounts = "https://accounts.zoho.in"
        elif connection.api_domain and ".eu" in connection.api_domain:
            base_accounts = "https://accounts.zoho.eu"

        token_url = f"{base_accounts}/oauth/v2/token"
        payload = {
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
        }

        logger.info(f"Refreshing Zoho access token for tenant {connection.tenant_id}...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(token_url, data=payload)
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Zoho token refresh failed [{response.status_code}]: {error_text}")
                connection.status = "ERROR"
                connection.error_message = f"Token refresh failed: {error_text}"
                await db.commit()
                raise RuntimeError(f"Failed to refresh Zoho token: {error_text}")

            data = response.json()
            if "error" in data:
                logger.error(f"Zoho token refresh returned error: {data}")
                connection.status = "ERROR"
                connection.error_message = f"OAuth error: {data.get('error')}"
                await db.commit()
                raise RuntimeError(f"Zoho OAuth error during refresh: {data.get('error')}")

            new_access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            api_domain = data.get("api_domain") or connection.api_domain

            connection.encrypted_access_token = encrypt_secret(new_access_token)
            connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 120)
            if api_domain:
                connection.api_domain = api_domain
            connection.status = "CONNECTED"
            connection.error_message = None
            connection.updated_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(f"Successfully refreshed access token for tenant {connection.tenant_id}")
            return new_access_token

    async def get_valid_access_token(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
    ) -> str:
        """Returns a decrypted active access token, automatically refreshing if expired."""
        now = datetime.now(timezone.utc)
        if (
            not connection.encrypted_access_token
            or not connection.token_expires_at
            or connection.token_expires_at <= now
        ):
            return await self.refresh_access_token(connection, db)

        return decrypt_secret(connection.encrypted_access_token)

    async def _make_authorized_request(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
        method: str,
        endpoint_path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Dispatches an authorized request to Zoho Books API with automatic 401 retry.
        """
        base_api = connection.api_domain.rstrip("/") if connection.api_domain else self.default_api_url
        if not base_api.endswith("/books/v3"):
            base_api = f"{base_api}/books/v3"

        url = f"{base_api}/{endpoint_path.lstrip('/')}"
        query_params = dict(params or {})
        if connection.organization_id:
            query_params["organization_id"] = connection.organization_id

        access_token = await self.get_valid_access_token(connection, db)
        req_headers = dict(headers or {})
        req_headers["Authorization"] = f"Zoho-oauthtoken {access_token}"

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.request(
                method=method,
                url=url,
                params=query_params,
                json=json_data,
                files=files,
                headers=req_headers,
            )

            # Auto-refresh on 401 and retry once
            if response.status_code == 401:
                logger.warning("Zoho API returned 401 Unauthorized. Refreshing token and retrying...")
                access_token = await self.refresh_access_token(connection, db)
                req_headers["Authorization"] = f"Zoho-oauthtoken {access_token}"
                response = await client.request(
                    method=method,
                    url=url,
                    params=query_params,
                    json=json_data,
                    files=files,
                    headers=req_headers,
                )

            if response.status_code not in (200, 201):
                error_msg = f"Zoho Books API error [{response.status_code}] on {method} {url}: {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            try:
                return response.json()
            except Exception:
                return {"text": response.text}

    async def get_organizations(
        self,
        access_token: str,
        api_domain: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves list of accessible Zoho Books organizations for the user."""
        base_api = (api_domain or self.default_api_url).rstrip("/")
        if not base_api.endswith("/books/v3"):
            base_api = f"{base_api}/books/v3"

        url = f"{base_api}/organizations"
        headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                raise RuntimeError(f"Failed to fetch Zoho organizations [{response.status_code}]: {response.text}")
            data = response.json()
            return data.get("organizations", [])

    async def get_chart_of_accounts(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Fetches active Chart of Accounts from Zoho Books."""
        res = await self._make_authorized_request(
            connection=connection,
            db=db,
            method="GET",
            endpoint_path="chartofaccounts",
        )
        return res.get("chartofaccounts", [])

    async def get_taxes(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Fetches tax rates & tax authorities from Zoho Books."""
        res = await self._make_authorized_request(
            connection=connection,
            db=db,
            method="GET",
            endpoint_path="settings/taxes",
        )
        return res.get("taxes", [])

    async def get_vendors(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Fetches vendor contacts from Zoho Books."""
        res = await self._make_authorized_request(
            connection=connection,
            db=db,
            method="GET",
            endpoint_path="contacts",
            params={"contact_type": "vendor"},
        )
        return res.get("contacts", [])

    async def search_vendor(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
        gstin: Optional[str] = None,
        pan: Optional[str] = None,
        vendor_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Searches for existing vendor contact by GSTIN, PAN, or Contact Name."""
        # 1. Search by name or keyword
        search_query = gstin or vendor_name
        if search_query:
            res = await self._make_authorized_request(
                connection=connection,
                db=db,
                method="GET",
                endpoint_path="contacts",
                params={"contact_type": "vendor", "search_text": search_query},
            )
            contacts = res.get("contacts", [])
            for c in contacts:
                # Exact match check
                if gstin and c.get("gst_no") == gstin:
                    return c
                if vendor_name and c.get("contact_name", "").lower() == vendor_name.lower():
                    return c
            if contacts:
                return contacts[0]

        return None

    async def create_vendor(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
        vendor_name: str,
        gstin: Optional[str] = None,
        pan: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a new Vendor Contact in Zoho Books."""
        payload: Dict[str, Any] = {
            "contact_name": vendor_name,
            "company_name": vendor_name,
            "contact_type": "vendor",
        }
        if gstin:
            payload["gst_no"] = gstin
            payload["gst_treatment"] = "business_gst"
        if pan:
            payload["pan_no"] = pan
        if email:
            payload["email"] = email
        if phone:
            payload["phone"] = phone
        if address:
            payload["billing_address"] = {"address": address}

        res = await self._make_authorized_request(
            connection=connection,
            db=db,
            method="POST",
            endpoint_path="contacts",
            json_data=payload,
        )
        return res.get("contact", {})

    async def create_bill(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
        bill_payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a Vendor Bill (`POST /bills`) in Zoho Books."""
        headers = {}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key

        res = await self._make_authorized_request(
            connection=connection,
            db=db,
            method="POST",
            endpoint_path="bills",
            json_data=bill_payload,
            headers=headers,
        )
        return res.get("bill", {})

    async def attach_file_to_bill(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
        bill_id: str,
        file_bytes: bytes,
        filename: str,
        mime_type: str = "application/pdf",
    ) -> Dict[str, Any]:
        """Attaches the original uploaded invoice document to the created Zoho Bill."""
        files = {
            "attachment": (filename, file_bytes, mime_type),
        }
        return await self._make_authorized_request(
            connection=connection,
            db=db,
            method="POST",
            endpoint_path=f"bills/{bill_id}/attachment",
            files=files,
        )

    async def find_bill_by_number(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
        bill_number: str,
        vendor_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Searches Zoho Books for an existing Bill matching a specific bill number.
        Validates vendor_id if provided to ensure authoritative reconciliation.
        """
        if not bill_number:
            return None

        params = {"bill_number": bill_number.strip()}
        if vendor_id:
            params["vendor_id"] = vendor_id

        try:
            res = await self._make_authorized_request(
                connection=connection,
                db=db,
                method="GET",
                endpoint_path="bills",
                params=params,
            )
            bills = res.get("bills", [])
            for b in bills:
                if b.get("bill_number", "").strip().lower() == bill_number.strip().lower():
                    if vendor_id and b.get("vendor_id") and str(b.get("vendor_id")) != str(vendor_id):
                        continue
                    return {
                        "bill_id": str(b.get("bill_id") or b.get("id")),
                        "bill_number": b.get("bill_number"),
                        "vendor_id": b.get("vendor_id"),
                        "status": b.get("status"),
                        "total": b.get("total"),
                    }
        except Exception as e:
            logger.warning(f"Error searching for existing Zoho Bill '{bill_number}': {e}")
        return None


zoho_client_service = ZohoClientService()
