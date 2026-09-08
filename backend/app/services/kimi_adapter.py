import logging
import re
from typing import Any, Dict, List, Optional

from app.services.financial_validator import parse_clean_numeric

logger = logging.getLogger(__name__)


class KimiK3ResponseAdapter:
    """
    Normalizes the current NVIDIA NIM / Colab Kimi K3 response into the
    backend's internal application structure.

    External model contract = fixed JSON structure used by the current Colab.
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
    def normalize_kimi_response(
        cls,
        kimi_response: Dict[str, Any],
        user_zoho_coa: Optional[
            List[Dict[str, Any]]
        ] = None,
    ) -> Dict[str, Any]:
        """
        Convert the current fixed JSON Colab response into the internal
        application structures.

        Expected external top-level structure (Kimi_K3_NVIDIA_FixedJSON_Foreground_Live_FINAL.ipynb):

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
            kimi_response,
            dict,
        ):
            raise ValueError(
                "Kimi K3 response must be a JSON object."
            )

        root = kimi_response
        if isinstance(root.get("prediction"), dict):
            root = root["prediction"]
        elif isinstance(root.get("data"), dict) and any(
            k in root["data"] for k in ("invoice_details", "vendor_details", "line_items", "financial_details")
        ):
            root = root["data"]

        # ---------------------------------------------------------
        # Current Colab fixed JSON structure with root fallback
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
            vendor_details.get("vendor_pan") or vendor_details.get("pan")
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

            # Master gst_rate reconciliation
            if gst_rate is None:
                if igst_rate is not None and igst_rate > 0:
                    gst_rate = igst_rate
                elif (cgst_rate or 0.0) + (sgst_rate or 0.0) > 0:
                    gst_rate = round((cgst_rate or 0.0) + (sgst_rate or 0.0), 2)
            else:
                # Master gst_rate exists but individual rates are missing
                if igst_amount is not None and igst_amount > 0 and igst_rate is None:
                    igst_rate = gst_rate
                elif (cgst_amount is not None and cgst_amount > 0 or sgst_amount is not None and sgst_amount > 0):
                    if cgst_rate is None:
                        cgst_rate = round(gst_rate / 2.0, 2)
                    if sgst_rate is None:
                        sgst_rate = round(gst_rate / 2.0, 2)

            # Total line total derivation
            if total is None and taxable_amount is not None:
                comp_taxes = (cgst_amount or 0.0) + (sgst_amount or 0.0) + (igst_amount or 0.0) + (cess_amount or 0.0)
                total = round(taxable_amount + comp_taxes, 2)

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
        tds_applicable = bool(tds_applicable_raw) if tds_applicable_raw is not None else False

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
            or "Kimi K3 TDS proposal"
        )

        normalized_tds = {
            "applicable": tds_applicable,
            "tds_applicable": tds_applicable,
            "section": tds_provision,
            "tds_section": tds_provision,
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
            "tds_reasoning": tds_reason,
            "is_approved": False,
            "approval_status": "PENDING",
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
            "raw_vlm_output": kimi_response,
            "normalized_data": normalized_data,
            "normalized_accounting": normalized_accounting,
        }