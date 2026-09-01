import logging
import re
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
            or (isinstance(connection.token_expires_at, datetime) and connection.token_expires_at <= now)
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
        """Fetches tax rates, tax groups & tax authorities from Zoho Books."""
        res = await self._make_authorized_request(
            connection=connection,
            db=db,
            method="GET",
            endpoint_path="settings/taxes",
        )
        all_taxes = list(res.get("taxes", []))

        # Include Tax Groups (Crucial for Indian GST Intra-State CGST+SGST groups e.g. GST18, GST12, GST5, GST28)
        for tg in res.get("tax_groups", []):
            tg_id = str(tg.get("tax_group_id") or tg.get("tax_id"))
            tg_name = tg.get("tax_group_name") or tg.get("tax_name")
            tg_pct = float(
                tg.get("tax_group_percentage")
                if tg.get("tax_group_percentage") is not None
                else tg.get("tax_percentage", 0.0)
            )
            all_taxes.append({
                "tax_id": tg_id,
                "tax_name": tg_name,
                "tax_percentage": tg_pct,
                "tax_type": "tax_group",
                "is_value_added": tg.get("is_value_added", True),
            })

        return all_taxes

    async def get_tax_exemptions(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Fetches tax exemptions from Zoho Books settings."""
        try:
            res = await self._make_authorized_request(
                connection=connection,
                db=db,
                method="GET",
                endpoint_path="settings/taxexemptions",
            )
            return res.get("tax_exemptions", [])
        except Exception:
            return []

    async def get_bill_editpage(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Fetches bill configuration, payment terms, and statutory TDS taxes from Zoho Books."""
        return await self._make_authorized_request(
            connection=connection,
            db=db,
            method="GET",
            endpoint_path="bills/editpage",
        )

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

    def _normalize_name(self, name: Optional[str]) -> str:
        """Normalizes company/vendor names for reliable matching."""
        if not name:
            return ""
        cleaned = re.sub(r"[^A-Za-z0-9\s]", " ", name).lower()
        suffixes = [
            "private limited", "pvt ltd", "pvt", "limited", "ltd", "llp",
            "inc", "corp", "corporation", "enterprises", "solutions", "systems", "services"
        ]
        for s in suffixes:
            cleaned = re.sub(r"\b" + s + r"\b", "", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    async def search_vendor(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
        gstin: Optional[str] = None,
        pan: Optional[str] = None,
        vendor_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Searches for existing vendor contact by GSTIN, PAN, or Contact/Company Name.
        Strictly requires a genuine match — NEVER returns arbitrary contacts.
        """
        clean_gst = re.sub(r"[^A-Za-z0-9]", "", gstin).upper().strip() if gstin else None
        clean_pan = re.sub(r"[^A-Za-z0-9]", "", pan).upper().strip() if pan else None
        norm_input_name = self._normalize_name(vendor_name) if vendor_name else None

        # 1. Search by GSTIN if provided
        if clean_gst:
            res = await self._make_authorized_request(
                connection=connection,
                db=db,
                method="GET",
                endpoint_path="contacts",
                params={"contact_type": "vendor", "search_text": clean_gst},
            )
            for c in res.get("contacts", []):
                contact_gst = re.sub(r"[^A-Za-z0-9]", "", c.get("gst_no") or "").upper().strip()
                if contact_gst and contact_gst == clean_gst:
                    logger.info(f"Resolved Zoho vendor by GSTIN match: {c.get('contact_name')} ({c.get('contact_id')})")
                    return c

        # 2. Search by Vendor Name if provided
        if vendor_name:
            res = await self._make_authorized_request(
                connection=connection,
                db=db,
                method="GET",
                endpoint_path="contacts",
                params={"contact_type": "vendor", "search_text": vendor_name[:50]},
            )
            contacts = res.get("contacts", [])
            for c in contacts:
                c_name = (c.get("contact_name") or "").strip()
                c_comp = (c.get("company_name") or "").strip()

                # Exact name check
                if vendor_name.strip().lower() in (c_name.lower(), c_comp.lower()):
                    logger.info(f"Resolved Zoho vendor by exact name match: {c_name} ({c.get('contact_id')})")
                    return c

                # Normalized name check (e.g. 'Aravalli Software Systems Pvt Ltd' vs 'Aravalli Software Systems')
                if norm_input_name and (self._normalize_name(c_name) == norm_input_name or self._normalize_name(c_comp) == norm_input_name):
                    logger.info(f"Resolved Zoho vendor by normalized name match: {c_name} ({c.get('contact_id')})")
                    return c

        # 3. Search by PAN if provided
        if clean_pan:
            res = await self._make_authorized_request(
                connection=connection,
                db=db,
                method="GET",
                endpoint_path="contacts",
                params={"contact_type": "vendor", "search_text": clean_pan},
            )
            for c in res.get("contacts", []):
                contact_pan = re.sub(r"[^A-Za-z0-9]", "", c.get("pan_no") or "").upper().strip()
                if contact_pan and contact_pan == clean_pan:
                    logger.info(f"Resolved Zoho vendor by PAN match: {c.get('contact_name')} ({c.get('contact_id')})")
                    return c

        # No confident match found — Return None to allow dynamic vendor creation
        logger.info(f"No existing Zoho vendor matched for '{vendor_name}' (GSTIN: {gstin}).")
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
        state_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a new Vendor Contact in Zoho Books with proper GST state classification."""
        payload: Dict[str, Any] = {
            "contact_name": vendor_name,
            "company_name": vendor_name,
            "contact_type": "vendor",
        }

        # Normalize state to valid 2-letter Zoho state code (e.g. "TS", "MH", "KA", "TN", "AD", "DL")
        from app.services.gst_engine import normalize_indian_state, validate_gstin
        zoho_state_code, numeric_state_code, full_state_name = normalize_indian_state(
            state_input=state_name,
            gstin=gstin,
        )

        # Validate GSTIN format before passing to Zoho API
        is_valid_gst, clean_gst = validate_gstin(gstin)

        if is_valid_gst and clean_gst:
            payload["gst_no"] = clean_gst
            payload["gst_treatment"] = "business_gst"
        else:
            payload["gst_treatment"] = "business_none"

        # Zoho Books India Contact API strictly requires place_of_contact to be the 2-letter Zoho state code (e.g. "TS", "MH")
        if zoho_state_code:
            payload["place_of_contact"] = zoho_state_code

        if pan:
            clean_pan = re.sub(r"[^A-Za-z0-9]", "", pan).upper().strip()
            if len(clean_pan) == 10:
                payload["pan_no"] = clean_pan
        if email:
            payload["email"] = email
        if phone:
            payload["phone"] = phone

        billing_addr: Dict[str, Any] = {"country": "India"}
        if address:
            billing_addr["address"] = address
        if full_state_name:
            billing_addr["state"] = full_state_name
        if zoho_state_code:
            billing_addr["state_code"] = zoho_state_code
        payload["billing_address"] = billing_addr

        res = await self._make_authorized_request(
            connection=connection,
            db=db,
            method="POST",
            endpoint_path="contacts",
            json_data=payload,
        )
        return res.get("contact", {})

    async def update_vendor(
        self,
        connection: ZohoConnection,
        db: AsyncSession,
        contact_id: str,
        vendor_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Updates an existing Contact in Zoho Books."""
        payload = dict(vendor_payload)
        if "place_of_contact" in payload:
            from app.services.gst_engine import normalize_indian_state
            zoho_code, _, _ = normalize_indian_state(state_input=payload["place_of_contact"])
            if zoho_code:
                payload["place_of_contact"] = zoho_code

        res = await self._make_authorized_request(
            connection=connection,
            db=db,
            method="PUT",
            endpoint_path=f"contacts/{contact_id}",
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
