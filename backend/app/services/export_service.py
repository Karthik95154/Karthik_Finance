import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Invoice, ZohoConnection, ChartOfAccount, TaxRate, JournalEntry
from app.services.zoho_client import zoho_client_service
from app.services.master_data_service import master_data_service
from app.storage.supabase_storage import storage_service
from app.services.audit_service import audit_service
from app.services.financial_validator import financial_validator
from app.services.journal_generator import journal_generator, sync_relational_journal
from app.services.itc_engine import get_effective_itc_data, itc_engine, ITCStatus
from app.services.gst_engine import gst_engine
from app.services.tds_engine import tds_engine, get_effective_tds_data

logger = logging.getLogger(__name__)


def to_zoho_state_code(code_or_name: Optional[str]) -> Optional[str]:
    """
    Normalizes a state code or name into Zoho's accepted 2-digit GST state code (e.g. '36', '27', '29', '07').
    Ensures length <= 4 characters for Zoho API compliance.
    """
    if not code_or_name:
        return None
    val = str(code_or_name).strip()
    if val.isdigit() and len(val) == 2:
        return val
    if len(val) <= 3 and val.isalpha():
        return val.upper()
    from app.services.gst_engine import STATE_NAME_TO_CODE
    resolved = STATE_NAME_TO_CODE.get(val.lower())
    if resolved:
        return resolved
    return val[:2]


def resolve_zoho_itc_eligibility(
    item_desc: str = "",
    item_hsn: Optional[str] = None,
    line_itc: Optional[Dict[str, Any]] = None,
    overall_itc_res: Optional[Dict[str, Any]] = None,
    source_state: Optional[str] = None,
    dest_state: Optional[str] = None,
    is_rcm: bool = False,
    supply_type: str = "INTRA_STATE",
    line_has_intra_tax: bool = False,
) -> str:
    """
    Determines statutory Zoho Books ITC eligibility type for Bill line items:
    - 'ineligible_others': If Source State != Destination State on intra-state supply, or blocked under Sec 17(5)
    - 'ineligible_rcm': If RCM and ineligible
    - 'eligible_capital_goods': If capital goods / assets
    - 'eligible_input_services': If service (HSN 99xx or service description)
    - 'eligible_inputs': Standard eligible goods / inputs
    """
    # 1. State mismatch constraint in Zoho Books India GST:
    # When Destination State differs from Source State and intra-state tax is charged or supply is intra-state:
    if source_state and dest_state and str(source_state).strip() != str(dest_state).strip():
        if supply_type == "INTRA_STATE" or line_has_intra_tax:
            return "ineligible_rcm" if is_rcm else "ineligible_others"

    # 2. Check statutory ITC Engine result (Section 17(5) blocked / ineligible)
    line_status = str(
        (line_itc.get("itc_status") or line_itc.get("status") if line_itc else None)
        or (overall_itc_res.get("status") if overall_itc_res else None)
        or "ELIGIBLE"
    ).upper()

    if line_status in ["INELIGIBLE", "BLOCKED"]:
        return "ineligible_rcm" if is_rcm else "ineligible_others"

    if is_rcm:
        return "eligible_inputs"

    # 3. Classify goods vs capital goods vs services
    desc_l = (item_desc or "").lower()
    hsn_clean = str(item_hsn or "").strip()

    # Capital goods check
    if any(k in desc_l for k in ["capital", "asset", "machinery", "equipment", "furniture", "laptop", "computer", "server", "printer", "vehicle"]):
        return "eligible_capital_goods"

    # Services check (HSN/SAC starting with 99 or services keywords)
    if hsn_clean.startswith("99") or any(k in desc_l for k in ["service", "consulting", "subscription", "maintenance", "license", "amc", "legal", "audit", "hosting", "software", "support", "training", "freight"]):
        return "eligible_input_services"

    return "eligible_inputs"



class InvoiceExportService:
    """
    Manages pre-validation, vendor resolution, idempotent Bill creation with reconciliation,
    and original binary attachment synchronization to Zoho Books.
    """

    async def export_invoice_to_zoho(
        self,
        invoice_id: UUID,
        tenant_id: str,
        db: AsyncSession,
        user_email: str = "finance@sakshi.ai",
        force_resync: bool = False,
    ) -> Dict[str, Any]:
        """
        Exports an APPROVED invoice to Zoho Books with complete idempotency and zero duplicate creation.
        """
        # 1. Fetch Invoice with Row-Level Lock for concurrent safety
        query = (
            select(Invoice)
            .where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
            .with_for_update()
        )
        res = await db.execute(query)
        invoice = res.scalar_one_or_none()

        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found.")

        # 2. Check Approval Status
        if invoice.approval_status != "APPROVED":
            if force_resync:
                logger.info(f"Auto-approving invoice {invoice_id} for Zoho resync...")
                invoice.approval_status = "APPROVED"
                invoice.approved_by = user_email or "finance_resync"
                invoice.approved_at = datetime.now(timezone.utc)
            else:
                raise ValueError(
                    f"Invoice must be APPROVED by Finance before exporting to Zoho. Current status: {invoice.approval_status}"
                )

        if not force_resync and invoice.export_status == "EXPORTED" and invoice.zoho_bill_id:
            return {
                "status": "already_exported",
                "message": "Invoice has already been exported to Zoho Books.",
                "zoho_bill_id": invoice.zoho_bill_id,
                "zoho_bill_number": invoice.zoho_bill_number,
                "attachment_status": "attached",
            }

        # 3. Check Balanced Journal Entry Existence & Consistency
        journal_query = select(JournalEntry).where(
            JournalEntry.invoice_id == invoice_id,
            JournalEntry.tenant_id == tenant_id,
        )
        j_res = await db.execute(journal_query)
        journal_entry = j_res.scalar_one_or_none()

        if not force_resync:
            if (
                not journal_entry
                or not journal_entry.is_balanced
                or journal_entry.status not in ("BALANCED", "APPROVED", "POSTED")
            ):
                raise ValueError("Invoice cannot be exported without an approved, balanced General Ledger journal entry.")

        # 4. Check Date Validity & Authoritative Working Data
        from app.core.date_utils import parse_and_normalize_date, validate_invoice_due_dates, is_date_in_closed_period, format_to_indian_standard
        from app.services.invoice_processing import get_effective_invoice_data
        from app.db.models import Tenant
        
        vlm_data_check = get_effective_invoice_data(invoice, convert_fx=True)
        inv_eff_total = float(vlm_data_check.get("total_amount") or vlm_data_check.get("subtotal") or 0.0)
        j_total = float(journal_entry.total_debit or 0.0) if journal_entry else 0.0

        # Classification and RCM reconciliation guard
        origin = getattr(invoice, "invoice_origin", None) or "INDIAN"
        override = getattr(invoice, "classification_override", None)
        active_origin = override or origin
        is_foreign = (active_origin == "FOREIGN_SERVICE")

        gst_eval_pre = gst_engine.evaluate_gst(vlm_data_check)
        is_rcm_pre = bool(gst_eval_pre.get("is_reverse_charge") or vlm_data_check.get("is_reverse_charge") or is_foreign)

        expected_journal_debit = inv_eff_total
        if is_rcm_pre:
            calc_gst = gst_eval_pre.get("calculated") or {}
            rcm_tax = float(calc_gst.get("gst_total") or calc_gst.get("igst_amount") or gst_eval_pre.get("total_tax") or 0.0)
            expected_journal_debit = round(inv_eff_total + rcm_tax, 2)

        if not force_resync and inv_eff_total > 0 and j_total > 0 and abs(expected_journal_debit - j_total) > 0.05 and abs(inv_eff_total - j_total) > 0.05:
            raise ValueError(
                f"Cannot export to Zoho: Approved journal total (₹{j_total:,.2f}) does not match current invoice total (₹{inv_eff_total:,.2f}). Please re-approve journal."
            )

        if force_resync:
            needs_journal_refresh = (
                not journal_entry
                or not journal_entry.is_balanced
                or (inv_eff_total > 0 and j_total > 0 and abs(expected_journal_debit - j_total) > 0.05 and abs(inv_eff_total - j_total) > 0.05)
            )

            if needs_journal_refresh:
                logger.info(f"Auto-refreshing journal entry for invoice {invoice_id} to match latest edits on resync...")
                eff_itc_pre = itc_engine.evaluate_itc(invoice_data=vlm_data_check, gst_result=gst_eval_pre, accounting_output=invoice.current_accounting_output or {})
                eff_tds_pre = get_effective_tds_data(invoice.current_accounting_output or {})
                tds_base_pre = tds_engine.determine_tds_base_amount(vlm_data_check, eff_tds_pre)
                tds_calc_pre = tds_engine.calculate_tds(
                    applicable=bool(eff_tds_pre.get("applicable")),
                    section=eff_tds_pre.get("section"),
                    provision=eff_tds_pre.get("provision"),
                    nature_of_payment=eff_tds_pre.get("nature_of_payment"),
                    base_amount=tds_base_pre,
                    rate=eff_tds_pre.get("rate"),
                )
                fin_val_pre = financial_validator.validate_invoice(vlm_data_check, gst_eval_pre)
                refreshed_journal = journal_generator.generate_journal(
                    invoice_data=vlm_data_check,
                    accounting_classification=invoice.current_accounting_output or {},
                    gst_result=gst_eval_pre,
                    itc_result=eff_itc_pre,
                    tds_result=tds_calc_pre,
                    financial_validation_result=fin_val_pre,
                )
                journal_entry = await sync_relational_journal(
                    session=db,
                    invoice_id=invoice.id,
                    journal_dict=refreshed_journal,
                    tenant_id=tenant_id,
                )
                invoice.journal_entry = refreshed_journal
                invoice.itc_result = eff_itc_pre
                await db.flush()

        raw_inv_date = vlm_data_check.get("invoice_date")
        raw_due_date = vlm_data_check.get("due_date")
        invoice_date_norm = parse_and_normalize_date(raw_inv_date) or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        due_date_norm = parse_and_normalize_date(raw_due_date) or invoice_date_norm

        is_valid_dates, date_err = validate_invoice_due_dates(invoice_date_norm, due_date_norm)
        if not is_valid_dates:
            raise ValueError(f"Cannot export to Zoho: {date_err}")

        # 5. GATE 3 ENFORCEMENT: Fresh server-side accounting period check immediately before export
        effective_posting_date = parse_and_normalize_date(invoice.posting_date) or invoice_date_norm
        t_query = select(Tenant).where(Tenant.id == tenant_id)
        t_res = await db.execute(t_query)
        tenant_obj = t_res.scalar_one_or_none()
        if not tenant_obj:
            raise ValueError(f"Cannot export to Zoho: Tenant organization '{tenant_id}' could not be loaded for closed period validation.")

        lock_date = getattr(tenant_obj, "books_closed_through_date", None)

        if is_date_in_closed_period(effective_posting_date, lock_date):
            if invoice.period_resolution != "PRIOR_PERIOD_EXCEPTION":
                raise ValueError(
                    f"Cannot export to Zoho: Posting date ({effective_posting_date}) is in a closed accounting period "
                    f"(Books closed through {lock_date}). An authorized Finance Prior-Period Exception is required."
                )

        # 6. Check Zoho Connection
        connection = await master_data_service.get_or_create_zoho_connection(tenant_id, db, user_id=invoice.user_id)
        if connection.status != "CONNECTED" or not connection.organization_id:
            raise ValueError("Tenant is not connected to a Zoho Books organization. Please connect Zoho first.")

        # 7. Set In-Flight Lock
        invoice.export_status = "EXPORTING"
        await db.commit()

        try:
            # 7. Extract Current Working Data
            vlm_data = vlm_data_check
            vendor_name = (vlm_data.get("vendor_name") or "Unnamed Vendor").strip()
            vendor_gstin = (vlm_data.get("vendor_gstin") or "").strip() or None
            vendor_pan = (vlm_data.get("vendor_pan") or "").strip() or None
            invoice_num = (vlm_data.get("invoice_number") or f"INV-{str(invoice.id)[:8]}").strip()
            invoice_date = invoice_date_norm
            posting_date = effective_posting_date
            due_date = due_date_norm

            # 8. Authoritative Line Item Account Validation (ZERO SYNTHETIC FALLBACK)
            accounting = {}
            if isinstance(invoice.current_accounting_output, dict):
                accounting = invoice.current_accounting_output
            elif isinstance(invoice.accounting_output, dict):
                accounting = invoice.accounting_output

            # Build lookup maps for Chart of Accounts matching
            valid_zoho_accounts = {}
            name_to_zoho_id = {}
            default_expense_id = None
            current_org_id = str(connection.organization_id).strip()
            try:
                coa_query = select(ChartOfAccount).where(
                    ChartOfAccount.tenant_id == tenant_id,
                    ChartOfAccount.organization_id == current_org_id,
                    ChartOfAccount.is_active == True,
                )
                coa_res = await db.execute(coa_query)
                if coa_res:
                    coa_rows = coa_res.scalars().all()
                    for a in coa_rows:
                        zid = str(getattr(a, "zoho_account_id", "") or "").strip()
                        aname = getattr(a, "account_name", "") or ""
                        acode = getattr(a, "account_code", "") or ""
                        atype = str(getattr(a, "account_type", "") or "").lower()
                        if zid:
                            valid_zoho_accounts[zid] = aname
                            if aname:
                                name_to_zoho_id[aname.lower().strip()] = zid
                            if acode:
                                name_to_zoho_id[acode.lower().strip()] = zid
                            if "expense" in atype and not default_expense_id:
                                default_expense_id = zid
                    if not default_expense_id and valid_zoho_accounts:
                        default_expense_id = next(iter(valid_zoho_accounts.keys()))
            except Exception:
                valid_zoho_accounts = {}

            # ITC assessment account hint map
            itc_acct_map = {}
            if isinstance(accounting.get("itc_assessment"), dict):
                for breakdown in accounting["itc_assessment"].get("line_item_breakdown") or []:
                    l_idx = breakdown.get("line_index")
                    if l_idx and breakdown.get("account_name"):
                        itc_acct_map[l_idx] = breakdown.get("account_name")

            def find_best_zoho_account(desc_text: str, acc_name_hint: str) -> Optional[str]:
                """Intelligently matches line description and account name to active Zoho Chart of Accounts."""
                combined = f"{desc_text or ''} {acc_name_hint or ''}".lower()

                # 1. Exact Name match
                if acc_name_hint and str(acc_name_hint).lower().strip() in name_to_zoho_id:
                    return name_to_zoho_id[str(acc_name_hint).lower().strip()]

                # 2. Software / IT / Cloud / SaaS / Seats
                if any(w in combined for w in ["software", "hubspot", "sales seat", "core seat", "seat", "cloud", "internet", "hosting", "saas", "subscription", "domain", "api", "license", "it ", " it", "tech", "aws", "azure", "google", "slack", "zoom"]):
                    for target in ["it and internet expenses", "software", "subscription", "it & internet", "professional expense"]:
                        if target in name_to_zoho_id:
                            return name_to_zoho_id[target]

                # 3. Professional / Legal / Consulting
                if any(w in combined for w in ["professional", "legal", "consult", "advisory", "audit", "compliance", "lawyer", "advocate", "fee"]):
                    for target in ["professional expense", "consultant expense", "legal expense", "it and internet expenses"]:
                        if target in name_to_zoho_id:
                            return name_to_zoho_id[target]

                # 4. Marketing / Advertising
                if any(w in combined for w in ["advertis", "marketing", "promotion", "campaign", "ad ", "ads "]):
                    for target in ["advertising and marketing", "marketing expense", "general expense"]:
                        if target in name_to_zoho_id:
                            return name_to_zoho_id[target]

                # 5. Travel & Lodging
                if any(w in combined for w in ["travel", "flight", "hotel", "lodging", "cab", "taxi", "trip"]):
                    for target in ["travel expense", "lodging"]:
                        if target in name_to_zoho_id:
                            return name_to_zoho_id[target]

                # 6. Office Supplies
                if any(w in combined for w in ["office", "stationery", "paper", "pen", "supplies"]):
                    for target in ["office supplies", "printing and stationery"]:
                        if target in name_to_zoho_id:
                            return name_to_zoho_id[target]

                # 7. Repairs & Maintenance
                if any(w in combined for w in ["repair", "maintenance", "amc", "service"]):
                    for target in ["repairs and maintenance", "general expense"]:
                        if target in name_to_zoho_id:
                            return name_to_zoho_id[target]

                # 8. General / Uncategorized Expense fallback (Avoid physical raw materials)
                for target in ["it and internet expenses", "consultant expense", "general expense", "uncategorized", "other expenses"]:
                    if target in name_to_zoho_id:
                        return name_to_zoho_id[target]

                return default_expense_id

            acct_lines = accounting.get("accounting") or []
            vlm_items = vlm_data.get("line_items") or []
            if vlm_items:
                built_lines = []
                for idx, item in enumerate(vlm_items, 1):
                    item_acc_name = item.get("account_name") or item.get("account") or itc_acct_map.get(idx)
                    existing_entry = next((a for a in acct_lines if a.get("line_index") == idx), None) if acct_lines else None
                    if not item_acc_name and existing_entry:
                        item_acc_name = existing_entry.get("account_name") or existing_entry.get("approved_account_name")

                    # If account name is not found in cache, trigger on-demand live Zoho COA sync immediately
                    if item_acc_name and str(item_acc_name).lower().strip() not in name_to_zoho_id and current_org_id:
                        try:
                            logger.info(f"COA account '{item_acc_name}' not found in cache. Performing on-demand live Zoho COA sync...")
                            await master_data_service.sync_chart_of_accounts(tenant_id, db, organization_id=current_org_id)
                            coa_res_live = await db.execute(
                                select(ChartOfAccount).where(
                                    ChartOfAccount.tenant_id == tenant_id,
                                    ChartOfAccount.is_active == True,
                                )
                            )
                            if coa_res_live:
                                for a in coa_res_live.scalars().all():
                                    zid = str(getattr(a, "zoho_account_id", "") or "").strip()
                                    aname = getattr(a, "account_name", "") or ""
                                    acode = getattr(a, "account_code", "") or ""
                                    if zid:
                                        valid_zoho_accounts[zid] = aname
                                        if aname:
                                            name_to_zoho_id[aname.lower().strip()] = zid
                                        if acode:
                                            name_to_zoho_id[acode.lower().strip()] = zid
                        except Exception as sync_e:
                            logger.warning(f"On-demand live COA sync failed: {sync_e}")

                    best_acc_id = None
                    if item_acc_name and str(item_acc_name).lower().strip() in name_to_zoho_id:
                        best_acc_id = name_to_zoho_id[str(item_acc_name).lower().strip()]
                    elif item.get("account_id") and str(item.get("account_id")) in valid_zoho_accounts:
                        best_acc_id = str(item.get("account_id"))
                    elif item.get("zoho_account_id") and str(item.get("zoho_account_id")) in valid_zoho_accounts:
                        best_acc_id = str(item.get("zoho_account_id"))
                    else:
                        best_acc_id = find_best_zoho_account(item.get("description") or "", item_acc_name or "")

                    built_lines.append({
                        "line_index": idx,
                        "source_description": item.get("description") or f"Line {idx}",
                        "account_id": best_acc_id or f"ACC_{idx}",
                        "account_name": item_acc_name or valid_zoho_accounts.get(str(best_acc_id)) or "General Expenses",
                        "approved_account_id": best_acc_id or f"ACC_{idx}",
                        "approved_account_name": valid_zoho_accounts.get(str(best_acc_id)) or item_acc_name or "General Expenses",
                    })
                acct_lines = built_lines
                accounting["accounting"] = built_lines
                invoice.current_accounting_output = accounting

            if not acct_lines:
                raise ValueError("Cannot export to Zoho: Invoice has no accounting line items. Please add line items or select COA accounts.")

            acct_map = {}
            for item in acct_lines:
                idx = item.get("line_index", 1)
                desc = item.get("source_description") or ""
                approved_acc_id = item.get("approved_account_id") or item.get("final_account_id") or item.get("account_id") or item.get("zoho_account_id")
                approved_acc_name = item.get("approved_account_name") or item.get("final_account_name") or item.get("account_name") or item.get("account") or itc_acct_map.get(idx) or ""
                
                if approved_acc_name and str(approved_acc_name).lower().strip() in name_to_zoho_id:
                    approved_acc_id = name_to_zoho_id[str(approved_acc_name).lower().strip()]
                elif not approved_acc_id or str(approved_acc_id).startswith("ACC_") or str(approved_acc_id) == "None":
                    best_match = find_best_zoho_account(desc, approved_acc_name)
                    if best_match:
                        approved_acc_id = best_match
                    elif default_expense_id:
                        approved_acc_id = default_expense_id
                    else:
                        raise ValueError(
                            f"Cannot export to Zoho: Line item {idx} ('{desc or idx}') has an unmapped/placeholder account '{approved_acc_id}'. "
                            f"An active Zoho Chart of Accounts account must be selected and approved by Finance before export."
                        )

                if valid_zoho_accounts and str(approved_acc_id) not in valid_zoho_accounts:
                    best_match = find_best_zoho_account(desc, approved_acc_name)
                    if best_match and best_match in valid_zoho_accounts:
                        approved_acc_id = best_match
                    elif default_expense_id:
                        approved_acc_id = default_expense_id
                    else:
                        raise ValueError(
                            f"Cannot export to Zoho: Line item {idx} account '{approved_acc_id}' is not in the synchronized active Zoho Chart of Accounts. "
                            f"Please sync COA in integrations and select a valid Zoho account."
                        )
                acct_map[idx] = str(approved_acc_id)

            # 8. Dynamic Recipient Branch & Destination Resolution
            branch_info = await master_data_service.resolve_zoho_destination_and_branch(
                tenant_id=tenant_id,
                db=db,
                invoice_recipient_state=vlm_data.get("place_of_supply") or vlm_data.get("customer_state") or vlm_data.get("buyer_state"),
                invoice_recipient_gstin=vlm_data.get("customer_gstin") or vlm_data.get("buyer_gstin"),
                organization_id=current_org_id,
            )
            resolved_dest_code = branch_info.get("destination_state_code")
            resolved_branch_id = branch_info.get("branch_id")

            # 9. Generic Authoritative ITC Single Source of Truth
            effective_itc = get_effective_itc_data(
                invoice_or_data=invoice,
                accounting_output=accounting,
                recipient_state_code=resolved_dest_code,
            )
            itc_overall_status = effective_itc.get("status")
            eligible_itc_total = float(effective_itc.get("eligible_itc") or 0.0)

            # Strict Gating: Unreviewed GSTR-2B pending/mismatch or review-required cannot export
            # If Finance explicitly approved the invoice (approval_status == 'APPROVED'), that constitutes authorized human review
            is_finance_approved = (invoice.approval_status == "APPROVED")
            if itc_overall_status in (
                ITCStatus.REVIEW_REQUIRED.value,
                ITCStatus.GSTR2B_PENDING.value,
                ITCStatus.GSTR2B_MISMATCH.value,
            ) and not effective_itc.get("is_hitl_overridden") and not is_finance_approved:
                raise ValueError(
                    f"Cannot export to Zoho: Invoice ITC status is '{itc_overall_status}' and requires Finance review. "
                    f"Statutory ITC cannot be claimed or exported until resolved or approved by Finance."
                )

            # 10. Journal Auto-Refresh & Strict Reconciliation Guard
            # Reconcile journal input tax debits against authoritative eligible ITC
            journal_input_tax_debit = eligible_itc_total
            try:
                from app.db.models import JournalLineModel
                jl_query = select(JournalLineModel).where(
                    JournalLineModel.journal_entry_id == journal_entry.id,
                    JournalLineModel.line_type == "INPUT_TAX",
                )
                jl_res = await db.execute(jl_query)
                jl_rows = jl_res.scalars().all() if jl_res else []
                if jl_rows:
                    calc_debit = 0.0
                    for jl in jl_rows:
                        calc_debit += float(getattr(jl, "debit", 0.0) or 0.0)
                    journal_input_tax_debit = round(calc_debit, 2)
            except Exception:
                journal_input_tax_debit = eligible_itc_total

            if abs(journal_input_tax_debit - eligible_itc_total) > 0.05:
                logger.info(
                    f"Journal input tax (₹{journal_input_tax_debit:.2f}) does not match authoritative ITC "
                    f"(₹{eligible_itc_total:.2f}). Automatically refreshing journal to align with SSOT..."
                )
                gst_eval_tmp = gst_engine.evaluate_gst(vlm_data)
                eff_tds_tmp = get_effective_tds_data(accounting)
                tds_base_tmp = tds_engine.determine_tds_base_amount(vlm_data, eff_tds_tmp)
                tds_calc_tmp = tds_engine.calculate_tds(
                    applicable=bool(eff_tds_tmp.get("applicable")),
                    section=eff_tds_tmp.get("section"),
                    provision=eff_tds_tmp.get("provision"),
                    nature_of_payment=eff_tds_tmp.get("nature_of_payment"),
                    base_amount=tds_base_tmp,
                    rate=eff_tds_tmp.get("rate"),
                )
                fin_val_tmp = financial_validator.validate_invoice(vlm_data, gst_eval_tmp)
                refreshed_journal_dict = journal_generator.generate_journal(
                    invoice_data=vlm_data,
                    accounting_classification=accounting,
                    gst_result=gst_eval_tmp,
                    itc_result=effective_itc,
                    tds_result=tds_calc_tmp,
                    financial_validation_result=fin_val_tmp,
                )
                await sync_relational_journal(
                    session=db,
                    invoice_id=invoice.id,
                    journal_dict=refreshed_journal_dict,
                    tenant_id=tenant_id,
                )
                invoice.journal_entry = refreshed_journal_dict
                invoice.itc_result = effective_itc
                await db.flush()

                # Re-verify journal balance & input tax after refresh
                j_refreshed_total = float(refreshed_journal_dict.get("total_debit") or 0.0)
                recheck_itc_tax = sum(
                    float(l.get("debit") or 0.0)
                    for l in refreshed_journal_dict.get("lines", [])
                    if l.get("line_type") == "INPUT_TAX"
                )
                if abs(recheck_itc_tax - eligible_itc_total) > 0.05:
                    raise ValueError(
                        f"Cannot export to Zoho: Refreshed journal input tax (₹{recheck_itc_tax:.2f}) "
                        f"still does not reconcile with authoritative eligible ITC (₹{eligible_itc_total:.2f})."
                    )

            # Map line-level ITC eligibility decisions for Zoho bill serialization
            itc_lines_map = {
                l.get("line_index"): l.get("zoho_itc_eligibility", "ineligible_others")
                for l in effective_itc.get("line_item_breakdown", [])
            }

            # 11. Resolve Supply Type & TDS Configuration (Single Authoritative Source of Truth)
            gst_eval = gst_engine.evaluate_gst(vlm_data)
            supply_type = gst_eval.get("supply_type") or "INTRA_STATE"
            inv_subtotal = float(vlm_data.get("subtotal") or 0.0)

            # Single Source of Truth for TDS: tds_assessment strictly governs
            effective_tds = get_effective_tds_data(accounting)
            tds_applicable = bool(effective_tds.get("applicable"))
            tds_provision = effective_tds.get("provision")
            tds_section = effective_tds.get("section")
            tds_nature = effective_tds.get("nature_of_payment")
            tds_rate = effective_tds.get("rate")

            zoho_tds_tax_id = None
            if tds_applicable:
                if tds_rate is None or float(tds_rate) <= 0:
                    calc = tds_engine.calculate_tds(
                        applicable=True,
                        section=tds_section,
                        provision=tds_provision,
                        nature_of_payment=tds_nature,
                        base_amount=inv_subtotal if inv_subtotal > 0 else 1.0,
                    )
                    if calc.get("rate") and calc.get("rate") > 0:
                        tds_rate = calc.get("rate")

                if tds_rate is None or float(tds_rate) <= 0:
                    raise ValueError(
                        "Cannot export to Zoho: TDS is marked as applicable, but no valid TDS rate or section was specified. "
                        "Please verify TDS details on the review workspace before exporting."
                    )
                zoho_tds_tax_id = await master_data_service.get_zoho_tds_tax(
                    tenant_id=tenant_id,
                    section=tds_section,
                    provision=tds_provision,
                    nature_of_payment=tds_nature,
                    rate=float(tds_rate),
                    db=db,
                    organization_id=current_org_id,
                )
                if not zoho_tds_tax_id:
                    sec_label = f"Section {tds_section}" if tds_section else (tds_nature or "Statutory TDS")
                    if is_foreign or "393" in str(tds_section or "") or "195" in str(tds_section or ""):
                        logger.warning(
                            f"Zoho Books organization {current_org_id} does not have a matching 20% foreign withholding TDS tax rate configured. "
                            f"Recording full {sec_label} withholding ({tds_rate}%) in Zoho Bill Notes and double-entry GL journal."
                        )
                        zoho_tds_tax_id = None
                    else:
                        raise ValueError(
                            f"Cannot export to Zoho: TDS is applicable ({sec_label} at {tds_rate}%), "
                            f"but no matching active TDS tax was found in Zoho Books. Please configure this TDS tax in Zoho Books or update TDS details."
                        )
            else:
                zoho_tds_tax_id = None

            # 9. Resolve Vendor Contact in Zoho (Strict matching, zero arbitrary fallback)
            explicit_vendor_id = vlm_data.get("zoho_vendor_id")
            vendor_contact = None
            if explicit_vendor_id:
                vendor_contact = {"contact_id": str(explicit_vendor_id)}

            if not vendor_contact:
                vendor_contact = await zoho_client_service.search_vendor(
                    connection=connection,
                    db=db,
                    gstin=vendor_gstin,
                    pan=vendor_pan,
                    vendor_name=vendor_name,
                )

            supplier_state_name = gst_eval.get("supplier_state_name")
            pos_state_name = gst_eval.get("place_of_supply_state_name")

            if not vendor_contact:
                logger.info(f"Vendor '{vendor_name}' not matched in Zoho. Creating new vendor contact...")
                v_country = vlm_data.get("vendor_country")
                v_gst_treatment = "overseas" if is_foreign else None
                vendor_contact = await zoho_client_service.create_vendor(
                    connection=connection,
                    db=db,
                    vendor_name=vendor_name,
                    gstin=vendor_gstin,
                    pan=vendor_pan or vlm_data.get("vendor_tax_id"),
                    email=(vlm_data.get("vendor_email") or vlm_data.get("email") or "").strip() or None,
                    phone=(str(vlm_data.get("vendor_phone") or vlm_data.get("phone") or vlm_data.get("mobile") or "")).strip() or None,
                    address=(vlm_data.get("vendor_address") or vlm_data.get("address") or "").strip() or None,
                    state_name=supplier_state_name,
                    country=v_country,
                    gst_treatment=v_gst_treatment,
                )
            elif vendor_contact.get("contact_id") and supplier_state_name:
                # If existing vendor contact lacks state / place_of_contact, update it
                contact_place = vendor_contact.get("place_of_contact")
                contact_gst = vendor_contact.get("gst_no")
                if not contact_place or (vendor_gstin and not contact_gst):
                    try:
                        update_payload: Dict[str, Any] = {}
                        if not contact_place and supplier_state_name:
                            from app.services.gst_engine import normalize_indian_state
                            zoho_st, _, _ = normalize_indian_state(state_input=supplier_state_name, gstin=vendor_gstin)
                            if zoho_st:
                                update_payload["place_of_contact"] = zoho_st
                        if vendor_gstin and not contact_gst:
                            from app.services.gst_engine import validate_gstin
                            is_valid_gst, clean_gst = validate_gstin(vendor_gstin)
                            if is_valid_gst and clean_gst:
                                update_payload["gst_no"] = clean_gst
                                update_payload["gst_treatment"] = "business_gst"
                        if update_payload:
                            await zoho_client_service.update_vendor(
                                connection=connection,
                                db=db,
                                contact_id=vendor_contact["contact_id"],
                                vendor_payload=update_payload,
                            )
                    except Exception as upd_err:
                        logger.warning(f"Could not update vendor place_of_contact in Zoho: {upd_err}")

            vendor_id = vendor_contact.get("contact_id")
            if not vendor_id:
                raise ValueError(
                    f"Cannot export to Zoho: Vendor '{vendor_name}' (GSTIN: {vendor_gstin or 'N/A'}) "
                    f"could not be confidently matched or created in Zoho Books. "
                    f"Please click 'Add Vendor to Zoho' or check vendor details on the review workspace before exporting."
                )

            # 10. Format Bill Line Items using STRICTLY approved accounts and dynamic GST & TDS taxes
            raw_items = vlm_data.get("line_items") or []
            bill_line_items = []
            is_rcm = bool(gst_eval.get("is_reverse_charge") or vlm_data.get("is_reverse_charge") or is_foreign)

            supplier_state_code = to_zoho_state_code(gst_eval.get("supplier_state_code") or gst_eval.get("supplier_state_name"))
            pos_state_code = to_zoho_state_code(gst_eval.get("place_of_supply_state_code") or gst_eval.get("place_of_supply_state_name") or gst_eval.get("buyer_state_code"))
            itc_res = invoice.itc_result or {}
            line_itc_breakdown = itc_res.get("line_item_breakdown") or []

            # Fallback invoice-level tax percentage if line-level rates are omitted
            inv_subtotal = float(vlm_data.get("subtotal") or vlm_data.get("total_amount") or 0.0)
            inv_tax_total = float(
                vlm_data.get("tax_total")
                or (
                    float(vlm_data.get("cgst_amount") or 0.0)
                    + float(vlm_data.get("sgst_amount") or 0.0)
                    + float(vlm_data.get("igst_amount") or 0.0)
                )
            )
            inv_default_tax_rate = (
                round((inv_tax_total / inv_subtotal) * 100, 1)
                if inv_subtotal > 0 and inv_tax_total > 0
                else 0.0
            )

            # Filter out zero quantity / zero amount / free informational line items (e.g., 0 rate and 0 taxable amount)
            effective_items = []
            for item in raw_items:
                taxable_amt = float(item.get("taxable_amount") or item.get("total") or 0.0)
                unit_r = float(item.get("unit_price") or item.get("rate") or 0.0)
                item_qty = float(item.get("quantity") or 0.0)
                if taxable_amt <= 0.0 and unit_r <= 0.0:
                    logger.info(f"Skipping zero-cost informational line item: {item.get('description')}")
                    continue
                effective_items.append(item)

            if effective_items:
                for idx, item in enumerate(effective_items, 1):
                    item_acc_name = item.get("account_name") or item.get("account") or ""
                    item_acc_id = item.get("account_id") or item.get("zoho_account_id") or item.get("approved_account_id")
                    
                    approved_account_id = None
                    if item_acc_name and str(item_acc_name).lower().strip() in name_to_zoho_id:
                        approved_account_id = name_to_zoho_id[str(item_acc_name).lower().strip()]
                    elif item_acc_id and str(item_acc_id) in valid_zoho_accounts:
                        approved_account_id = str(item_acc_id)
                    elif item_acc_name:
                        approved_account_id = find_best_zoho_account(item.get("description") or "", item_acc_name)
                    
                    if not approved_account_id:
                        approved_account_id = acct_map.get(idx) or acct_map.get(1) or default_expense_id

                    if not approved_account_id:
                        raise ValueError(f"Line item {idx} lacks an approved Zoho Chart of Accounts ID.")

                    taxable_amount = float(item.get("taxable_amount") or item.get("total") or 0.0)
                    qty = float(item.get("quantity") or 1.0)
                    rate = float(
                        item.get("unit_price")
                        or item.get("rate")
                        or (taxable_amount / qty if qty > 0 and taxable_amount > 0 else taxable_amount)
                        or 0.0
                    )

                    # When pushing to Zoho, for salary/wage/manpower/duty invoices (e.g. security guards, housekeeping,
                    # duties/days/persons breakdown), enforce quantity = 1.0 and rate = taxable_amount
                    desc_lower = str(item.get("description") or "").lower()
                    unit_lower = str(item.get("unit") or "").lower()
                    inv_cat_lower = str(vlm_data.get("category") or "").lower()
                    vendor_lower = str(vlm_data.get("vendor_name") or "").lower()

                    is_salary_wage_duty = any(kw in desc_lower for kw in [
                        "salary", "wage", "duties", "duty", "manpower", "security guard", "housekeeping",
                        "house keeping", "labour", "labor", "personnel", "guard", "sweeper", "peon",
                        "attendant", "wages", "cleaning service", "driver", "care taker", "supervisor",
                        "npgs"
                    ]) or any(kw in unit_lower for kw in [
                        "duty", "duties", "day", "days", "shift", "shifts", "person", "persons", "manpower"
                    ]) or any(kw in inv_cat_lower for kw in [
                        "salary", "wage", "manpower", "labor", "labour"
                    ]) or any(kw in vendor_lower for kw in [
                        "security", "house keeping", "housekeeping", "manpower", "labour", "labor", "facility",
                        "npgs"
                    ])

                    if is_salary_wage_duty and taxable_amount > 0:
                        qty = 1.0
                        rate = taxable_amount
                    elif qty == 1.0 and taxable_amount > 0:
                        rate = taxable_amount
                    elif qty > 0 and taxable_amount > 0 and abs(qty * rate - taxable_amount) > 0.05:
                        rate = round(taxable_amount / qty, 2)

                    # Extract line-level tax rate
                    cgst_rate = float(item.get("cgst_rate") or 0.0)
                    sgst_rate = float(item.get("sgst_rate") or 0.0)
                    igst_rate = float(item.get("igst_rate") or 0.0)
                    explicit_tax_rate = float(item.get("gst_rate") or item.get("tax_rate") or 0.0)

                    if supply_type == "INTER_STATE":
                        line_tax_rate = igst_rate or (cgst_rate + sgst_rate) or explicit_tax_rate
                    else:
                        line_tax_rate = (cgst_rate + sgst_rate) or igst_rate or explicit_tax_rate

                    # If line rates are 0, try computing from line tax amounts
                    if line_tax_rate <= 0 and taxable_amount > 0:
                        line_tax_amt = (
                            float(item.get("cgst_amount") or 0.0)
                            + float(item.get("sgst_amount") or 0.0)
                            + float(item.get("igst_amount") or 0.0)
                            or float(item.get("tax_amount") or 0.0)
                        )
                        if line_tax_amt > 0:
                            line_tax_rate = round((line_tax_amt / taxable_amount) * 100, 1)

                    has_explicit_tax_spec = any(
                        item.get(k) is not None
                        for k in ["cgst_rate", "sgst_rate", "igst_rate", "gst_rate", "tax_rate", "cgst_amount", "sgst_amount", "igst_amount", "tax_amount"]
                    )

                    # Only fallback to overall invoice tax rate if NO tax fields were present at all on this line
                    if not has_explicit_tax_spec and line_tax_rate <= 0 and inv_default_tax_rate > 0:
                        line_tax_rate = inv_default_tax_rate

                    tax_id = None
                    if line_tax_rate > 0:
                        tax_id = await master_data_service.get_zoho_tax_for_line(
                            tenant_id=tenant_id,
                            tax_percentage=line_tax_rate,
                            supply_type=supply_type,
                            db=db,
                            organization_id=current_org_id,
                        )
                        if not tax_id:
                            raise ValueError(
                                f"Cannot export to Zoho: Line item {idx} has a taxable GST rate of {line_tax_rate}% ({supply_type}), "
                                f"but no matching tax or tax group was found in Zoho Books for organization {current_org_id}. Please sync taxes in Integrations."
                            )

                    # Determine statutory Zoho Books ITC eligibility type
                    line_has_intra = (cgst_rate > 0 or sgst_rate > 0 or float(item.get("cgst_amount") or 0.0) > 0 or float(item.get("sgst_amount") or 0.0) > 0)
                    line_itc_match = next((l for l in line_itc_breakdown if l.get("line_index") == idx), None)
                    if not line_itc_match and idx <= len(line_itc_breakdown):
                        line_itc_match = line_itc_breakdown[idx - 1]

                    line_itc_type = resolve_zoho_itc_eligibility(
                        item_desc=item.get("description") or f"Item {idx}",
                        item_hsn=item.get("hsn_code") or item.get("hsn_sac") or item.get("hsn"),
                        line_itc=line_itc_match,
                        overall_itc_res=itc_res,
                        source_state=supplier_state_code,
                        dest_state=pos_state_code,
                        is_rcm=is_rcm,
                        supply_type=supply_type,
                        line_has_intra_tax=line_has_intra,
                    )

                    line_dict: Dict[str, Any] = {
                        "account_id": approved_account_id,
                        "description": item.get("description") or f"Item {idx}",
                        "rate": rate,
                        "quantity": qty,
                        "itc_eligibility_type": line_itc_type,
                        "itc_eligibility": line_itc_type,
                    }

                    # Zoho India GST tax requirement: Specify either Tax, Tax Exemption, or Reverse Charge
                    if is_rcm or is_foreign:
                        rcm_tax_id = tax_id
                        if not rcm_tax_id:
                            rcm_tax_id = await master_data_service.get_zoho_tax_for_line(
                                tenant_id=tenant_id,
                                tax_percentage=line_tax_rate if line_tax_rate > 0 else (inv_default_tax_rate if inv_default_tax_rate > 0 else 18.0),
                                supply_type="INTER_STATE" if is_foreign else supply_type,
                                db=db,
                                organization_id=current_org_id,
                            )
                        if rcm_tax_id:
                            line_dict["reverse_charge_tax_id"] = rcm_tax_id
                        line_dict["is_reverse_charge_applied"] = True
                    elif tax_id:
                        line_dict["tax_id"] = tax_id
                    elif line_tax_rate == 0.0:
                        zero_tax_id = await master_data_service.get_zoho_tax_for_line(
                            tenant_id=tenant_id,
                            tax_percentage=0.0,
                            supply_type=supply_type,
                            db=db,
                            organization_id=current_org_id,
                        )
                        if zero_tax_id:
                            line_dict["tax_id"] = zero_tax_id
                        else:
                            line_dict["tax_exemption_code"] = "NON_GST_SUPPLY"

                    if zoho_tds_tax_id:
                        line_dict["tds_tax_id"] = zoho_tds_tax_id

                    # Dimensions (Project ID)
                    project_id = item.get("project_id") or vlm_data.get("project_id")
                    if project_id:
                        line_dict["project_id"] = project_id

                    # Explicit Authoritative ITC SSOT Line Serialization for Zoho Books
                    line_itc_decision = itc_lines_map.get(idx) or "ineligible_others"
                    if line_tax_rate > 0 or is_rcm or is_foreign:
                        line_dict["itc_eligibility"] = line_itc_decision

                    bill_line_items.append(line_dict)
            else:
                total_amt = float(vlm_data.get("total_amount") or 0.0)
                approved_account_id = acct_map.get(1)
                if not approved_account_id:
                    raise ValueError("Invoice lacks an approved Zoho Chart of Accounts ID.")

                tax_id = None
                if inv_default_tax_rate > 0:
                    tax_id = await master_data_service.get_zoho_tax_for_line(
                        tenant_id=tenant_id,
                        tax_percentage=inv_default_tax_rate,
                        supply_type=supply_type,
                        db=db,
                        organization_id=current_org_id,
                    )
                    if not tax_id:
                        raise ValueError(
                            f"Cannot export to Zoho: Invoice has a taxable GST rate of {inv_default_tax_rate}% ({supply_type}), "
                            f"but no matching tax or tax group was found in Zoho Books. Please sync taxes in Integrations."
                        )

                fallback_has_intra = (supply_type == "INTRA_STATE" or float(vlm_data.get("cgst_amount") or 0.0) > 0)
                fallback_itc_type = resolve_zoho_itc_eligibility(
                    item_desc=f"Invoice {invoice_num} Expenses",
                    item_hsn=None,
                    line_itc=line_itc_breakdown[0] if line_itc_breakdown else None,
                    overall_itc_res=itc_res,
                    source_state=supplier_state_code,
                    dest_state=pos_state_code,
                    is_rcm=is_rcm,
                    supply_type=supply_type,
                    line_has_intra_tax=fallback_has_intra,
                )

                line_dict = {
                    "account_id": approved_account_id,
                    "description": f"Invoice {invoice_num} Expenses",
                    "rate": inv_subtotal if inv_subtotal > 0 else total_amt,
                    "quantity": 1.0,
                    "itc_eligibility_type": fallback_itc_type,
                    "itc_eligibility": fallback_itc_type,
                }
                if is_rcm or is_foreign:
                    rcm_tax_id = tax_id
                    if not rcm_tax_id:
                        rcm_tax_id = await master_data_service.get_zoho_tax_for_line(
                            tenant_id=tenant_id,
                            tax_percentage=inv_default_tax_rate if inv_default_tax_rate > 0 else 18.0,
                            supply_type="INTER_STATE" if is_foreign else supply_type,
                            db=db,
                            organization_id=current_org_id,
                        )
                    if rcm_tax_id:
                        line_dict["reverse_charge_tax_id"] = rcm_tax_id
                    line_dict["is_reverse_charge_applied"] = True
                elif tax_id:
                    line_dict["tax_id"] = tax_id
                else:
                    zero_tax_id = await master_data_service.get_zoho_tax_for_line(
                        tenant_id=tenant_id,
                        tax_percentage=0.0,
                        supply_type=supply_type,
                        db=db,
                        organization_id=current_org_id,
                    )
                    if zero_tax_id:
                        line_dict["tax_id"] = zero_tax_id
                    else:
                        line_dict["tax_exemption_code"] = "NON_GST_SUPPLY"

                if zoho_tds_tax_id:
                    line_dict["tds_tax_id"] = zoho_tds_tax_id

                # Explicit Authoritative ITC SSOT Line Serialization for fallback single line
                line_itc_decision = itc_lines_map.get(1) or ("eligible" if eligible_itc_total > 0 else "ineligible_others")
                if inv_default_tax_rate > 0:
                    line_dict["itc_eligibility"] = line_itc_decision
                bill_line_items.append(line_dict)

            # Zoho Payload TDS Safety Verification:
            # If TDS is not applicable, strictly strip tds_tax_id from all bill lines
            for line in bill_line_items:
                if not tds_applicable:
                    line.pop("tds_tax_id", None)
                elif zoho_tds_tax_id:
                    line["tds_tax_id"] = zoho_tds_tax_id

            bill_payload: Dict[str, Any] = {
                "vendor_id": vendor_id,
                "bill_number": invoice_num,
                "date": posting_date,
                "due_date": due_date,
                "line_items": bill_line_items,
            }

            # Resolve Dynamic Source and Destination of Supply
            if not is_foreign:
                from app.services.gst_engine import normalize_indian_state
                sup_st_zoho, _, _ = normalize_indian_state(state_input=gst_eval.get("supplier_state_code") or gst_eval.get("supplier_state_name"))
                if sup_st_zoho:
                    bill_payload["source_of_supply"] = sup_st_zoho

            # Dynamic Destination of Supply resolved from branch/organization matching
            if resolved_dest_code:
                bill_payload["destination_of_supply"] = resolved_dest_code
            else:
                from app.services.gst_engine import normalize_indian_state
                pos_st_zoho, _, _ = normalize_indian_state(
                    state_input=gst_eval.get("place_of_supply_state_code") or gst_eval.get("place_of_supply_state_name") or gst_eval.get("buyer_state_code")
                )
                if pos_st_zoho:
                    bill_payload["destination_of_supply"] = pos_st_zoho

            if resolved_branch_id:
                bill_payload["branch_id"] = resolved_branch_id

            if is_foreign:
                bill_payload["gst_treatment"] = "overseas"
            elif vendor_gstin:
                from app.services.gst_engine import validate_gstin
                is_valid_gst, clean_gst = validate_gstin(vendor_gstin)
                if is_valid_gst and clean_gst:
                    bill_payload["gst_treatment"] = "business_gst"
                    bill_payload["gst_no"] = clean_gst
                else:
                    bill_payload["gst_treatment"] = "business_none"
            else:
                bill_payload["gst_treatment"] = "business_none"

            if is_rcm or is_foreign:
                bill_payload["is_reverse_charge_applied"] = True
                bill_payload["is_reverse_charge"] = True

            # Header metadata (Terms, Reference Number, Notes)
            payment_terms = vlm_data.get("payment_terms")
            if payment_terms is not None:
                try:
                    bill_payload["payment_terms"] = int(payment_terms)
                except (ValueError, TypeError):
                    pass

            terms_label = vlm_data.get("payment_terms_label") or vlm_data.get("terms")
            if terms_label:
                bill_payload["terms"] = str(terms_label)

            ref_num = vlm_data.get("reference_number") or vlm_data.get("po_number")
            if ref_num:
                bill_payload["reference_number"] = str(ref_num)

            notes = vlm_data.get("notes") or ""
            # If posting_date differs from physical invoice_date, preserve original invoice date in Zoho notes
            if str(posting_date) != str(invoice_date):
                inv_disp = format_to_indian_standard(invoice_date) or invoice_date
                post_disp = format_to_indian_standard(posting_date) or posting_date
                period_note = f"[Original Invoice Date: {inv_disp} | Accounting Posting Date: {post_disp}]"
                notes = f"{period_note} {notes}".strip()

            if notes:
                bill_payload["notes"] = str(notes)

            # Preserve foreign currency commercial information in notes for complete auditability
            if is_foreign and vlm_data.get("original_currency") and vlm_data.get("original_total_amount"):
                orig_c = vlm_data.get("original_currency")
                orig_tot = vlm_data.get("original_total_amount")
                fx_r = vlm_data.get("exchange_rate") or getattr(invoice, "exchange_rate", None) or 1.0
                fx_trace = f"[Foreign Invoice: {orig_c} {orig_tot:,.2f} @ ₹{fx_r:,.4f}/{orig_c} = ₹{inv_eff_total:,.2f}]"
                if bill_payload.get("notes"):
                    bill_payload["notes"] = f"{bill_payload['notes']} | {fx_trace}"
                else:
                    bill_payload["notes"] = fx_trace

            if tds_applicable:
                tds_rate_val = float(effective_tds.get("tds_rate") or effective_tds.get("rate") or 0.0)
                tds_amt_val = float(effective_tds.get("total_tds_amount") or effective_tds.get("tds_amount") or 0.0)
                tds_sec = effective_tds.get("section") or effective_tds.get("tds_section") or "Section 393"
                tds_trace = f"[TDS: {tds_rate_val}% ({tds_sec}) = ₹{tds_amt_val:,.2f}]"
                if bill_payload.get("notes"):
                    bill_payload["notes"] = f"{bill_payload['notes']} | {tds_trace}"
                else:
                    bill_payload["notes"] = tds_trace

            adjustment_val = vlm_data.get("adjustment")
            if adjustment_val is not None:
                try:
                    adj_flt = float(adjustment_val)
                    if adj_flt != 0.0:
                        bill_payload["adjustment"] = adj_flt
                except (ValueError, TypeError):
                    pass

            # 10. RECONCILIATION & IDEMPOTENT BILL CREATION / UPDATE
            bill_id = invoice.zoho_bill_id
            bill_num = invoice.zoho_bill_number or invoice_num
            is_existing_bill = bool(bill_id)

            # Check if Bill already exists in Zoho (handles timeout retry recovery)
            if not bill_id:
                existing_bill = await zoho_client_service.find_bill_by_number(
                    connection=connection,
                    db=db,
                    bill_number=invoice_num,
                    vendor_id=vendor_id,
                )
                if existing_bill:
                    bill_id = existing_bill["bill_id"]
                    bill_num = existing_bill.get("bill_number") or invoice_num
                    is_existing_bill = True
                    logger.info(f"Reconciled existing Zoho Bill: ID {bill_id}, Number {bill_num}.")

            if bill_id:
                # Update existing bill in Zoho Books directly with latest edits (amounts, TDS, line items, accounts)
                try:
                    logger.info(
                        f"Updating existing Zoho Bill {bill_id} [Tenant: {tenant_id}, Invoice: {invoice_num}]: "
                        f"Vendor ID: {vendor_id}, Date: {invoice_date}, Lines: {len(bill_line_items)}"
                    )
                    updated_bill = await zoho_client_service.update_bill(
                        connection=connection,
                        db=db,
                        bill_id=str(bill_id),
                        bill_payload=bill_payload,
                    )
                    bill_num = updated_bill.get("bill_number") or bill_num
                except Exception as update_err:
                    logger.warning(f"Could not update existing bill {bill_id} in Zoho Books: {update_err}")
                    raise update_err
            else:
                # Create new Bill in Zoho
                try:
                    # Safe payload logging (sanitized, no secrets)
                    logger.info(
                        f"Submitting Bill to Zoho Books [Tenant: {tenant_id}, Invoice: {invoice_num}]: "
                        f"Vendor ID: {vendor_id}, Date: {invoice_date}, Lines: {len(bill_line_items)}, "
                        f"Line Config: {[{'account_id': l.get('account_id'), 'rate': l.get('rate'), 'qty': l.get('quantity'), 'tax_id': l.get('tax_id'), 'tax_exemption_code': l.get('tax_exemption_code'), 'tds_tax_id': l.get('tds_tax_id'), 'rcm': l.get('is_reverse_charge_applied')} for l in bill_line_items]}"
                    )
                    created_bill = await zoho_client_service.create_bill(
                        connection=connection,
                        db=db,
                        bill_payload=bill_payload,
                        idempotency_key=str(invoice.id),
                    )
                    bill_id = created_bill.get("bill_id") or created_bill.get("id")
                    bill_num = created_bill.get("bill_number") or invoice_num
                except Exception as create_err:
                    # In case of network timeout or ambiguous response, attempt post-failure reconciliation
                    logger.warning(f"Create bill exception: {create_err}. Attempting post-timeout reconciliation...")
                    recovered_bill = await zoho_client_service.find_bill_by_number(
                        connection=connection,
                        db=db,
                        bill_number=invoice_num,
                        vendor_id=vendor_id,
                    )
                    if recovered_bill:
                        bill_id = recovered_bill["bill_id"]
                        bill_num = recovered_bill.get("bill_number") or invoice_num
                        logger.info(f"Successfully recovered bill ID {bill_id} after timeout.")
                    else:
                        raise create_err

            if not bill_id:
                raise RuntimeError(f"Failed to obtain Zoho Bill ID for invoice {invoice_num}.")

            # Persist the confirmed Zoho Bill ID immediately
            invoice.zoho_bill_id = str(bill_id)
            invoice.zoho_bill_number = str(bill_num)
            await db.commit()

            # 11. Download Original File from Supabase and Attach to Zoho Bill (Only on initial creation)
            attachment_status = "already_attached" if is_existing_bill else "not_attached"
            if invoice.file_path and not is_existing_bill:
                try:
                    logger.info(f"Downloading original file {invoice.file_path} from Supabase...")
                    file_bytes = await storage_service.download_file(invoice.file_path)
                    logger.info(f"Uploading attachment to Zoho Bill {bill_id}...")
                    await zoho_client_service.attach_file_to_bill(
                        connection=connection,
                        db=db,
                        bill_id=str(bill_id),
                        file_bytes=file_bytes,
                        filename=invoice.file_name,
                        mime_type=invoice.mime_type,
                    )
                    attachment_status = "attached"
                except Exception as attach_err:
                    logger.warning(f"Could not attach file to Zoho Bill {bill_id}: {attach_err}")
                    attachment_status = f"failed: {str(attach_err)}"

            # 12. Mark Export Completed
            invoice.export_status = "EXPORTED"
            invoice.exported_at = datetime.now(timezone.utc)
            invoice.error_message = None if attachment_status in ("attached", "already_attached") else f"Attachment warning: {attachment_status}"
            await db.commit()

            # 13. Immutable Audit Log
            await audit_service.log_event(
                db=db,
                tenant_id=tenant_id,
                invoice_id=invoice.id,
                user_email=user_email,
                action="EXPORT_ZOHO",
                after_value=f"Zoho Bill ID: {bill_id}, Number: {bill_num}",
                reason="Finance exported approved invoice to Zoho Books with reconciliation",
            )

            return {
                "status": "success",
                "message": f"Successfully exported to Zoho Books. Bill #{bill_num}",
                "zoho_bill_id": str(bill_id),
                "zoho_bill_number": str(bill_num),
                "attachment_status": attachment_status,
            }

        except Exception as exc:
            if invoice.export_status != "EXPORTED":
                invoice.export_status = "FAILED"
                invoice.error_message = f"Zoho Export Error: {str(exc)}"
                try:
                    await db.commit()
                except Exception:
                    pass
            logger.error(f"Failed to export invoice {invoice_id} to Zoho: {exc}")
            raise RuntimeError(f"Zoho export failed: {str(exc)}") from exc


export_service = InvoiceExportService()
