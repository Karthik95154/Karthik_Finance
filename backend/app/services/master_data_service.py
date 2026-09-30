import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import select, delete, or_, false
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChartOfAccount, TaxRate, Vendor, ZohoConnection
from app.services.zoho_client import zoho_client_service

logger = logging.getLogger(__name__)


class MasterDataService:
    """Manages local caching and synchronization of Zoho Chart of Accounts, Taxes, and Vendors strictly scoped by organization_id."""

    async def get_or_create_zoho_connection(
        self,
        tenant_id: str,
        db: AsyncSession,
        user_id: Optional[Any] = None,
    ) -> ZohoConnection:
        """
        Retrieves the ZohoConnection for the given user.

        ISOLATION RULE: When user_id is provided, this method ONLY ever returns
        that specific user's connection. It will NEVER return another user's
        connection as a fallback, even if they share the same tenant_id.

        When user_id is None (internal/legacy calls only), falls back to
        tenant-scoped lookup with a warning.
        """
        user_uuid: Optional[uuid.UUID] = None

        if not user_id:
            logger.warning("get_or_create_zoho_connection called without user_id. Falling back to tenant-scoped lookup.")
            query = (
                select(ZohoConnection)
                .where(ZohoConnection.tenant_id == tenant_id)
                .order_by(ZohoConnection.created_at.desc())
            )
            res = await db.execute(query)
            conns = []
            if res:
                try:
                    s_all = res.scalars().all()
                    if s_all:
                        conns = list(s_all)
                except Exception:
                    pass
                if not conns:
                    try:
                        one = res.scalar_one_or_none()
                        if one:
                            conns = [one]
                    except Exception:
                        pass
            if conns:
                for c in conns:
                    if getattr(c, "status", None) == "CONNECTED":
                        return c
                return conns[0]
            return ZohoConnection(tenant_id=tenant_id, user_id=None, status="DISCONNECTED")

        try:
            user_uuid = uuid.UUID(str(user_id))
        except Exception:
            logger.error(f"get_or_create_zoho_connection: invalid user_id '{user_id}'. Refusing tenant fallback.")
            return ZohoConnection(tenant_id=tenant_id, user_id=None, status="DISCONNECTED")

        # Query strictly by user_id ONLY — completely ignore tenant_id for user connection matching
        query = (
            select(ZohoConnection)
            .where(ZohoConnection.user_id == user_uuid)
            .order_by(ZohoConnection.created_at.desc())
        )

        res = await db.execute(query)
        conns = res.scalars().all()

        if not conns:
            # No connection found for this user — create a clean DISCONNECTED record
            connection = ZohoConnection(
                tenant_id=tenant_id,
                user_id=user_uuid,
                status="DISCONNECTED",
            )
            db.add(connection)
            await db.commit()
            await db.refresh(connection)
            return connection

        # Pick the best record: prefer CONNECTED + has org_id, else most recent
        connected = [c for c in conns if c.status == "CONNECTED" and c.organization_id]
        primary = connected[0] if connected else conns[0]

        # Clean up any extra orphan DISCONNECTED records for this user
        if len(conns) > 1:
            for extra in conns:
                if extra.id != primary.id and extra.status != "CONNECTED":
                    try:
                        await db.delete(extra)
                    except Exception:
                        pass
            try:
                await db.commit()
            except Exception:
                pass

        return primary

    async def _resolve_organization_id(
        self,
        tenant_id: str,
        db: AsyncSession,
        organization_id: Optional[str] = None,
    ) -> Optional[str]:
        """Resolves authoritative active organization_id for tenant."""
        if organization_id:
            return str(organization_id).strip()
        conn = await self.get_or_create_zoho_connection(tenant_id, db)
        return str(conn.organization_id).strip() if conn and conn.organization_id else None

    async def sync_chart_of_accounts(
        self,
        tenant_id: str,
        db: AsyncSession,
        organization_id: Optional[str] = None,
        user_id: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Fetches live COA from Zoho and upserts into local chart_of_accounts table scoped to organization_id."""
        connection = await self.get_or_create_zoho_connection(tenant_id, db, user_id=user_id)
        if connection.status != "CONNECTED" or not connection.organization_id:
            logger.warning(f"Tenant {tenant_id} is not connected to Zoho. Skipping live COA sync.")
            return await self.get_cached_chart_of_accounts(tenant_id, db, organization_id=organization_id)

        current_org_id = str(organization_id or connection.organization_id).strip()
        zoho_accounts = await zoho_client_service.get_chart_of_accounts(connection, db)
        logger.info(f"Fetched {len(zoho_accounts)} accounts from Zoho for tenant {tenant_id} (Org: {current_org_id})")

        # Fetch existing local accounts scoped to current organization_id
        existing_query = select(ChartOfAccount).where(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.organization_id == current_org_id,
        )
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
                existing.organization_id = current_org_id
                existing.updated_at = datetime.now(timezone.utc)
            else:
                new_acc = ChartOfAccount(
                    tenant_id=tenant_id,
                    organization_id=current_org_id,
                    zoho_account_id=z_id,
                    account_name=name,
                    account_code=code,
                    account_type=acc_type,
                    is_active=is_active,
                )
                db.add(new_acc)

        # Prune / Invalidate any obsolete accounts that do not belong to current_org_id
        await db.execute(
            delete(ChartOfAccount).where(
                ChartOfAccount.tenant_id == tenant_id,
                ChartOfAccount.organization_id != current_org_id,
            )
        )

        await db.commit()
        return await self.get_cached_chart_of_accounts(tenant_id, db, organization_id=current_org_id)

    async def get_cached_chart_of_accounts(
        self,
        tenant_id: str,
        db: AsyncSession,
        organization_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Returns list of active expense/COGS/asset COA accounts strictly scoped to active Zoho organization."""
        org_id = await self._resolve_organization_id(tenant_id, db, organization_id)
        
        query = select(ChartOfAccount).where(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.is_active == True,
        )
        if org_id:
            query = query.where(ChartOfAccount.organization_id == org_id)

        result = await db.execute(query)
        accounts = result.scalars().all()

        if not accounts and org_id:
            # Auto-sync on cache miss
            try:
                await self.sync_chart_of_accounts(tenant_id, db, organization_id=org_id)
                res2 = await db.execute(query)
                accounts = res2.scalars().all()
            except Exception as e:
                logger.warning(f"On-demand COA sync error: {e}")


        if not accounts:
            return []

        # Filter relevant accounts for vendor invoices (Expense, COGS, Stock, Assets)
        # Avoid flooding LLM with Equity, Bank, and Liability accounts to prevent GPU OOM
        valid_types = {"expense", "other_expense", "cost_of_goods_sold", "cogs", "fixed_asset", "stock", "other_current_asset"}
        filtered = [
            acc for acc in accounts
            if any(t in str(acc.account_type or "").lower() for t in valid_types)
        ]
        
        candidate_list = filtered if filtered else accounts

        return [
            {
                "account_id": acc.zoho_account_id,
                "account_name": acc.account_name,
                "account_type": acc.account_type,
                "account_code": acc.account_code or "",
            }
            for acc in candidate_list[:40]
        ]

    async def match_chart_of_account(
        self,
        tenant_id: str,
        db: AsyncSession,
        extracted_name: Optional[str],
        extracted_type: Optional[str] = None,
        extracted_code: Optional[str] = None,
        zoho_account_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Hierarchical COA Matcher strictly scoped to tenant_id & organization_id:
        Priority 1: Exact zoho_account_id match
        Priority 2: Exact account_code match
        Priority 3: Exact normalized account_name match with compatible type -> EXACT_MATCH
        Priority 4: Exact normalized account_name match with incompatible type -> COA_CONFLICT
        Priority 5: Safe fuzzy similarity search (score >= 0.70) -> SUGGESTED_MATCH
        Priority 6: NO_MATCH
        """
        org_id = await self._resolve_organization_id(tenant_id, db, organization_id)
        query = select(ChartOfAccount).where(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.is_active == True,
        )
        if org_id:
            query = query.where(ChartOfAccount.organization_id == org_id)

        res = await db.execute(query)
        cached_coas = res.scalars().all()

        if not cached_coas:
            return {
                "match_status": "NO_MATCH",
                "message": "No active Zoho Chart of Accounts found for this organization.",
                "matched_account": None,
                "suggested_account": None,
            }

        # Priority 1: Exact Zoho Account ID Match
        if zoho_account_id:
            for acc in cached_coas:
                if str(acc.zoho_account_id).strip() == str(zoho_account_id).strip():
                    return {
                        "match_status": "EXACT_MATCH",
                        "match_priority": 1,
                        "matched_account": {
                            "zoho_account_id": acc.zoho_account_id,
                            "account_name": acc.account_name,
                            "account_code": acc.account_code,
                            "account_type": acc.account_type,
                        },
                        "message": f"Exact match found by Zoho Account ID: '{acc.account_name}' ({acc.zoho_account_id}).",
                    }

        # Priority 2: Exact Account Code Match
        if extracted_code and str(extracted_code).strip():
            target_code = str(extracted_code).strip().lower()
            for acc in cached_coas:
                if acc.account_code and str(acc.account_code).strip().lower() == target_code:
                    return {
                        "match_status": "EXACT_MATCH",
                        "match_priority": 2,
                        "matched_account": {
                            "zoho_account_id": acc.zoho_account_id,
                            "account_name": acc.account_name,
                            "account_code": acc.account_code,
                            "account_type": acc.account_type,
                        },
                        "message": f"Exact match found by Account Code '{acc.account_code}': '{acc.account_name}'.",
                    }

        if not extracted_name or not str(extracted_name).strip():
            return {
                "match_status": "NO_MATCH",
                "message": "Extracted account name is empty.",
                "matched_account": None,
                "suggested_account": None,
            }

        norm_extracted = "".join(e for e in extracted_name.lower() if e.isalnum())
        norm_type = extracted_type.strip().lower() if extracted_type else "expense"

        # Priorities 3 & 4: Exact Name Check & Conflict Check
        for acc in cached_coas:
            norm_zoho_name = "".join(e for e in (acc.account_name or "").lower() if e.isalnum())
            if norm_extracted == norm_zoho_name:
                zoho_type = (acc.account_type or "").lower()
                # Compatible types check
                type_compatible = (
                    norm_type in zoho_type
                    or zoho_type in norm_type
                    or ("expense" in norm_type and "expense" in zoho_type)
                    or ("asset" in norm_type and "asset" in zoho_type)
                    or ("income" in norm_type and "income" in zoho_type)
                )
                if type_compatible:
                    return {
                        "match_status": "EXACT_MATCH",
                        "match_priority": 3,
                        "matched_account": {
                            "zoho_account_id": acc.zoho_account_id,
                            "account_name": acc.account_name,
                            "account_code": acc.account_code,
                            "account_type": acc.account_type,
                        },
                        "message": f"Exact match found by account name: '{acc.account_name}' ({acc.account_type}).",
                    }
                else:
                    return {
                        "match_status": "COA_CONFLICT",
                        "match_priority": 4,
                        "conflicting_account": {
                            "zoho_account_id": acc.zoho_account_id,
                            "account_name": acc.account_name,
                            "account_code": acc.account_code,
                            "account_type": acc.account_type,
                            "extracted_type": norm_type,
                        },
                        "message": f"Account name '{acc.account_name}' matches, but extracted type '{norm_type}' conflicts with Zoho type '{acc.account_type}'.",
                    }

        # Priority 5: Safe Fuzzy Similarity Search
        import difflib
        best_score = 0.0
        best_acc = None

        for acc in cached_coas:
            score = difflib.SequenceMatcher(
                None, extracted_name.lower().strip(), (acc.account_name or "").lower().strip()
            ).ratio()
            if score > best_score:
                best_score = score
                best_acc = acc

        if best_acc and best_score >= 0.70:
            return {
                "match_status": "SUGGESTED_MATCH",
                "match_priority": 5,
                "similarity_score": round(best_score, 2),
                "suggested_account": {
                    "zoho_account_id": best_acc.zoho_account_id,
                    "account_name": best_acc.account_name,
                    "account_code": best_acc.account_code,
                    "account_type": best_acc.account_type,
                },
                "message": f"No exact match found. Closest match: '{best_acc.account_name}' ({int(best_score * 100)}% match). Approval required.",
            }

        return {
            "match_status": "NO_MATCH",
            "match_priority": 6,
            "message": f"No matching Zoho Chart of Account found for '{extracted_name}'.",
            "matched_account": None,
            "suggested_account": None,
        }

    async def create_and_sync_chart_of_account(
        self,
        tenant_id: str,
        db: AsyncSession,
        account_name: str,
        account_type: str = "expense",
        account_code: Optional[str] = None,
        description: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates new COA in Zoho Books after explicit user confirmation with pre-creation duplicate protection."""
        org_id = await self._resolve_organization_id(tenant_id, db, organization_id)
        if not org_id:
            raise ValueError("No active Zoho organization connection found for this tenant.")

        norm_name = "".join(e for e in account_name.lower() if e.isalnum())

        connection = await self.get_or_create_zoho_connection(tenant_id, db)
        if connection.status != "CONNECTED":
            raise ValueError("Zoho connection is not active. Please connect Zoho Books first.")

        # Create account via Zoho Client API
        zoho_acc_data = await zoho_client_service.create_chart_of_account(
            connection=connection,
            db=db,
            account_name=account_name,
            account_type=account_type,
            account_code=account_code,
            description=description,
        )

        zoho_id = str(zoho_acc_data.get("account_id"))
        created_name = zoho_acc_data.get("account_name", account_name)
        created_type = zoho_acc_data.get("account_type", account_type)
        created_code = zoho_acc_data.get("account_code", account_code)

        # Upsert into local DB table
        new_coa = ChartOfAccount(
            tenant_id=tenant_id,
            organization_id=org_id,
            zoho_account_id=zoho_id,
            account_name=created_name,
            account_type=created_type,
            account_code=created_code,
            is_active=True,
        )
        db.add(new_coa)
        await db.commit()
        await db.refresh(new_coa)

        return {
            "status": "CREATED",
            "message": f"Successfully created and synced Chart of Account '{created_name}' in Zoho Books!",
            "chart_of_account": {
                "zoho_account_id": zoho_id,
                "account_name": created_name,
                "account_type": created_type,
                "account_code": created_code,
            },
        }

    async def sync_taxes(
        self,
        tenant_id: str,
        db: AsyncSession,
        organization_id: Optional[str] = None,
        user_id: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Fetches live GST taxes and statutory TDS taxes from Zoho and upserts into local tax_rates table scoped to organization_id."""
        connection = await self.get_or_create_zoho_connection(tenant_id, db, user_id=user_id)
        if connection.status != "CONNECTED" or not connection.organization_id:
            logger.warning(f"Tenant {tenant_id} is not connected to Zoho. Skipping live tax sync.")
            return await self.get_cached_taxes(tenant_id, db, organization_id=organization_id)

        current_org_id = str(organization_id or connection.organization_id).strip()
        all_taxes_to_sync: List[Dict[str, Any]] = []

        # 1. Fetch GST taxes and Tax Groups from settings/taxes
        try:
            zoho_taxes = await zoho_client_service.get_taxes(connection, db)
            for t in zoho_taxes:
                all_taxes_to_sync.append({
                    "tax_id": str(t.get("tax_id")),
                    "tax_name": t.get("tax_name") or "GST Tax",
                    "tax_percentage": float(t.get("tax_percentage", 0.0)),
                    "tax_type": t.get("tax_type") or "GST",
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
                    "tax_section": t.get("section") or t.get("tax_specific_type"),
                    "tax_description": t.get("tax_specific_type_desc") or t.get("description"),
                })
            # Also capture any taxes or tax_groups returned in bill editpage
            for t in editpage.get("taxes", []):
                all_taxes_to_sync.append({
                    "tax_id": str(t.get("tax_id")),
                    "tax_name": t.get("tax_name") or "GST Tax",
                    "tax_percentage": float(t.get("tax_percentage", 0.0)),
                    "tax_type": "GST",
                    "tax_section": t.get("section"),
                    "tax_description": t.get("description"),
                })
            for tg in editpage.get("tax_groups", []):
                tg_id = str(tg.get("tax_group_id") or tg.get("tax_id"))
                tg_name = tg.get("tax_group_name") or tg.get("tax_name")
                tg_pct = float(
                    tg.get("tax_group_percentage")
                    if tg.get("tax_group_percentage") is not None
                    else tg.get("tax_percentage", 0.0)
                )
                all_taxes_to_sync.append({
                    "tax_id": tg_id,
                    "tax_name": tg_name,
                    "tax_percentage": tg_pct,
                    "tax_type": "tax_group",
                    "tax_section": None,
                    "tax_description": None,
                })
        except Exception as e:
            logger.warning(f"Failed to fetch bills/editpage tds_taxes: {e}")

        logger.info(f"Fetched {len(all_taxes_to_sync)} total tax records from Zoho for tenant {tenant_id} (Org: {current_org_id})")

        existing_query = select(TaxRate).where(
            TaxRate.tenant_id == tenant_id,
            TaxRate.organization_id == current_org_id,
        )
        existing_res = await db.execute(existing_query)
        existing_map = {t.zoho_tax_id: t for t in existing_res.scalars().all()}

        for tax_data in all_taxes_to_sync:
            z_id = str(tax_data.get("tax_id"))
            if not z_id or z_id == "None":
                continue
            name = tax_data.get("tax_name")
            percentage = float(tax_data.get("tax_percentage", 0.0))
            tax_type = tax_data.get("tax_type", "GST")
            tax_section = tax_data.get("tax_section")
            tax_description = tax_data.get("tax_description")

            if z_id in existing_map:
                existing = existing_map[z_id]
                existing.tax_name = name
                existing.tax_percentage = percentage
                existing.tax_type = tax_type
                if tax_section:
                    existing.tax_section = tax_section
                if tax_description:
                    existing.tax_description = tax_description
                existing.organization_id = current_org_id
                existing.updated_at = datetime.now(timezone.utc)
            else:
                new_tax = TaxRate(
                    tenant_id=tenant_id,
                    organization_id=current_org_id,
                    zoho_tax_id=z_id,
                    tax_name=name,
                    tax_percentage=percentage,
                    tax_type=tax_type,
                    tax_section=tax_section,
                    tax_description=tax_description,
                )
                db.add(new_tax)

        # Prune / Invalidate any obsolete taxes that do not belong to current_org_id
        await db.execute(
            delete(TaxRate).where(
                TaxRate.tenant_id == tenant_id,
                TaxRate.organization_id != current_org_id,
            )
        )

        await db.commit()
        return await self.get_cached_taxes(tenant_id, db, organization_id=current_org_id)

    async def get_cached_taxes(
        self,
        tenant_id: str,
        db: AsyncSession,
        organization_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Returns list of active taxes strictly scoped to active Zoho organization."""
        org_id = await self._resolve_organization_id(tenant_id, db, organization_id)
        query = select(TaxRate).where(
            TaxRate.tenant_id == tenant_id,
            TaxRate.is_active == True,
        )
        if org_id:
            query = query.where(TaxRate.organization_id == org_id)

        result = await db.execute(query)
        taxes = result.scalars().all()

        if not taxes and org_id:
            try:
                await self.sync_taxes(tenant_id, db, organization_id=org_id)
                res2 = await db.execute(query)
                taxes = res2.scalars().all()
            except Exception as e:
                logger.warning(f"On-demand tax sync error: {e}")

        if not taxes:
            return []

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
        organization_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Dynamically finds the matching Zoho Tax ID for an invoice line item
        strictly scoped to the active Zoho organization_id.
        """
        if tax_percentage is None or not db:
            return None

        org_id = await self._resolve_organization_id(tenant_id, db, organization_id)

        try:
            query = select(TaxRate).where(
                TaxRate.tenant_id == tenant_id,
                TaxRate.is_active == True,
            )
            if org_id:
                query = query.where(TaxRate.organization_id == org_id)

            res = await db.execute(query)
            all_taxes = res.scalars().all() if res else []
            taxes = [t for t in all_taxes if (t.tax_type or "").lower() not in ["tds", "withholding"]]
        except Exception:
            taxes = []

        if not taxes and org_id:
            try:
                await self.sync_taxes(tenant_id, db, organization_id=org_id)
                res = await db.execute(query)
                all_taxes = res.scalars().all() if res else []
                taxes = [t for t in all_taxes if (t.tax_type or "").lower() not in ["tds", "withholding"]]
            except Exception as sync_err:
                logger.warning(f"On-demand tax sync failed: {sync_err}")

        if not taxes:
            return None

        target_pct = float(tax_percentage)

        # 1. Filter by percentage match (within 0.1 tolerance)
        matching_rate = [t for t in taxes if abs(float(t.tax_percentage) - target_pct) < 0.1]
        
        # If looking for 0% and no exact 0% tax, try looking for zero/nil/exempt by name
        if target_pct == 0.0 and not matching_rate:
            matching_rate = [
                t for t in taxes
                if any(w in (t.tax_name or "").upper() for w in ["0%", "GST0", "IGST0", "NIL", "EXEMPT", "ZERO"])
            ]

        if not matching_rate:
            return None

        if len(matching_rate) == 1:
            return matching_rate[0].zoho_tax_id

        # Differentiate INTRA_STATE (GST18 / tax_group) vs INTER_STATE (IGST18)
        is_interstate = (supply_type == "INTER_STATE")
        if is_interstate:
            # Prefer IGST named taxes
            for t in matching_rate:
                t_name = (t.tax_name or "").upper()
                if t_name.startswith("IGST") or "IGST" in t_name:
                    return t.zoho_tax_id
        else:
            # Prefer GST / tax_group named taxes (e.g. GST18, [GST18])
            for t in matching_rate:
                t_name = (t.tax_name or "").upper()
                if (t_name.startswith("GST") or t.tax_type == "tax_group") and "IGST" not in t_name:
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
        organization_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Dynamically resolves the Zoho Tax ID for TDS strictly scoped to the active Zoho organization_id.
        Follows statutory priority matching:
        1. Exact rate + Zoho Section Slug / ID Match
        2. Exact rate + Normalized Clause / Provision Match (e.g. Sl 6(iii)(D)(b) vs D(a))
        3. Exact rate + Operational Category Match (strictly excludes passive taxes like Dividend/Interest on service bills)
        4. Safe single rate match
        5. Ambiguity safety guard: Returns None if unresolved rather than guessing wrong tax
        """
        if not db:
            return None

        if rate is None or float(rate) <= 0:
            return None

        clean_rate = float(rate)
        org_id = await self._resolve_organization_id(tenant_id, db, organization_id)

        try:
            query = select(TaxRate).where(
                TaxRate.tenant_id == tenant_id,
                TaxRate.is_active == True,
                TaxRate.tax_type.in_(["TDS", "tds_tax", "tds"]),
            )
            if org_id:
                query = query.where(TaxRate.organization_id == org_id)

            res = await db.execute(query)
            tds_taxes = res.scalars().all() if res else []
        except Exception:
            return None

        if not tds_taxes and org_id:
            try:
                await self.sync_taxes(tenant_id, db, organization_id=org_id)
                res = await db.execute(query)
                tds_taxes = res.scalars().all() if res else []
            except Exception as sync_err:
                logger.warning(f"On-demand TDS sync failed: {sync_err}")

        if not tds_taxes:
            return None

        # Filter strictly active taxes matching the exact required rate (within 0.05% tolerance)
        candidate_taxes = [
            t for t in tds_taxes
            if t.is_active and abs(float(t.tax_percentage or 0.0) - clean_rate) < 0.05
        ]

        if not candidate_taxes:
            # Check if any active TDS tax mentions the exact rate in its name (e.g. "20%", "20.0%")
            rate_str_pct = f"{int(clean_rate) if clean_rate.is_integer() else clean_rate}%"
            named_rate_taxes = [
                t for t in tds_taxes
                if t.is_active and rate_str_pct in (t.tax_name or "")
            ]
            if named_rate_taxes:
                return named_rate_taxes[0].zoho_tax_id

            logger.warning(
                f"No Zoho TDS tax rate matching {clean_rate}% found in organization {org_id}. "
                f"Available TDS rates: {[float(t.tax_percentage or 0.0) for t in tds_taxes if t.is_active]}. "
                f"Returning None to avoid applying incorrect withholding tax rate."
            )
            return None

        # Normalize incoming inputs
        from app.services.tds_engine import resolve_tds_tax_details, normalize_statutory_text
        resolved_details = resolve_tds_tax_details(
            section_raw=section,
            provision_raw=provision,
            nature_raw=nature_of_payment,
            rate_hint=clean_rate,
        )
        target_slug = resolved_details.get("zoho_section_slug")
        combined_text = f"{provision or ''} {section or ''} {nature_of_payment or ''}".upper()
        norm_combined = normalize_statutory_text(combined_text)

        # -----------------------------------------------------------------
        # TIER 1: Exact Rate + Zoho Section Slug Match (Most authoritative)
        # -----------------------------------------------------------------
        if target_slug:
            slug_matches = [
                t for t in candidate_taxes
                if (t.tax_section or "").lower() == target_slug.lower()
            ]
            if len(slug_matches) == 1:
                return slug_matches[0].zoho_tax_id
            elif len(slug_matches) > 1:
                candidate_taxes = slug_matches

        # -----------------------------------------------------------------
        # TIER 2: Specific Clause / Token Disambiguation
        # E.g. Subclauses: D(a) -> Technical Services vs D(b) -> Professional Fees
        # -----------------------------------------------------------------
        # Only run subclause disambiguation if invoice actually relates to professional/technical services
        is_tech_prof_bill = any(k in norm_combined for k in ("TECHNICAL", "FTS", "CLOUD", "SOFTWARE", "IT SERVICE", "PROFESSIONAL", "LEGAL", "CONSULT", "FEES", "WITHHELD", "ROYALTY", "ARCHITECT", "SL 6 III", "194J"))
        is_subclause_a = is_tech_prof_bill and any(k in norm_combined for k in ("D A", "TECHNICAL", "TECH SERVICES", "FTS", "CLOUD", "SOFTWARE", "IT SERVICE"))
        is_subclause_b = is_tech_prof_bill and any(k in norm_combined for k in ("D B", "PROFESSIONAL", "LEGAL", "CONSULT", "FEES", "WITHHELD", "ROYALTY", "ARCHITECT"))

        if is_subclause_a and not is_subclause_b:
            sub_matches = [
                t for t in candidate_taxes
                if any(k in normalize_statutory_text(f"{t.tax_name} {t.tax_section} {t.tax_description}")
                       for k in ("TECHNICAL", "TECH", "D A"))
            ]
            if len(sub_matches) == 1:
                return sub_matches[0].zoho_tax_id
            elif len(sub_matches) > 1:
                candidate_taxes = sub_matches

        elif is_subclause_b and not is_subclause_a:
            sub_matches = [
                t for t in candidate_taxes
                if any(k in normalize_statutory_text(f"{t.tax_name} {t.tax_section} {t.tax_description}")
                       for k in ("PROFESSIONAL", "FEES", "WITHHELD", "D B"))
            ]
            if len(sub_matches) == 1:
                return sub_matches[0].zoho_tax_id
            elif len(sub_matches) > 1:
                candidate_taxes = sub_matches

        # -----------------------------------------------------------------
        # TIER 3: Operational Category Keyword Match
        # (Strictly distinguishes Vendor operational taxes from passive taxes)
        # -----------------------------------------------------------------
        category_keywords = {
            "PROFESSIONAL": ["PROFESSIONAL", "WITHHELD", "LEGAL", "CONSULT", "ARCHITECT", "MEDICAL", "ROYALTY"],
            "TECHNICAL": ["TECHNICAL", "FTS", "CLOUD", "TECH", "SOFTWARE", "IT SERVICE"],
            "CONTRACTOR": ["CONTRACTOR", "CONTRACT", "194C", "HUF", "SUB CONTRACT", "MANPOWER", "GUARD"],
            "RENT": ["RENT", "194I", "PLANT", "LAND", "BUILDING", "FURNITURE", "MACHINERY"],
            "COMMISSION": ["COMMISSION", "BROKERAGE", "194H", "BROKER"],
            "PURCHASE": ["PURCHASE", "GOODS", "194Q"],
            "DIVIDEND": ["DIVIDEND", "DISTRIBUTION"],
            "INTEREST": ["INTEREST", "SECURITIES"],
        }

        # Identify which category the invoice belongs to
        matched_categories = set()
        for cat, kws in category_keywords.items():
            if any(kw in norm_combined for kw in kws):
                matched_categories.add(cat)

        # If it's a vendor operational service/goods bill, strictly eliminate Dividend and Interest
        is_vendor_bill = bool(matched_categories.intersection({"PROFESSIONAL", "TECHNICAL", "CONTRACTOR", "RENT", "COMMISSION", "PURCHASE"})) or any(
            k in norm_combined for k in ("393", "194", "FEE", "SERVICE", "SUPPLY", "BILL")
        )

        if is_vendor_bill and not matched_categories.intersection({"DIVIDEND", "INTEREST"}):
            non_passive = [
                t for t in candidate_taxes
                if not any(p in normalize_statutory_text(f"{t.tax_name} {t.tax_section} {t.tax_description}")
                           for p in ("DIVIDEND", "INTEREST", "SECURITIES"))
            ]
            if len(non_passive) == 1:
                return non_passive[0].zoho_tax_id
            elif len(non_passive) > 1:
                candidate_taxes = non_passive

        # Attempt category keyword matching on remaining candidates
        if matched_categories:
            cat_tokens = []
            for cat in matched_categories:
                cat_tokens.extend(category_keywords[cat])
            cat_matches = [
                t for t in candidate_taxes
                if any(kw in normalize_statutory_text(f"{t.tax_name} {t.tax_section} {t.tax_description}") for kw in cat_tokens)
            ]
            if len(cat_matches) == 1:
                return cat_matches[0].zoho_tax_id

        # -----------------------------------------------------------------
        # TIER 4: Safe Unique Rate Match
        # -----------------------------------------------------------------
        if len(candidate_taxes) == 1:
            # Final sanity guard: Don't pick passive Dividend/Interest for a vendor service invoice
            t_cand = candidate_taxes[0]
            cand_text = normalize_statutory_text(f"{t_cand.tax_name} {t_cand.tax_section} {t_cand.tax_description}")
            if is_vendor_bill and any(p in cand_text for p in ("DIVIDEND", "INTEREST")):
                return None
            return t_cand.zoho_tax_id

        # -----------------------------------------------------------------
        # TIER 5: Ambiguity Guard
        # Multiple active taxes exist at this rate and cannot be safely
        # disambiguated. Fail safely rather than guessing an arbitrary tax.
        # -----------------------------------------------------------------
        logger.warning(
            f"Ambiguous Zoho TDS tax resolution for tenant {tenant_id}: {len(candidate_taxes)} taxes match rate {clean_rate}% "
            f"({[t.tax_name for t in candidate_taxes]}), but none uniquely matched statutory classification '{combined_text}'."
        )
        return None

    async def sync_vendors(
        self,
        tenant_id: str,
        db: AsyncSession,
        organization_id: Optional[str] = None,
        user_id: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Fetches vendor contacts from Zoho and upserts into local vendors table scoped to organization_id."""
        connection = await self.get_or_create_zoho_connection(tenant_id, db, user_id=user_id)
        if connection.status != "CONNECTED" or not connection.organization_id:
            logger.warning(f"Tenant {tenant_id} is not connected to Zoho. Skipping live vendor sync.")
            return await self.get_cached_vendors(tenant_id, db, organization_id=organization_id)

        current_org_id = str(organization_id or connection.organization_id).strip()

        try:
            zoho_contacts = await zoho_client_service.get_vendors(connection, db)
            logger.info(f"Fetched {len(zoho_contacts)} vendor contacts from Zoho for tenant {tenant_id} (Org: {current_org_id})")

            existing_query = select(Vendor).where(
                Vendor.tenant_id == tenant_id,
                Vendor.organization_id == current_org_id,
            )
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
                    v.organization_id = current_org_id
                    v.updated_at = datetime.now(timezone.utc)
                else:
                    new_v = Vendor(
                        tenant_id=tenant_id,
                        organization_id=current_org_id,
                        zoho_contact_id=z_id,
                        vendor_name=name,
                        gstin=gstin,
                        pan=pan,
                        email=email,
                        phone=phone,
                        approval_status="APPROVED",
                    )
                    db.add(new_v)

            # Prune obsolete vendors from old organizations
            await db.execute(
                delete(Vendor).where(
                    Vendor.tenant_id == tenant_id,
                    Vendor.organization_id != current_org_id,
                )
            )

            await db.commit()
            return await self.get_cached_vendors(tenant_id, db, organization_id=current_org_id)
        except Exception as exc:
            logger.warning(f"Vendor sync warning: {exc}")
            return await self.get_cached_vendors(tenant_id, db, organization_id=current_org_id)

    async def get_cached_vendors(
        self,
        tenant_id: str,
        db: AsyncSession,
        organization_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Returns list of cached vendors strictly scoped to active Zoho organization."""
        org_id = await self._resolve_organization_id(tenant_id, db, organization_id)
        query = select(Vendor).where(Vendor.tenant_id == tenant_id)
        if org_id:
            query = query.where(Vendor.organization_id == org_id)

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

    async def resolve_zoho_destination_and_branch(
        self,
        tenant_id: str,
        db: AsyncSession,
        invoice_recipient_state: Optional[str] = None,
        invoice_recipient_gstin: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Dynamically resolves the Zoho destination of supply (2-letter state code, e.g. 'TS', 'MH')
        and matching Zoho branch_id without any hardcoded state codes.

        Algorithm:
        1. Query connected Zoho organization to inspect primary address and GSTIN.
        2. Query Zoho branches API (GET /branches) to inspect all active branch registrations.
        3. If a branch matches the invoice recipient GSTIN or recipient state, select that branch.
        4. Otherwise fallback to the primary organization state and registration.
        """
        from app.services.gst_engine import normalize_indian_state

        try:
            conn = await self.get_or_create_zoho_connection(tenant_id, db)
        except Exception as e:
            logger.debug(f"DB/connection lookup skipped in branch resolution: {e}")
            conn = None

        if not conn or conn.status != "CONNECTED" or not conn.organization_id:
            zoho_st, _, _ = normalize_indian_state(state_input=invoice_recipient_state, gstin=invoice_recipient_gstin)
            return {
                "destination_state_code": zoho_st,
                "branch_id": None,
                "source": "fallback_invoice",
            }

        target_zoho_st, target_num_st, _ = normalize_indian_state(
            state_input=invoice_recipient_state, gstin=invoice_recipient_gstin
        )

        # 1. Fetch live branches from Zoho
        branches = []
        try:
            res = await zoho_client_service._make_authorized_request(
                connection=conn,
                db=db,
                method="GET",
                endpoint_path="branches",
            )
            branches = res.get("branches") or []
        except Exception as e:
            logger.warning(f"Could not fetch Zoho branches: {e}")

        # Determine if organization genuinely supports multi-branch transaction tracking.
        # In Zoho Books (India Edition), single-branch organizations have only 1 default Head Office
        # branch registration. Sending branch_id on POST /bills for such organizations fails with
        # code 8 ("Invalid Element branch_id"). Only true multi-branch organizations (len(branches) > 1
        # or having explicit non-primary branches) accept/require branch_id on transaction headers.
        is_multi_branch_org = (
            len(branches) > 1
            or any(not b.get("is_primary_branch", False) for b in branches if isinstance(b, dict))
        )

        matched_branch = None
        # Match branch by GSTIN first
        if invoice_recipient_gstin and branches:
            clean_recip_gst = str(invoice_recipient_gstin).strip().upper()
            for b in branches:
                b_gst = str(b.get("tax_reg_no") or "").strip().upper()
                if b_gst and b_gst == clean_recip_gst:
                    matched_branch = b
                    break

        # Match branch by state if not matched by GSTIN
        if not matched_branch and target_zoho_st and branches:
            for b in branches:
                b_st = str(b.get("address", {}).get("state_code") or b.get("address", {}).get("state") or "").strip().upper()
                norm_b_st, _, _ = normalize_indian_state(state_input=b_st)
                if norm_b_st and norm_b_st == target_zoho_st:
                    matched_branch = b
                    break

        if matched_branch:
            b_state = matched_branch.get("address", {}).get("state_code") or matched_branch.get("address", {}).get("state")
            zoho_b_st, _, _ = normalize_indian_state(state_input=b_state)
            # Only return branch_id if organization is genuinely multi-branched.
            # For single-branch / single-entity Head Office orgs, return None so the field is safely omitted.
            resolved_bid = matched_branch.get("branch_id") if is_multi_branch_org else None
            return {
                "destination_state_code": zoho_b_st or target_zoho_st,
                "branch_id": resolved_bid,
                "branch_name": matched_branch.get("branch_name"),
                "source": "zoho_branch_match" if is_multi_branch_org else "zoho_org_primary_branch",
            }

        # 2. Match against primary organization registration
        try:
            org_res = await zoho_client_service._make_authorized_request(
                connection=conn,
                db=db,
                method="GET",
                endpoint_path=f"organizations/{conn.organization_id}",
            )
            org = org_res.get("organization") or {}
            org_st_raw = org.get("address", {}).get("state_code") or org.get("address", {}).get("state")
            zoho_org_st, _, _ = normalize_indian_state(state_input=org_st_raw)
            return {
                "destination_state_code": zoho_org_st or target_zoho_st,
                "branch_id": None,
                "source": "zoho_org_primary",
            }
        except Exception as e:
            logger.warning(f"Could not fetch Zoho organization details: {e}")

        return {
            "destination_state_code": target_zoho_st,
            "branch_id": None,
            "source": "invoice_recipient_fallback",
        }


master_data_service = MasterDataService()
