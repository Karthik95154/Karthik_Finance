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
from app.services.journal_generator import journal_generator

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

        # 2. Check Approval and Export Status
        if invoice.approval_status != "APPROVED":
            raise ValueError(
                f"Invoice must be APPROVED by Finance before exporting to Zoho. Current status: {invoice.approval_status}"
            )

        if invoice.export_status == "EXPORTED" and invoice.zoho_bill_id:
            return {
                "status": "already_exported",
                "message": "Invoice has already been exported to Zoho Books.",
                "zoho_bill_id": invoice.zoho_bill_id,
                "zoho_bill_number": invoice.zoho_bill_number,
                "attachment_status": "attached",
            }

        # 3. Check Balanced Journal Entry Existence
        journal_query = select(JournalEntry).where(
            JournalEntry.invoice_id == invoice_id,
            JournalEntry.tenant_id == tenant_id,
        )
        j_res = await db.execute(journal_query)
        journal_entry = j_res.scalar_one_or_none()
        if (
            not journal_entry
            or not journal_entry.is_balanced
            or journal_entry.status not in ("BALANCED", "APPROVED", "POSTED")
        ):
            raise ValueError("Invoice cannot be exported without an approved, balanced General Ledger journal entry.")

        # 4. Check Date Validity & Authoritative Working Data
        from app.core.date_utils import parse_and_normalize_date, validate_invoice_due_dates
        from app.services.invoice_processing import get_effective_invoice_data
        
        vlm_data_check = get_effective_invoice_data(invoice)

        raw_inv_date = vlm_data_check.get("invoice_date")
        raw_due_date = vlm_data_check.get("due_date")
        invoice_date_norm = parse_and_normalize_date(raw_inv_date) or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        due_date_norm = parse_and_normalize_date(raw_due_date) or invoice_date_norm

        is_valid_dates, date_err = validate_invoice_due_dates(invoice_date_norm, due_date_norm)
        if not is_valid_dates:
            raise ValueError(f"Cannot export to Zoho: {date_err}")

        # 5. Check Zoho Connection
        connection = await master_data_service.get_or_create_zoho_connection(tenant_id, db)
        if connection.status != "CONNECTED" or not connection.organization_id:
            raise ValueError("Tenant is not connected to a Zoho Books organization. Please connect Zoho first.")

        # 6. Set In-Flight Lock
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
            due_date = due_date_norm

            # 8. Authoritative Line Item Account Validation (ZERO SYNTHETIC FALLBACK)
            accounting = {}
            if isinstance(invoice.current_accounting_output, dict):
                accounting = invoice.current_accounting_output
            elif isinstance(invoice.accounting_output, dict):
                accounting = invoice.accounting_output

            acct_lines = accounting.get("accounting") or []
            if not acct_lines:
                raise ValueError("Cannot export to Zoho: Invoice has no accounting line items.")

            # Retrieve active synchronized Zoho accounts to validate and resolve if available in DB
            valid_zoho_accounts = {}
            name_to_zoho_id = {}
            default_expense_id = None
            try:
                coa_query = select(ChartOfAccount).where(
                    ChartOfAccount.tenant_id == tenant_id,
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

            acct_map = {}
            for item in acct_lines:
                idx = item.get("line_index", 1)
                approved_acc_id = item.get("approved_account_id") or item.get("final_account_id")
                approved_acc_name = item.get("approved_account_name") or item.get("final_account_name") or item.get("account_name") or ""
                
                if not approved_acc_id or str(approved_acc_id).startswith("ACC_"):
                    if approved_acc_name and str(approved_acc_name).lower().strip() in name_to_zoho_id:
                        approved_acc_id = name_to_zoho_id[str(approved_acc_name).lower().strip()]
                    else:
                        raise ValueError(
                            f"Cannot export to Zoho: Line item {idx} ('{item.get('source_description') or idx}') has an unmapped/placeholder account '{approved_acc_id}'. "
                            f"An active Zoho Chart of Accounts account must be selected and approved by Finance before export."
                        )

                if valid_zoho_accounts and str(approved_acc_id) not in valid_zoho_accounts:
                    if approved_acc_name and str(approved_acc_name).lower().strip() in name_to_zoho_id:
                        approved_acc_id = name_to_zoho_id[str(approved_acc_name).lower().strip()]
                    else:
                        raise ValueError(
                            f"Cannot export to Zoho: Line item {idx} account '{approved_acc_id}' is not in the synchronized active Zoho Chart of Accounts. "
                            f"Please sync COA in integrations and select a valid Zoho account."
                        )
                acct_map[idx] = str(approved_acc_id)

            # 8. Resolve Supply Type & TDS Configuration
            from app.services.gst_engine import gst_engine
            gst_eval = gst_engine.evaluate_gst(vlm_data)
            supply_type = gst_eval.get("supply_type") or "INTRA_STATE"

            tds_info = accounting.get("tds") or {}
            tds_applicable = bool(tds_info.get("applicable") or tds_info.get("tds_applicable") or tds_info.get("is_applicable"))
            tds_provision = tds_info.get("approved_tds_provision") or tds_info.get("tds_provision") or tds_info.get("provision")
            tds_section = tds_info.get("approved_tds_section") or tds_info.get("tds_section") or tds_info.get("section")
            tds_nature = tds_info.get("approved_nature_of_payment") or tds_info.get("nature_of_payment") or tds_info.get("nature")
            tds_rate = tds_info.get("approved_tds_rate") or tds_info.get("tds_rate") or tds_info.get("rate")

            zoho_tds_tax_id = None
            if tds_applicable:
                zoho_tds_tax_id = await master_data_service.get_zoho_tds_tax(
                    tenant_id=tenant_id,
                    section=tds_section,
                    provision=tds_provision,
                    nature_of_payment=tds_nature,
                    rate=float(tds_rate) if tds_rate is not None else None,
                    db=db,
                )

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
                vendor_contact = await zoho_client_service.create_vendor(
                    connection=connection,
                    db=db,
                    vendor_name=vendor_name,
                    gstin=vendor_gstin,
                    pan=vendor_pan,
                    email=vlm_data.get("vendor_email"),
                    phone=vlm_data.get("vendor_phone"),
                    address=vlm_data.get("vendor_address"),
                    state_name=supplier_state_name,
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
            is_rcm = bool(gst_eval.get("is_reverse_charge") or vlm_data.get("is_reverse_charge"))

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

            if raw_items:
                for idx, item in enumerate(raw_items, 1):
                    approved_account_id = acct_map.get(idx)
                    if not approved_account_id:
                        raise ValueError(f"Line item {idx} lacks an approved Zoho Chart of Accounts ID.")

                    taxable_amount = float(item.get("taxable_amount") or item.get("total") or 0.0)
                    qty = float(item.get("quantity") or 1.0)
                    rate = float(
                        item.get("unit_price")
                        or item.get("rate")
                        or (taxable_amount / qty if qty > 0 and taxable_amount > 0 else taxable_amount)
                        or 1.0
                    )

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
                        )
                        if not tax_id:
                            raise ValueError(
                                f"Cannot export to Zoho: Line item {idx} has a taxable GST rate of {line_tax_rate}% ({supply_type}), "
                                f"but no matching tax or tax group was found in Zoho Books. Please sync taxes in Integrations."
                            )

                    line_dict: Dict[str, Any] = {
                        "account_id": approved_account_id,
                        "description": item.get("description") or f"Item {idx}",
                        "rate": rate,
                        "quantity": qty,
                    }

                    # Zoho India GST tax requirement: Specify either Tax, Tax Exemption, or Reverse Charge
                    if tax_id:
                        line_dict["tax_id"] = tax_id
                    elif line_tax_rate == 0.0:
                        zero_tax_id = await master_data_service.get_zoho_tax_for_line(
                            tenant_id=tenant_id,
                            tax_percentage=0.0,
                            supply_type=supply_type,
                            db=db,
                        )
                        if zero_tax_id:
                            line_dict["tax_id"] = zero_tax_id
                        else:
                            line_dict["tax_exemption_code"] = "NON_GST_SUPPLY"

                    if is_rcm:
                        line_dict["is_reverse_charge_applied"] = True

                    if zoho_tds_tax_id:
                        line_dict["tds_tax_id"] = zoho_tds_tax_id

                    # Dimensions (Project ID)
                    project_id = item.get("project_id") or vlm_data.get("project_id")
                    if project_id:
                        line_dict["project_id"] = project_id

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
                    )
                    if not tax_id:
                        raise ValueError(
                            f"Cannot export to Zoho: Invoice has a taxable GST rate of {inv_default_tax_rate}% ({supply_type}), "
                            f"but no matching tax or tax group was found in Zoho Books. Please sync taxes in Integrations."
                        )

                line_dict = {
                    "account_id": approved_account_id,
                    "description": f"Invoice {invoice_num} Expenses",
                    "rate": inv_subtotal if inv_subtotal > 0 else total_amt,
                    "quantity": 1.0,
                }
                if tax_id:
                    line_dict["tax_id"] = tax_id
                else:
                    zero_tax_id = await master_data_service.get_zoho_tax_for_line(
                        tenant_id=tenant_id,
                        tax_percentage=0.0,
                        supply_type=supply_type,
                        db=db,
                    )
                    if zero_tax_id:
                        line_dict["tax_id"] = zero_tax_id
                    else:
                        line_dict["tax_exemption_code"] = "NON_GST_SUPPLY"

                if is_rcm:
                    line_dict["is_reverse_charge_applied"] = True

                if zoho_tds_tax_id:
                    line_dict["tds_tax_id"] = zoho_tds_tax_id
                bill_line_items.append(line_dict)

            bill_payload: Dict[str, Any] = {
                "vendor_id": vendor_id,
                "bill_number": invoice_num,
                "date": invoice_date,
                "due_date": due_date,
                "line_items": bill_line_items,
            }

            supplier_state_code = to_zoho_state_code(gst_eval.get("supplier_state_code") or gst_eval.get("supplier_state_name"))
            pos_state_code = to_zoho_state_code(gst_eval.get("place_of_supply_state_code") or gst_eval.get("place_of_supply_state_name") or gst_eval.get("buyer_state_code"))

            if supplier_state_code:
                bill_payload["source_of_supply"] = supplier_state_code
            if pos_state_code:
                bill_payload["destination_of_supply"] = pos_state_code

            if vendor_gstin:
                from app.services.gst_engine import validate_gstin
                is_valid_gst, clean_gst = validate_gstin(vendor_gstin)
                if is_valid_gst and clean_gst:
                    bill_payload["gst_treatment"] = "business_gst"
                    bill_payload["gst_no"] = clean_gst
                else:
                    bill_payload["gst_treatment"] = "business_none"
            else:
                bill_payload["gst_treatment"] = "business_none"

            if is_rcm:
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

            notes = vlm_data.get("notes")
            if notes:
                bill_payload["notes"] = str(notes)

            # 10. RECONCILIATION & IDEMPOTENT BILL CREATION
            bill_id = invoice.zoho_bill_id
            bill_num = invoice.zoho_bill_number or invoice_num

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
                    logger.info(f"Reconciled existing Zoho Bill: ID {bill_id}, Number {bill_num}. Skipping creation.")

            # If still not found, create new Bill in Zoho
            if not bill_id:
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

            # 11. Download Original File from Supabase and Attach to Zoho Bill
            attachment_status = "not_attached"
            if invoice.file_path:
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
            invoice.error_message = None if attachment_status == "attached" else f"Attachment warning: {attachment_status}"
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
                await db.commit()
            logger.error(f"Failed to export invoice {invoice_id} to Zoho: {exc}")
            raise RuntimeError(f"Zoho export failed: {str(exc)}") from exc


export_service = InvoiceExportService()
