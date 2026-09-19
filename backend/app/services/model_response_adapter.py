import logging
import re
from typing import Any, Dict, List, Optional

from app.services.financial_validator import parse_clean_numeric
from app.services.tds_engine import parse_vendor_declared_tds

logger = logging.getLogger(__name__)


class ModelResponseAdapter:
    """
    Normalizes the AI model's fixed JSON response into the
    backend's internal application structure.

    External model contract = fixed JSON structure (provider-independent).
    There is NO JSON-Schema lock here.

    The adapter intentionally keeps the external contract isolated from the
    rest of the backend.
    """

    EXTERNAL_STRUCTURE_VERSION = "2.3.0"

    @classmethod
    def extract_pan_from_gstin(
        cls,
        gstin: Optional[str],
    ) -> Optional[str]:
        """
        Derive a 10-character PAN from a valid-looking 15-character GSTIN
        using GSTIN characters 3-12 (Python slice [2:12]).
        """
        if not gstin:
            return None

        clean_gst = str(gstin).strip().upper()

        if len(clean_gst) < 15:
            return None

        pan = clean_gst[2:12]

        if re.match(
            r"^[A-Z]{5}[0-9]{4}[A-Z]$",
            pan,
        ):
            return pan

        return None

    @staticmethod
    def _clean_optional_string(
        value: Any,
    ) -> Optional[str]:
        if value is None:
            return None

        s = str(value).strip()

        if not s or s.lower() in ("null", "none", "n/a"):
            return None

        return s

    @staticmethod
    def _get_numeric(
        obj: Dict[str, Any],
        key: str,
    ) -> Optional[float]:
        """
        Preserve missing/null as None.
        Explicit numeric zero remains 0.0.
        """
        if key not in obj or obj.get(key) is None:
            return None

        val = obj.get(key)
        if isinstance(val, str) and val.strip().lower() in ("null", "none", "n/a", ""):
            return None

        return parse_clean_numeric(val)

    @staticmethod
    def _get_bool(
        obj: Dict[str, Any],
        key: str,
        default: bool = False,
    ) -> bool:
        value = obj.get(key)

        if value is None:
            return default

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() in {
                "true",
                "1",
                "yes",
                "y",
            }

        return bool(value)

    @classmethod
    def normalize_model_response(
        cls,
        model_response: Dict[str, Any],
        user_zoho_coa: Optional[
            List[Dict[str, Any]]
        ] = None,
        raw_document_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Convert the AI model's fixed JSON response into the internal
        application structures.

        Expected external top-level structure (fixed JSON contract):

        invoice_details
        vendor_details
        customer_details
        line_items
        financial_details
        gst_support
        tds_support
        tcs_support
        itc_support
        coa_support
        gl_support
        validation
        review_flags

        The external model response is retained unchanged in raw_vlm_output.
        """

        if not isinstance(
            model_response,
            dict,
        ):
            raise ValueError(
                "Model response must be a JSON object."
            )

        root = model_response
        if isinstance(root.get("prediction"), dict):
            root = root["prediction"]
        elif isinstance(root.get("data"), dict) and any(
            k in root["data"] for k in ("invoice_details", "vendor_details", "line_items", "financial_details")
        ):
            root = root["data"]

        # ---------------------------------------------------------
        # Fixed JSON contract structure with root fallback
        # ---------------------------------------------------------
        invoice_details = (
            root.get("invoice_details")
            or {}
        )

        vendor_details = (
            root.get("vendor_details")
            or {}
        )

        customer_details = (
            root.get("customer_details")
            or {}
        )

        line_items = (
            root.get("line_items")
            or invoice_details.get("line_items")
            or []
        )

        financial_details = (
            root.get("financial_details")
            or {}
        )

        gst_support = (
            root.get("gst_support")
            or {}
        )

        tds_support = (
            root.get("tds_support")
            or {}
        )

        tcs_support = (
            root.get("tcs_support")
            or {}
        )

        itc_support = (
            root.get("itc_support")
            or {}
        )

        coa_support = (
            root.get("coa_support")
            or {}
        )

        gl_support = (
            root.get("gl_support")
            or {}
        )

        validation = (
            root.get("validation")
            or {}
        )

        review_flags = (
            root.get("review_flags")
            or []
        )

        if not isinstance(invoice_details, dict):
            invoice_details = {}
        if not isinstance(vendor_details, dict):
            vendor_details = {}
        if not isinstance(customer_details, dict):
            customer_details = {}
        if not isinstance(line_items, list):
            line_items = []
        if not isinstance(financial_details, dict):
            financial_details = {}
        if not isinstance(gst_support, dict):
            gst_support = {}
        if not isinstance(tds_support, dict):
            tds_support = {}
        if not isinstance(tcs_support, dict):
            tcs_support = {}
        if not isinstance(itc_support, dict):
            itc_support = {}
        if not isinstance(coa_support, dict):
            coa_support = {}
        if not isinstance(gl_support, dict):
            gl_support = {}
        if not isinstance(validation, dict):
            validation = {}
        if not isinstance(review_flags, list):
            review_flags = []

        # ---------------------------------------------------------
        # 1. Vendor / customer details
        # ---------------------------------------------------------
        v_name = cls._clean_optional_string(
            vendor_details.get("vendor_name") or vendor_details.get("name")
        )
        v_address = cls._clean_optional_string(
            vendor_details.get("vendor_address") or vendor_details.get("address")
        )
        v_gstin = cls._clean_optional_string(
            vendor_details.get("vendor_gstin") or vendor_details.get("gstin")
        )
        v_pan = cls._clean_optional_string(
            vendor_details.get("vendor_pan") or vendor_details.get("pan") or vendor_details.get("pan_number")
        )
        v_phone = cls._clean_optional_string(
            vendor_details.get("vendor_phone") or vendor_details.get("phone")
        )
        v_email = cls._clean_optional_string(
            vendor_details.get("vendor_email") or vendor_details.get("email")
        )

        # Derive vendor PAN only from vendor GSTIN
        if not v_pan and v_gstin:
            v_pan = cls.extract_pan_from_gstin(v_gstin)

        c_name = cls._clean_optional_string(
            customer_details.get("customer_name") or customer_details.get("name")
        )
        c_address = cls._clean_optional_string(
            customer_details.get("customer_address") or customer_details.get("address")
        )
        c_gstin = cls._clean_optional_string(
            customer_details.get("customer_gstin") or customer_details.get("gstin")
        )
        c_pan = cls._clean_optional_string(
            customer_details.get("customer_pan") or customer_details.get("pan")
        )
        c_phone = cls._clean_optional_string(
            customer_details.get("customer_phone") or customer_details.get("phone")
        )
        c_email = cls._clean_optional_string(
            customer_details.get("customer_email") or customer_details.get("email")
        )

        # Derive customer PAN only from customer GSTIN
        if not c_pan and c_gstin:
            c_pan = cls.extract_pan_from_gstin(c_gstin)

        # Bank details parsing: check all structural possibilities (vendor_details.bank_details, payment_details, root.bank_details, root.payment_details, or flat vendor/payment fields)
        raw_bank = vendor_details.get("bank_details") or root.get("bank_details") or root.get("payment_details") or vendor_details.get("payment_details")
        b_name, b_acc, b_ifsc, b_branch, b_upi = None, None, None, None, None

        if isinstance(raw_bank, dict):
            b_name = cls._clean_optional_string(raw_bank.get("bank_name") or raw_bank.get("name") or raw_bank.get("bank"))
            b_acc = cls._clean_optional_string(
                raw_bank.get("account_number") or raw_bank.get("bank_account_number") or raw_bank.get("acc_no") or raw_bank.get("a_c_no") or raw_bank.get("account_no")
            )
            b_ifsc = cls._clean_optional_string(raw_bank.get("ifsc_code") or raw_bank.get("ifsc") or raw_bank.get("ifsc_code_candidate"))
            b_branch = cls._clean_optional_string(raw_bank.get("branch") or raw_bank.get("branch_name") or raw_bank.get("branch_and_address"))
            b_upi = cls._clean_optional_string(raw_bank.get("upi_id") or raw_bank.get("vpa") or raw_bank.get("upi"))

        # Fallback to flat vendor_details or root keys if any key is missing
        b_name = b_name or cls._clean_optional_string(vendor_details.get("bank_name") or root.get("bank_name") or invoice_details.get("bank_name"))
        b_acc = b_acc or cls._clean_optional_string(
            vendor_details.get("bank_account_number") or vendor_details.get("account_number") or root.get("bank_account_number") or root.get("account_number")
        )
        b_ifsc = b_ifsc or cls._clean_optional_string(vendor_details.get("ifsc_code") or vendor_details.get("ifsc") or root.get("ifsc_code") or root.get("ifsc"))
        b_branch = b_branch or cls._clean_optional_string(vendor_details.get("branch") or root.get("branch"))
        b_upi = b_upi or cls._clean_optional_string(vendor_details.get("upi_id") or vendor_details.get("vpa") or root.get("upi_id") or root.get("vpa"))

        if b_name or b_acc or b_ifsc or b_branch or b_upi:
            bank_details = {
                "bank_name": b_name,
                "account_number": b_acc,
                "ifsc_code": b_ifsc,
                "branch": b_branch,
                "upi_id": b_upi,
            }
        elif isinstance(raw_bank, str) and raw_bank.strip():
            bank_details = {"raw_text": raw_bank.strip()}
        else:
            bank_details = None

        # ---------------------------------------------------------
        # 2. Active Zoho COA lookup
        # ---------------------------------------------------------
        coa_map_by_id: Dict[str, Dict[str, Any]] = {}
        coa_map_by_name: Dict[str, Dict[str, Any]] = {}

        for account in (user_zoho_coa or []):
            if not isinstance(account, dict):
                continue
            account_id = cls._clean_optional_string(
                account.get("account_id") or account.get("zoho_account_id")
            )
            account_name = cls._clean_optional_string(
                account.get("account_name")
            )
            if account_id:
                coa_map_by_id[account_id] = account
            if account_name:
                coa_map_by_name[account_name.lower()] = account

        raw_line_matches = coa_support.get("line_matches") or []
        if not isinstance(raw_line_matches, list):
            raw_line_matches = []

        line_matches_by_index: Dict[int, Dict[str, Any]] = {}
        for match in raw_line_matches:
            if not isinstance(match, dict):
                continue
            raw_index = match.get("line_index")
            try:
                if raw_index is None:
                    continue
                line_index = int(raw_index)
            except (TypeError, ValueError):
                continue
            line_matches_by_index[line_index] = match

        # ---------------------------------------------------------
        # 3. Normalize invoice line items
        # ---------------------------------------------------------
        normalized_line_items: List[Dict[str, Any]] = []
        accounting_lines: List[Dict[str, Any]] = []

        for external_position, item in enumerate(line_items):
            if not isinstance(item, dict):
                continue

            raw_line_index = item.get("line_index")
            try:
                model_line_index = (
                    int(raw_line_index)
                    if raw_line_index is not None
                    else external_position
                )
            except (TypeError, ValueError):
                model_line_index = external_position

            display_idx = model_line_index if (raw_line_index is not None and int(raw_line_index) > 0) else model_line_index + 1

            description = cls._clean_optional_string(item.get("description"))
            quantity = cls._get_numeric(item, "quantity")
            unit = cls._clean_optional_string(item.get("unit"))
            unit_price = cls._get_numeric(item, "unit_price")
            discount = cls._get_numeric(item, "discount") or cls._get_numeric(item, "discount_amount")
            discount_type = cls._clean_optional_string(item.get("discount_type"))
            line_amount = cls._get_numeric(item, "line_amount")
            taxable_amount = cls._get_numeric(item, "taxable_amount")
            hsn_sac = cls._clean_optional_string(item.get("hsn_sac") or item.get("hsn_code"))
            gst_rate = cls._get_numeric(item, "gst_rate")
            cgst_rate = cls._get_numeric(item, "cgst_rate")
            cgst_amount = cls._get_numeric(item, "cgst_amount")
            sgst_rate = cls._get_numeric(item, "sgst_rate")
            sgst_amount = cls._get_numeric(item, "sgst_amount")
            igst_rate = cls._get_numeric(item, "igst_rate")
            igst_amount = cls._get_numeric(item, "igst_amount")
            cess_rate = cls._get_numeric(item, "cess_rate")
            cess_amount = cls._get_numeric(item, "cess_amount")
            total = cls._get_numeric(item, "total") or cls._get_numeric(item, "total_amount")

            # -----------------------------------------------------
            # Automatic Bidirectional Math & Tax Calculation Rules
            # -----------------------------------------------------
            if line_amount is None and quantity is not None and unit_price is not None:
                line_amount = round(quantity * unit_price, 2)

            if taxable_amount is None:
                if line_amount is not None:
                    taxable_amount = round(line_amount - (discount or 0.0), 2)

            # Bidirectional IGST calculation
            if igst_amount is not None and igst_amount > 0 and taxable_amount and taxable_amount > 0:
                calc_igst_rate = round((igst_amount / taxable_amount) * 100.0, 2)
                if igst_rate is None:
                    igst_rate = calc_igst_rate
            elif igst_rate is not None and igst_rate > 0 and taxable_amount is not None and igst_amount is None:
                igst_amount = round((taxable_amount * igst_rate) / 100.0, 2)

            # Bidirectional CGST calculation
            if cgst_amount is not None and cgst_amount > 0 and taxable_amount and taxable_amount > 0:
                calc_cgst_rate = round((cgst_amount / taxable_amount) * 100.0, 2)
                if cgst_rate is None:
                    cgst_rate = calc_cgst_rate
            elif cgst_rate is not None and cgst_rate > 0 and taxable_amount is not None and cgst_amount is None:
                cgst_amount = round((taxable_amount * cgst_rate) / 100.0, 2)

            # Bidirectional SGST calculation
            if sgst_amount is not None and sgst_amount > 0 and taxable_amount and taxable_amount > 0:
                calc_sgst_rate = round((sgst_amount / taxable_amount) * 100.0, 2)
                if sgst_rate is None:
                    sgst_rate = calc_sgst_rate
            elif sgst_rate is not None and sgst_rate > 0 and taxable_amount is not None and sgst_amount is None:
                sgst_amount = round((taxable_amount * sgst_rate) / 100.0, 2)

            # Determine supply/tax classification context (Intra-State vs Inter-State)
            hdr_cgst = cls._get_numeric(financial_details, "cgst_amount") or cls._get_numeric(financial_details, "cgst_total")
            hdr_sgst = cls._get_numeric(financial_details, "sgst_amount") or cls._get_numeric(financial_details, "sgst_total")
            hdr_igst = cls._get_numeric(financial_details, "igst_amount") or cls._get_numeric(financial_details, "igst_total")
            
            tax_components = gst_support.get("tax_components_candidate") or []
            if isinstance(tax_components, str):
                tax_components = [tax_components]
            tax_components_str = " ".join(tax_components).upper()
            
            supply_candidate = (gst_support.get("supply_type_candidate") or "").upper()
            is_intra = (
                supply_candidate == "INTRA_STATE" or 
                "CGST" in tax_components_str or 
                "SGST" in tax_components_str or 
                (hdr_cgst is not None and hdr_cgst > 0) or 
                (hdr_sgst is not None and hdr_sgst > 0)
            )
            is_inter = (
                supply_candidate == "INTER_STATE" or 
                "IGST" in tax_components_str or 
                (hdr_igst is not None and hdr_igst > 0)
            )

            # Master gst_rate reconciliation and automatic component split
            if gst_rate is None:
                if igst_rate is not None and igst_rate > 0:
                    gst_rate = igst_rate
                elif (cgst_rate or 0.0) + (sgst_rate or 0.0) > 0:
                    gst_rate = round((cgst_rate or 0.0) + (sgst_rate or 0.0), 2)
                elif taxable_amount and taxable_amount > 0:
                    # Fallback: check if header has a single tax rate (e.g. 5%)
                    hdr_taxable = cls._get_numeric(financial_details, "taxable_amount") or cls._get_numeric(financial_details, "subtotal")
                    if hdr_taxable and hdr_taxable > 0:
                        if is_intra and hdr_cgst and hdr_cgst > 0:
                            gst_rate = round(((hdr_cgst * 2.0) / hdr_taxable) * 100.0, 2)
                        elif is_inter and hdr_igst and hdr_igst > 0:
                            gst_rate = round((hdr_igst / hdr_taxable) * 100.0, 2)

            if gst_rate is not None and gst_rate > 0:
                # Master gst_rate exists: split according to tax context
                if is_intra or (not is_inter and not (igst_amount and igst_amount > 0)):
                    # Intra-state: split into CGST and SGST
                    if cgst_rate is None:
                        cgst_rate = round(gst_rate / 2.0, 2)
                    if sgst_rate is None:
                        sgst_rate = round(gst_rate / 2.0, 2)
                    if taxable_amount is not None and taxable_amount > 0:
                        if cgst_amount is None:
                            cgst_amount = round((taxable_amount * cgst_rate) / 100.0, 2)
                        if sgst_amount is None:
                            sgst_amount = round((taxable_amount * sgst_rate) / 100.0, 2)
                elif is_inter or (igst_amount and igst_amount > 0):
                    # Inter-state: IGST
                    if igst_rate is None:
                        igst_rate = gst_rate
                    if taxable_amount is not None and taxable_amount > 0 and igst_amount is None:
                        igst_amount = round((taxable_amount * igst_rate) / 100.0, 2)

            # Total line total derivation: reconcile taxable amount + all applicable taxes
            comp_taxes = (cgst_amount or 0.0) + (sgst_amount or 0.0) + (igst_amount or 0.0) + (cess_amount or 0.0)
            if taxable_amount is not None:
                calc_total = round(taxable_amount + comp_taxes, 2)
                # If total is missing, or if total was equal to pretax taxable_amount despite taxes being present,
                # or if total is significantly lower than taxable + taxes, update to full inclusive total.
                if total is None:
                    total = calc_total
                elif comp_taxes > 0 and (abs(total - taxable_amount) < 0.05 or abs(total - calc_total) > 0.05):
                    total = calc_total

            normalized_item = {
                "line_index": display_idx,
                "description": description or f"Item {display_idx}",
                "hsn_code": hsn_sac,
                "hsn_sac": hsn_sac,
                "quantity": quantity,
                "unit": unit,
                "unit_price": unit_price,
                "discount": discount,
                "discount_type": discount_type,
                "line_amount": line_amount,
                "taxable_amount": taxable_amount,
                "gst_rate": gst_rate,
                "cgst_rate": cgst_rate,
                "cgst_amount": cgst_amount,
                "sgst_rate": sgst_rate,
                "sgst_amount": sgst_amount,
                "igst_rate": igst_rate,
                "igst_amount": igst_amount,
                "cess_rate": cess_rate,
                "cess_amount": cess_amount,
                "total": total,
            }
            normalized_line_items.append(normalized_item)

            # Resolve COA from canonical root line_matches or inline suggestion
            match = line_matches_by_index.get(model_line_index) or {}
            inline_coa = item.get("coa_suggestion") or item.get("coa_match") or {}

            suggested_id = cls._clean_optional_string(
                match.get("matched_account_id") or match.get("account_id") or inline_coa.get("account_id")
            )
            suggested_name = cls._clean_optional_string(
                match.get("matched_account_name") or match.get("account_name") or inline_coa.get("account_name")
            )
            confidence = cls._get_numeric(match, "confidence") if "confidence" in match else cls._get_numeric(inline_coa, "confidence")

            requires_review = cls._get_bool(
                match,
                "requires_review",
                default=(suggested_id is None and suggested_name is None),
            )

            matched_account_id = None
            matched_account_name = None
            match_status = "NO_MATCH"
            reason = cls._clean_optional_string(match.get("reason")) or "No active Zoho COA match found."

            if suggested_id and suggested_id in coa_map_by_id:
                account = coa_map_by_id[suggested_id]
                matched_account_id = suggested_id
                matched_account_name = account.get("account_name")
                match_status = "EXACT_MATCH"
            elif suggested_name and suggested_name.lower() in coa_map_by_name:
                account = coa_map_by_name[suggested_name.lower()]
                matched_account_id = account.get("account_id") or account.get("zoho_account_id")
                matched_account_name = account.get("account_name")
                match_status = "EXACT_MATCH"
            elif suggested_name:
                import difflib
                best_ratio = 0.0
                best_account = None
                for account_name_key, account_obj in coa_map_by_name.items():
                    ratio = difflib.SequenceMatcher(
                        None, suggested_name.lower(), account_name_key
                    ).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_account = account_obj
                if best_account and best_ratio >= 0.70:
                    match_status = "SUGGESTED_MATCH"
                    matched_account_name = best_account.get("account_name")
                    reason = f"Suggested match '{matched_account_name}' ({int(best_ratio * 100)}% similarity). Approval required."
                    requires_review = True

            accounting_lines.append({
                "line_index": display_idx,
                "source_description": description or f"Item {display_idx}",
                "account_id": matched_account_id if match_status == "EXACT_MATCH" else None,
                "account_name": matched_account_name or suggested_name or "General Expenses",
                "account_type": inline_coa.get("account_type") or "expense",
                "ai_account_id": suggested_id or None,
                "ai_account_name": suggested_name or "General Expenses",
                "ai_account_type": inline_coa.get("account_type") or "expense",
                "ai_confidence": confidence if confidence is not None else 0.0,
                "ai_needs_review": match_status != "EXACT_MATCH" or requires_review,
                "match_status": match_status,
                "match_message": reason,
                "approved_account_id": matched_account_id if match_status == "EXACT_MATCH" else None,
                "approved_account_name": matched_account_name if match_status == "EXACT_MATCH" else None,
            })

        # ---------------------------------------------------------
        # 4. Financial details
        # ---------------------------------------------------------
        subtotal_val = cls._get_numeric(financial_details, "subtotal")
        discount_total = cls._get_numeric(financial_details, "discount_total")
        taxable_total = cls._get_numeric(financial_details, "taxable_amount")
        tax_total = cls._get_numeric(financial_details, "tax_total")
        cgst_total = cls._get_numeric(financial_details, "cgst_amount") or cls._get_numeric(financial_details, "cgst_total")
        sgst_total = cls._get_numeric(financial_details, "sgst_amount") or cls._get_numeric(financial_details, "sgst_total")
        igst_total = cls._get_numeric(financial_details, "igst_amount") or cls._get_numeric(financial_details, "igst_total")
        cess_total = cls._get_numeric(financial_details, "cess_amount") or cls._get_numeric(financial_details, "cess_total")
        shipping_val = cls._get_numeric(financial_details, "shipping_charges")
        other_val = cls._get_numeric(financial_details, "other_charges")
        adjustment_val = cls._get_numeric(financial_details, "adjustment")
        round_off = cls._get_numeric(financial_details, "round_off")
        grand_total = cls._get_numeric(financial_details, "total_amount")
        notes_val = cls._clean_optional_string(financial_details.get("notes"))

        # Fallback: If subtotal is null, derive it from taxable_total or sum of line items taxable amounts
        if subtotal_val is None:
            if taxable_total is not None:
                subtotal_val = taxable_total
            else:
                line_taxable_sum = sum(
                    float(it.get("taxable_amount") or it.get("line_amount") or 0.0)
                    for it in normalized_line_items
                )
                if line_taxable_sum > 0:
                    subtotal_val = round(line_taxable_sum, 2)

        # ---------------------------------------------------------
        # ---------------------------------------------------------
        # 5. TDS support
        # ---------------------------------------------------------
        tds_applicable_raw = (
            tds_support.get("tds_applicable_candidate")
            if "tds_applicable_candidate" in tds_support
            else (
                tds_support.get("tds_applicable")
                if "tds_applicable" in tds_support
                else tds_support.get("applicable")
            )
        )

        tds_nature = cls._clean_optional_string(
            tds_support.get("payment_nature") or tds_support.get("nature_of_payment")
        )
        law_version = cls._clean_optional_string(tds_support.get("law_version_candidate"))
        tds_provision = cls._clean_optional_string(
            tds_support.get("provision_candidate") or tds_support.get("section") or tds_support.get("provision")
        )
        legacy_provision = cls._clean_optional_string(tds_support.get("legacy_provision_reference"))
        tds_rate = cls._get_numeric(tds_support, "rate_candidate") or cls._get_numeric(tds_support, "rate") or cls._get_numeric(tds_support, "tds_rate")
        tds_base = cls._get_numeric(tds_support, "base_candidate") or cls._get_numeric(tds_support, "base_amount") or cls._get_numeric(tds_support, "tds_base_amount")
        proposed_tds = cls._get_numeric(tds_support, "proposed_tds_amount") or cls._get_numeric(tds_support, "proposed_amount")
        threshold_status = cls._clean_optional_string(tds_support.get("threshold_status"))
        pan_status = cls._clean_optional_string(tds_support.get("pan_status"))
        cumulative_required = cls._get_bool(tds_support, "cumulative_vendor_data_required", default=False)
        tds_requires_backend_validation = cls._get_bool(tds_support, "requires_backend_validation", default=True)
        tds_reason = (
            cls._clean_optional_string(tds_support.get("reason") or tds_support.get("reasoning"))
            or "TDS proposal"
        )

        # Extract vendor-declared TDS evidence from text sources (raw document text, notes, terms, descriptions)
        text_sources_to_scan = [
            raw_document_text,
            notes_val,
            invoice_details.get("payment_terms"),
            financial_details.get("payment_terms"),
        ]
        for li in normalized_line_items:
            if li.get("description"):
                text_sources_to_scan.append(li.get("description"))

        vendor_decl = parse_vendor_declared_tds(
            text_sources=text_sources_to_scan,
            base_amount=subtotal_val,
        )

        tds_sec_code = None

        # Statutory evaluation: evaluate both line-item level composite services and header-level fallbacks
        is_indiv = bool(v_pan and len(v_pan) >= 4 and v_pan[3].upper() in ("P", "H"))
        
        # 1. Inspect line items for specific statutory service classifications
        line_tds_deductions = []
        has_ambiguous_9973 = False

        for l_idx, li in enumerate(normalized_line_items, 1):
            li_desc = str(li.get("description") or "").upper()
            li_sac = str(li.get("hsn_sac") or li.get("hsn_code") or "").upper()
            li_taxable = float(li.get("taxable_amount") or li.get("line_amount") or 0.0)
            combo_text = f"{li_desc} {li_sac}"

            l_app = False
            l_rate = 0.0
            l_sec = None
            l_prov = None

            # Check for software / SaaS / licensing first (even if SAC has 9973 / 997331)
            is_software_saas = any(
                k in combo_text
                for k in (
                    "997331",
                    "99733",
                    "SOFTWARE",
                    "SAAS",
                    "SUBSCRIPTION",
                    "LICENSE",
                    "LICENSING",
                    "PLATFORM",
                    "APPLICATION",
                    "PORTAL",
                )
            )

            # Section 194J / Section 393(1) Sl 6(iii)
            is_prof_candidate = any(k in combo_text for k in ("PROFESSIONAL", "LEGAL", "CONSULTING", "ARCHITECT", "STATUTORY AUDIT", "TAX AUDIT"))
            is_tech_candidate = is_software_saas or any(k in combo_text for k in ("9983", "9982", "TECHNICAL", "IT SERVICE", "IT_SERVICE", "DEVELOPMENT", "CLOUD", "INFRASTRUCTURE", "SECURITY AUDIT", "VULNERABILITY"))
            if is_prof_candidate or is_tech_candidate:
                l_sec = "194J"
                if is_tech_candidate and not (is_prof_candidate and "LEGAL" in combo_text):
                    l_prov = "Section 194J - Fees for Technical Services"
                    l_rate = 2.0
                else:
                    l_prov = "Section 194J - Professional Services"
                    l_rate = 10.0
                l_app = (li_taxable > 0)
            # Section 194I (Rent / Lease of Equipment vs Immovable Property)
            elif any(k in combo_text for k in ("9972", "9973", "RENT", "RENTAL", "LEASE", "HIRING")):
                # Check for physical equipment / machinery / vehicles / plant
                is_equipment = any(
                    m in combo_text
                    for m in (
                        "99731",
                        "99732",
                        "EQUIPMENT",
                        "CCTV",
                        "PLANT",
                        "MACHINERY",
                        "VEHICLE",
                        "HARDWARE",
                        "GENERATOR",
                        "COMPUTER HARDWARE",
                    )
                )
                # Check for immovable property (land, building, office space)
                is_immovable = any(
                    p in combo_text
                    for p in (
                        "9972",
                        "BUILDING",
                        "LAND",
                        "OFFICE",
                        "PREMISES",
                        "WAREHOUSE",
                        "PROPERTY",
                        "COMMERCIAL SPACE",
                    )
                )

                if is_equipment:
                    l_sec = "194I"
                    l_prov = "Section 194I - Rent of Plant, Machinery or Equipment"
                    l_rate = 2.0
                    l_app = (li_taxable > 0)
                elif is_immovable or any(r in combo_text for r in ("RENT", "RENTAL", "LEASE")):
                    l_sec = "194I"
                    l_prov = "Section 194I - Rent of Immovable Property"
                    l_rate = 10.0
                    l_app = (li_taxable > 0)
                else:
                    # Ambiguous 9973xx with no equipment, software, or rent keywords:
                    # Do NOT force statutory classification (no 194I, no rate). Flag for review and preserve taxable base.
                    has_ambiguous_9973 = True
                    l_sec = None
                    l_prov = None
                    l_rate = None
                    l_app = (li_taxable > 0)
            # Section 194C (Manpower, Security Guards, Contractor, Facilities, Transportation)
            elif any(k in combo_text for k in ("9985", "MANPOWER", "GUARD", "FACILITY", "CONTRACTOR", "WORK_CONTRACT", "SUBCONTRACT", "TRANSPORT", "HOUSEKEEPING", "CLEANING")) or ("SECURITY" in combo_text and any(w in combo_text for w in ("GUARD", "PERSONNEL", "MANPOWER", "DEPLOYMENT", "FACILITY", "PATROL", "SURVEILLANCE"))):
                l_sec = "194C"
                l_prov = "Section 194C - Payments to Contractors / Manpower"
                l_rate = 1.0 if is_indiv else 2.0
                l_app = (li_taxable > 0)
            # Section 194H (Commission / Brokerage)
            elif any(k in combo_text for k in ("COMMISSION", "BROKERAGE")):
                l_sec = "194H"
                l_prov = "Section 194H - Commission or Brokerage"
                l_rate = 2.0
                l_app = (li_taxable > 0)

            if l_app and li_taxable > 0:
                l_tds_amt = round((li_taxable * l_rate) / 100.0, 2) if (l_rate is not None and l_rate > 0) else None
                line_tds_deductions.append({
                    "line_index": l_idx,
                    "section": l_sec,
                    "provision": l_prov,
                    "rate": l_rate,
                    "base_amount": li_taxable,
                    "tds_amount": l_tds_amt,
                })

        # 2. Check if composite line-level statutory deduction exists
        if line_tds_deductions:
            tds_applicable = True
            comp_base = round(sum(d["base_amount"] for d in line_tds_deductions), 2)
            known_tds_amts = [d["tds_amount"] for d in line_tds_deductions if d["tds_amount"] is not None]
            comp_tds_total = round(sum(known_tds_amts), 2) if known_tds_amts else None
            unique_sections = sorted(list(set(d["section"] for d in line_tds_deductions if d["section"])))
            
            # If model already provided an explicit provision/section (e.g. 194C) and deductions are single-section, preserve it
            if len(unique_sections) > 1:
                tds_provision = ", ".join(unique_sections)
                tds_nature = "Composite Services (" + ", ".join(f"{d['section']}: Rs.{d['tds_amount']}" for d in line_tds_deductions if d['tds_amount'] is not None) + ")"
                tds_rate = round((comp_tds_total / comp_base) * 100.0, 2) if (comp_tds_total is not None and comp_base > 0) else None
                tds_reason_parts = [f"{d['section']} on Rs.{d['base_amount']:,.2f}" for d in line_tds_deductions if d['section']]
                tds_reason = f"Composite statutory withholding: {', '.join(tds_reason_parts)}"
            elif len(unique_sections) == 1:
                tds_sec_code = (
                    line_tds_deductions[0].get("section")
                    if line_tds_deductions and line_tds_deductions[0].get("section")
                    else unique_sections[0]
                )
                tds_provision = (
                    line_tds_deductions[0].get("provision")
                    if line_tds_deductions and line_tds_deductions[0].get("provision")
                    else (tds_provision or tds_sec_code)
                )
                tds_nature = tds_nature or (line_tds_deductions[0].get("provision") if line_tds_deductions else "Statutory deduction")
                tds_rate = tds_rate or (line_tds_deductions[0].get("rate") if line_tds_deductions else None)
                tds_reason = f"Statutory withholding under {tds_provision} on assessable value Rs.{comp_base:,.2f}"
            else:
                # No unique statutory sections resolved (e.g. all lines are ambiguous SAC 9973)
                tds_sec_code = None
                tds_provision = None
                tds_nature = "Classification Unresolved"
                tds_rate = None
                tds_reason = f"Classification unresolved for assessable value Rs.{comp_base:,.2f}. Manual review required."

            tds_base = comp_base
            proposed_tds = comp_tds_total
        elif tds_applicable_raw is None:
            # Fallback to header-level evaluation if no specific service lines triggered
            candidate_base = tds_base or subtotal_val or 0.0
            nature_check = (f"{tds_nature or ''} {tds_provision or ''}").upper()

            is_contractor = any(k in nature_check for k in ("CONTRACTOR", "MANPOWER", "SECURITY", "FACILITY", "SUBCONTRACT", "WORK_CONTRACT", "194C", "SL 6 I"))
            is_prof_tech = any(k in nature_check for k in ("TECHNICAL", "PROFESSIONAL", "CONSULTING", "LEGAL", "SOFTWARE", "IT_SERVICE", "194J", "SL 6 III", "FTS"))
            is_rent = any(k in nature_check for k in ("RENT", "LEASE", "194I", "SL 2"))
            is_commission = any(k in nature_check for k in ("COMMISSION", "BROKERAGE", "194H", "SL 1 II"))
            is_purchase = any(k in nature_check for k in ("PURCHASE", "GOODS", "194Q", "SL 8 II"))

            if is_contractor:
                if candidate_base > 0:
                    tds_applicable = True
                    if not tds_provision:
                        tds_provision = "Section 393(1) [Table Sl. No. 6(i)]"
                    if not tds_nature:
                        tds_nature = "CONTRACTOR_WORK"
                    if tds_rate is None or tds_rate <= 0:
                        tds_rate = 1.0 if is_indiv else 2.0
                else:
                    tds_applicable = False
            elif is_purchase:
                if candidate_base > 0:
                    tds_applicable = True
                    if not tds_provision:
                        tds_provision = "Section 393(1) [Table Sl. No. 8(ii)]"
                    if not tds_nature:
                        tds_nature = "PURCHASE_OF_GOODS"
                    if tds_rate is None or tds_rate <= 0:
                        tds_rate = 0.1
                else:
                    tds_applicable = False
            elif is_prof_tech:
                if candidate_base > 0:
                    tds_applicable = True
                    is_fts = "TECHNICAL" in nature_check or "FTS" in nature_check or "CLOUD" in nature_check or "SOFTWARE" in nature_check
                    if not tds_provision:
                        tds_provision = "Section 393(1) [Table Sl. No. 6(iii)(D)(a)]" if is_fts else "Section 393(1) [Table Sl. No. 6(iii)(D)(b)]"
                    if not tds_nature:
                        tds_nature = "TECHNICAL_SERVICES" if is_fts else "PROFESSIONAL_SERVICES"
                    if tds_rate is None or tds_rate <= 0:
                        tds_rate = 2.0 if is_fts else 10.0
                else:
                    tds_applicable = False
            elif is_rent:
                if candidate_base > 0:
                    tds_applicable = True
                    is_equipment = "EQUIPMENT" in nature_check or "PLANT" in nature_check or "MACHINERY" in nature_check
                    if not tds_provision:
                        tds_provision = "Section 393(1) [Table Sl. No. 2(ii)]"
                    if not tds_nature:
                        tds_nature = "RENT_PLANT_MACHINERY" if is_equipment else "RENT_LAND_BUILDING"
                    if tds_rate is None or tds_rate <= 0:
                        tds_rate = 2.0 if is_equipment else 10.0
                else:
                    tds_applicable = False
            elif is_commission:
                if candidate_base > 0:
                    tds_applicable = True
                    if not tds_provision:
                        tds_provision = "Section 393(1) [Table Sl. No. 1(ii)]"
                    if not tds_nature:
                        tds_nature = "COMMISSION_OR_BROKERAGE"
                    if tds_rate is None or tds_rate <= 0:
                        tds_rate = 2.0
                else:
                    tds_applicable = False
            else:
                tds_applicable = False
        else:
            tds_applicable = bool(tds_applicable_raw)

        if tds_applicable and (tds_base is None or tds_base <= 0) and subtotal_val:
            tds_base = subtotal_val

        if tds_applicable and (proposed_tds is None or proposed_tds <= 0) and tds_base and tds_rate:
            proposed_tds = round((tds_base * tds_rate) / 100.0, 2)

        # Conflict & Review Evaluation between Statutory Assessment and Vendor-Declared TDS
        # If TDS is applicable but rate/category is unresolved, flag for review
        is_category_unresolved = tds_applicable and (tds_rate is None or not tds_provision or tds_provision == "Section 393")
        tds_needs_review = bool(tds_requires_backend_validation or has_ambiguous_9973 or is_category_unresolved)
        tds_conflict_code = None
        tds_conflict_reason = None

        if has_ambiguous_9973 or is_category_unresolved:
            tds_needs_review = True
            tds_conflict_code = "TDS_AMBIGUOUS_SAC"
            if has_ambiguous_9973:
                tds_conflict_reason = "Ambiguous SAC 9973 service without clear equipment or software classification. Review required."
            else:
                tds_conflict_reason = f"TDS classification unresolved for '{tds_provision or tds_nature or 'Services'}'. Manual review required."

        if vendor_decl and vendor_decl.get("present"):
            v_amt = vendor_decl.get("amount")
            v_rate = vendor_decl.get("rate") or vendor_decl.get("derived_rate")
            has_amt_diff = v_amt is not None and proposed_tds is not None and abs(v_amt - proposed_tds) > 1.0
            has_rate_diff = v_rate is not None and tds_rate is not None and abs(v_rate - tds_rate) > 0.05

            if has_amt_diff or has_rate_diff:
                tds_needs_review = True
                tds_conflict_code = "TDS_VENDOR_STATUTORY_MISMATCH"
                v_desc = f"₹{v_amt:,.2f}" if v_amt is not None else ""
                if v_rate is not None:
                    v_desc += f" ({v_rate}%)"
                s_desc = f"₹{proposed_tds:,.2f}" if proposed_tds is not None else ""
                if tds_rate is not None:
                    s_desc += f" ({tds_rate}%)"
                tds_conflict_reason = (
                    f"Conflict between vendor-declared TDS [{v_desc}] and statutory determination [{s_desc}]. "
                    f"Statutory section: {tds_provision or 'Services'}. Manual review required."
                )

        eff_approval_status = "REVIEW_REQUIRED" if tds_needs_review else "PENDING"
        final_sec = tds_sec_code if (line_tds_deductions and len(unique_sections) <= 1) else tds_provision

        normalized_tds = {
            "applicable": tds_applicable,
            "tds_applicable": tds_applicable,
            "section": final_sec,
            "tds_section": final_sec,
            "provision": tds_provision,
            "tds_provision": tds_provision,
            "nature_of_payment": tds_nature,
            "law_version": law_version,
            "legacy_provision_reference": legacy_provision,
            "rate": tds_rate,
            "tds_rate": tds_rate,
            "base_amount": tds_base,
            "tds_base_amount": tds_base,
            "proposed_tds_amount": proposed_tds,
            "threshold_status": threshold_status,
            "pan_status": pan_status,
            "cumulative_vendor_data_required": cumulative_required,
            "requires_backend_validation": tds_requires_backend_validation,
            "tds_reasoning": tds_conflict_reason or tds_reason,
            "is_approved": False,
            "approval_status": eff_approval_status,
            "vendor_declared_tds": vendor_decl,
            "tds_needs_review": tds_needs_review,
            "tds_conflict_code": tds_conflict_code,
            "tds_conflict_reason": tds_conflict_reason,
        }

        # ---------------------------------------------------------
        # 6. Safety Net: Unmapped extra metadata preservation
        # ---------------------------------------------------------
        known_top_level = {
            "invoice_details",
            "vendor_details",
            "customer_details",
            "line_items",
            "financial_details",
            "gst_support",
            "tds_support",
            "tcs_support",
            "itc_support",
            "coa_support",
            "gl_support",
            "validation",
            "review_flags",
            "schema_version",
            "knowledge_version",
            "interpretation",
        }
        additional_fields = {
            k: v for k, v in root.items() if k not in known_top_level
        }

        # ---------------------------------------------------------
        # 7. Internal normalized data
        # ---------------------------------------------------------
        normalized_data = {
            "schema_version": root.get("schema_version") or cls.EXTERNAL_STRUCTURE_VERSION,
            "knowledge_version": root.get("knowledge_version"),
            "invoice_number": invoice_details.get("invoice_number"),
            "invoice_date": invoice_details.get("invoice_date"),
            "due_date": invoice_details.get("due_date"),
            "po_number": invoice_details.get("po_number"),
            "place_of_supply": invoice_details.get("place_of_supply"),
            "payment_terms": invoice_details.get("payment_terms"),
            "currency": invoice_details.get("currency") or "INR",
            "document_type": invoice_details.get("document_type"),
            "vendor_name": v_name,
            "vendor_address": v_address,
            "vendor_gstin": v_gstin,
            "vendor_pan": v_pan,
            "vendor_phone": v_phone,
            "vendor_email": v_email,
            "customer_name": c_name,
            "customer_address": c_address,
            "customer_gstin": c_gstin,
            "customer_pan": c_pan,
            "customer_phone": c_phone,
            "customer_email": c_email,
            "bank_details": bank_details,
            "line_items": normalized_line_items,
            "subtotal": subtotal_val,
            "discount_total": discount_total,
            "taxable_amount": taxable_total,
            "tax_total": tax_total,
            "cgst_amount": cgst_total,
            "sgst_amount": sgst_total,
            "igst_amount": igst_total,
            "cess_amount": cess_total,
            "shipping_charges": shipping_val,
            "other_charges": other_val,
            "adjustment": adjustment_val,
            "round_off": round_off,
            "total_amount": grand_total,
            "notes": notes_val,
            "additional_fields": additional_fields,
        }

        # ---------------------------------------------------------
        # 8. Normalized accounting support
        # ---------------------------------------------------------
        normalized_accounting = {
            "accounting": accounting_lines,
            "tds_assessment": normalized_tds,
            "tds": normalized_tds,
            "vendor_declared_tds": vendor_decl,
            "gst_support": gst_support,
            "itc_support": itc_support,
            "tcs_support": tcs_support,
            "coa_support": coa_support,
            "gl_support": gl_support,
            "validation": validation,
            "review_flags": review_flags,
            "interpretation": root.get("interpretation"),
        }

        return {
            "raw_vlm_output": model_response,
            "normalized_data": normalized_data,
            "normalized_accounting": normalized_accounting,
        }


    # Backward-compatibility alias for the renamed method
    normalize_kimi_response = normalize_model_response


# Backward-compatibility alias for legacy imports
KimiK3ResponseAdapter = ModelResponseAdapter