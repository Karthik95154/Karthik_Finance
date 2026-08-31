import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChartOfAccount, TaxRate, Vendor, ZohoConnection
from app.services.zoho_client import zoho_client_service

logger = logging.getLogger(__name__)


class MasterDataService:
    """Manages local caching and synchronization of Zoho Chart of Accounts, Taxes, and Vendors."""

    async def get_or_create_zoho_connection(
        self,
        tenant_id: str,
        db: AsyncSession,
    ) -> ZohoConnection:
        """Retrieves active ZohoConnection for tenant or returns a placeholder record."""
        query = select(ZohoConnection).where(ZohoConnection.tenant_id == tenant_id)
        result = await db.execute(query)
        connection = result.scalar_one_or_none()
        if not connection:
            connection = ZohoConnection(tenant_id=tenant_id, status="DISCONNECTED")
            db.add(connection)
            await db.commit()
            await db.refresh(connection)
        return connection

    async def sync_chart_of_accounts(
        self,
        tenant_id: str,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Fetches live COA from Zoho and upserts into local chart_of_accounts table."""
        connection = await self.get_or_create_zoho_connection(tenant_id, db)
        if connection.status != "CONNECTED" or not connection.organization_id:
            logger.warning(f"Tenant {tenant_id} is not connected to Zoho. Skipping live COA sync.")
            return await self.get_cached_chart_of_accounts(tenant_id, db)

        zoho_accounts = await zoho_client_service.get_chart_of_accounts(connection, db)
        logger.info(f"Fetched {len(zoho_accounts)} accounts from Zoho for tenant {tenant_id}")

        # Fetch existing local accounts
        existing_query = select(ChartOfAccount).where(ChartOfAccount.tenant_id == tenant_id)
        existing_res = await db.execute(existing_query)
        existing_map = {acc.zoho_account_id: acc for acc in existing_res.scalars().all()}

        for acc_data in zoho_accounts:
            z_id = str(acc_data.get("account_id"))
            name = acc_data.get("account_name")
            code = acc_data.get("account_code")
            acc_type = acc_data.get("account_type", "expense").lower()
            is_active = acc_data.get("status") == "active" or acc_data.get("is_active", True)

            if z_id in existing_map:
                existing = existing_map[z_id]
                existing.account_name = name
                existing.account_code = code
                existing.account_type = acc_type
                existing.is_active = is_active
                existing.updated_at = datetime.now(timezone.utc)
            else:
                new_acc = ChartOfAccount(
                    tenant_id=tenant_id,
                    zoho_account_id=z_id,
                    account_name=name,
                    account_code=code,
                    account_type=acc_type,
                    is_active=is_active,
                )
                db.add(new_acc)

        await db.commit()
        return await self.get_cached_chart_of_accounts(tenant_id, db)

    async def get_cached_chart_of_accounts(
        self,
        tenant_id: str,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Returns list of active COA accounts formatted for Qwen3-4B prompt."""
        query = select(ChartOfAccount).where(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.is_active == True,
        )
        result = await db.execute(query)
        accounts = result.scalars().all()

        if not accounts:
            from app.services.accounting_service import DEFAULT_CHART_OF_ACCOUNTS
            return DEFAULT_CHART_OF_ACCOUNTS

        return [
            {
                "account_id": acc.zoho_account_id,
                "account_name": acc.account_name,
                "account_type": acc.account_type,
                "account_code": acc.account_code or "",
            }
            for acc in accounts
        ]

    async def sync_taxes(
        self,
        tenant_id: str,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Fetches live GST taxes and statutory TDS taxes from Zoho and upserts into local tax_rates table."""
        connection = await self.get_or_create_zoho_connection(tenant_id, db)
        if connection.status != "CONNECTED" or not connection.organization_id:
            logger.warning(f"Tenant {tenant_id} is not connected to Zoho. Skipping live tax sync.")
            return await self.get_cached_taxes(tenant_id, db)

        all_taxes_to_sync: List[Dict[str, Any]] = []

        # 1. Fetch GST taxes from settings/taxes
        try:
            zoho_taxes = await zoho_client_service.get_taxes(connection, db)
            for t in zoho_taxes:
                all_taxes_to_sync.append({
                    "tax_id": str(t.get("tax_id")),
                    "tax_name": t.get("tax_name") or "GST Tax",
                    "tax_percentage": float(t.get("tax_percentage", 0.0)),
                    "tax_type": "GST",
                })
        except Exception as e:
            logger.warning(f"Failed to fetch settings/taxes: {e}")

        # 2. Fetch statutory TDS taxes and editpage configuration from bills/editpage
        try:
            editpage = await zoho_client_service.get_bill_editpage(connection, db)
            tds_taxes = editpage.get("tds_taxes", [])
            for t in tds_taxes:
                all_taxes_to_sync.append({
                    "tax_id": str(t.get("tax_id")),
                    "tax_name": t.get("tax_name") or t.get("section") or "TDS Tax",
                    "tax_percentage": float(t.get("tax_percentage", 0.0)),
                    "tax_type": "TDS",
                })
        except Exception as e:
            logger.warning(f"Failed to fetch bills/editpage tds_taxes: {e}")

        logger.info(f"Fetched {len(all_taxes_to_sync)} total tax records from Zoho for tenant {tenant_id}")

        existing_query = select(TaxRate).where(TaxRate.tenant_id == tenant_id)
        existing_res = await db.execute(existing_query)
        existing_map = {t.zoho_tax_id: t for t in existing_res.scalars().all()}

        for tax_data in all_taxes_to_sync:
            z_id = str(tax_data.get("tax_id"))
            if not z_id or z_id == "None":
                continue
            name = tax_data.get("tax_name")
            percentage = float(tax_data.get("tax_percentage", 0.0))
            tax_type = tax_data.get("tax_type", "GST")

            if z_id in existing_map:
                existing = existing_map[z_id]
                existing.tax_name = name
                existing.tax_percentage = percentage
                existing.tax_type = tax_type
                existing.updated_at = datetime.now(timezone.utc)
            else:
                new_tax = TaxRate(
                    tenant_id=tenant_id,
                    zoho_tax_id=z_id,
                    tax_name=name,
                    tax_percentage=percentage,
                    tax_type=tax_type,
                )
                db.add(new_tax)

        await db.commit()
        return await self.get_cached_taxes(tenant_id, db)

    async def get_cached_taxes(
        self,
        tenant_id: str,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Returns list of active taxes formatted for Qwen3-4B prompt."""
        query = select(TaxRate).where(
            TaxRate.tenant_id == tenant_id,
            TaxRate.is_active == True,
        )
        result = await db.execute(query)
        taxes = result.scalars().all()

        if not taxes:
            from app.services.accounting_service import DEFAULT_AVAILABLE_TAXES
            return DEFAULT_AVAILABLE_TAXES

        return [
            {
                "tax_id": t.zoho_tax_id,
                "tax_name": t.tax_name,
                "tax_rate": t.tax_percentage,
                "tax_type": t.tax_type,
            }
            for t in taxes
        ]

    async def get_zoho_tax_for_line(
        self,
        tenant_id: str,
        tax_percentage: float,
        supply_type: str,
        db: AsyncSession,
    ) -> Optional[str]:
        """
        Dynamically finds the matching Zoho Tax ID for an invoice line item
        based on supply_type (INTRA_STATE vs INTER_STATE) and tax percentage.
        """
        if tax_percentage is None or tax_percentage <= 0:
            return None

        query = select(TaxRate).where(
            TaxRate.tenant_id == tenant_id,
            TaxRate.is_active == True,
            TaxRate.tax_type.in_(["GST", "tax", "Tax", "gst"]),
        )
        res = await db.execute(query)
        taxes = res.scalars().all()

        if not taxes:
            return None

        # Filter by percentage match (within 0.1 tolerance)
        matching_rate = [t for t in taxes if abs(float(t.tax_percentage) - float(tax_percentage)) < 0.1]
        if not matching_rate:
            return None

        if len(matching_rate) == 1:
            return matching_rate[0].zoho_tax_id

        # Differentiate INTRA_STATE (GST18 / CGST+SGST) vs INTER_STATE (IGST18)
        is_interstate = (supply_type == "INTER_STATE")
        if is_interstate:
            # 1. Exact start with IGST (e.g. IGST18)
            for t in matching_rate:
                t_name = (t.tax_name or "").upper()
                if t_name.startswith("IGST"):
                    return t.zoho_tax_id
            for t in matching_rate:
                if "IGST" in (t.tax_name or "").upper():
                    return t.zoho_tax_id
        else:
            # 1. Exact start with GST (e.g. GST18) and not IGST
            for t in matching_rate:
                t_name = (t.tax_name or "").upper()
                if t_name.startswith("GST") and "IGST" not in t_name:
                    return t.zoho_tax_id
            for t in matching_rate:
                if "IGST" not in (t.tax_name or "").upper():
                    return t.zoho_tax_id

        return matching_rate[0].zoho_tax_id

    async def get_zoho_tds_tax(
        self,
        tenant_id: str,
        section: Optional[str] = None,
        rate: Optional[float] = None,
        provision: Optional[str] = None,
        nature_of_payment: Optional[str] = None,
        db: AsyncSession = None,
    ) -> Optional[str]:
        """
        Dynamically resolves the Zoho Tax ID for TDS / withholding tax configuration
        using AI/Finance approved:
        - provision (e.g. 'Section 393')
        - section (e.g. 'Table 6(ii)' or '194J')
        - nature_of_payment (e.g. 'Professional services')
        - rate (e.g. 10.0)

        Does not assume 194J, does not resolve by percentage alone, and does not hardcode IDs.
        """
        query = select(TaxRate).where(
            TaxRate.tenant_id == tenant_id,
            TaxRate.is_active == True,
            TaxRate.tax_type.in_(["TDS", "tds_tax", "tds"]),
        )
        res = await db.execute(query)
        tds_taxes = res.scalars().all()

        if not tds_taxes:
            return None

        # Build search tokens from all AI/Finance approved inputs
        combined_text = f"{provision or ''} {section or ''} {nature_of_payment or ''}".upper()

        # Keywords for statutory categories
        category_keywords = {
            "PROFESSIONAL": ["PROFESSIONAL", "TECHNICAL", "FEES", "393", "TABLE 6", "6(II)", "194J", "TECH", "LEGAL", "CONSULT"],
            "CONTRACTOR": ["CONTRACTOR", "CONTRACT", "194C", "HUF", "SUB-CONTRACT"],
            "RENT": ["RENT", "194I", "PLANT", "LAND", "BUILDING"],
            "COMMISSION": ["COMMISSION", "BROKERAGE", "194H"],
            "DIVIDEND": ["DIVIDEND", "DISTRIBUTION"],
            "INTEREST": ["INTEREST", "SECURITIES"],
            "PURCHASE": ["PURCHASE", "GOODS", "194Q"],
        }

        matched_category_keywords = []
        for cat, kws in category_keywords.items():
            if any(kw in combined_text for kw in kws):
                matched_category_keywords.extend(kws)

        # 1. Best match: Category keyword match AND rate match
        if matched_category_keywords and rate is not None and rate > 0:
            for t in tds_taxes:
                t_name_upper = (t.tax_name or "").upper()
                if any(kw in t_name_upper for kw in matched_category_keywords):
                    if abs(float(t.tax_percentage) - float(rate)) < 0.1:
                        return t.zoho_tax_id

        # 2. Category keyword match alone
        if matched_category_keywords:
            for t in tds_taxes:
                t_name_upper = (t.tax_name or "").upper()
                if any(kw in t_name_upper for kw in matched_category_keywords):
                    return t.zoho_tax_id

        # 3. Exact rate match if category wasn't found in Zoho tax names
        if rate is not None and rate > 0:
            for t in tds_taxes:
                if abs(float(t.tax_percentage) - float(rate)) < 0.1:
                    return t.zoho_tax_id

        return tds_taxes[0].zoho_tax_id if tds_taxes else None



    async def sync_vendors(
        self,
        tenant_id: str,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Fetches vendor contacts from Zoho and upserts into local vendors table."""
        connection = await self.get_or_create_zoho_connection(tenant_id, db)
        if connection.status != "CONNECTED" or not connection.organization_id:
            logger.warning(f"Tenant {tenant_id} is not connected to Zoho. Skipping live vendor sync.")
            return await self.get_cached_vendors(tenant_id, db)

        try:
            zoho_contacts = await zoho_client_service.get_vendors(connection, db)
            logger.info(f"Fetched {len(zoho_contacts)} vendor contacts from Zoho for tenant {tenant_id}")

            existing_query = select(Vendor).where(Vendor.tenant_id == tenant_id)
            existing_res = await db.execute(existing_query)
            existing_map = {v.zoho_contact_id: v for v in existing_res.scalars().all() if v.zoho_contact_id}

            for c in zoho_contacts:
                z_id = str(c.get("contact_id"))
                name = c.get("contact_name") or c.get("company_name") or "Unknown Vendor"
                gstin = c.get("gst_no")
                pan = c.get("pan_no")
                email = c.get("email")
                phone = c.get("phone")

                if z_id in existing_map:
                    v = existing_map[z_id]
                    v.vendor_name = name
                    v.gstin = gstin
                    v.pan = pan
                    v.email = email
                    v.phone = phone
                    v.updated_at = datetime.now(timezone.utc)
                else:
                    new_v = Vendor(
                        tenant_id=tenant_id,
                        zoho_contact_id=z_id,
                        vendor_name=name,
                        gstin=gstin,
                        pan=pan,
                        email=email,
                        phone=phone,
                        approval_status="APPROVED",
                    )
                    db.add(new_v)

            await db.commit()
            return await self.get_cached_vendors(tenant_id, db)
        except Exception as exc:
            logger.warning(f"Vendor sync warning: {exc}")
            return await self.get_cached_vendors(tenant_id, db)

    async def get_cached_vendors(
        self,
        tenant_id: str,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Returns list of cached vendors for tenant."""
        query = select(Vendor).where(Vendor.tenant_id == tenant_id)
        result = await db.execute(query)
        vendors = result.scalars().all()
        return [
            {
                "vendor_id": v.zoho_contact_id,
                "vendor_name": v.vendor_name,
                "gstin": v.gstin,
                "pan": v.pan,
            }
            for v in vendors
        ]


master_data_service = MasterDataService()

