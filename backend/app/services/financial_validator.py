import re
import logging
from typing import Dict, Any, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

# Default financial validation monetary tolerance (in INR)
DEFAULT_TOLERANCE: float = getattr(settings, "FINANCIAL_VALIDATION_TOLERANCE", 1.0)


def parse_clean_numeric(val: Any) -> Optional[float]:
    """
    Safely converts strings/numbers with commas, spaces, currency symbols to clean float.
    Returns None if missing, non-finite (inf/-inf/nan), boolean, or unparseable.
    """
    import math
    if val is None or val == "":
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return float(val)
    if isinstance(val, str):
        clean = val.strip()
        if re.match(r"^[+\-]{2,}", clean):
            return None
        negative = False
        if clean.startswith("-"):
            negative = True
            clean = clean[1:].strip()
        elif clean.startswith("+"):
            clean = clean[1:].strip()
        elif clean.startswith("(") and clean.endswith(")"):
            negative = True
            clean = clean[1:-1].strip()

        clean = re.sub(r"^(?:Rupees|Rupee|Rs\.?|INR|₹)\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s*(?:/-\s*|Only\s*|%\s*)$", "", clean, flags=re.IGNORECASE)
        clean = clean.strip()
        if re.match(r"^[+\-]{2,}", clean):
            return None
        if not negative and clean.startswith("-"):
            negative = True
            clean = clean[1:].strip()
        elif not negative and clean.startswith("(") and clean.endswith(")"):
            negative = True
            clean = clean[1:-1].strip()
        elif negative and (clean.startswith("-") or clean.startswith("+")):
            return None
        if re.search(r"[a-zA-Z]", clean):
            return None
        if "," in clean:
            if clean.startswith(",") or clean.endswith(",") or ",," in clean:
                return None
            parts = clean.split(".")
            if len(parts) > 2:
                return None
            int_part = parts[0]
            if not int_part:
                return None
            indian_pattern = r"^\d{1,2}(?:,\d{2})*,\d{3}$"
            intl_pattern = r"^\d{1,3}(?:,\d{3})+$"
            if not (re.match(indian_pattern, int_part) or re.match(intl_pattern, int_part)):
                return None
            clean = clean.replace(",", "")
        if not re.match(r"^\d+(?:\.\d+)?$", clean):
            return None
        try:
            num = float(clean)
            if math.isnan(num) or math.isinf(num):
                return None
            return -num if negative else num
        except ValueError:
            return None
    return None
def parse_discount_semantics(item: Dict[str, Any]) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """
    Deterministically parses discount value and preserves discount_type semantics.
    Supports:
      - percentage ("percentage"): explicit %, percentage header, or discount_type="percentage"
      - amount ("amount"): explicit currency symbol (₹, Rs, INR), amount header, or discount_type="amount"
      - ambiguous ("ambiguous"): bare numeric discount without explicit percentage or amount indicator
    
    Returns: (discount_val, discount_type, ambiguity_or_error_reason)
      where discount_type is 'percentage', 'amount', or None.
      If ambiguous, discount_type is None and error_reason is 'AMBIGUOUS_DISCOUNT_CLASSIFICATION'.
      If invalid percentage (>100%), error_reason is 'INVALID_DISCOUNT_PERCENTAGE'.
      If negative discount (<0), error_reason is 'NEGATIVE_DISCOUNT'.
    """
    if not isinstance(item, dict):
        return None, None, None

    PERCENTAGE_HEADERS = {
        "discount %", "disc %", "discount rate", "rate of discount",
        "trade discount %", "cash discount %", "special discount %",
        "dealer discount %", "volume discount %", "scheme discount %", "rebate %",
        "discount_pct", "discount_percentage", "discount_rate"
    }

    AMOUNT_HEADERS = {
        "discount amount", "disc amt", "discount value", "trade discount amount",
        "cash discount amount", "rebate amount", "scheme discount amount",
        "special discount amount", "discount_amount", "disc_amt", "discount_val"
    }

    raw_disc = None
    source_key = None
    raw_fields = item.get("raw_fields") if isinstance(item.get("raw_fields"), dict) else {}

    # Check candidates in item and raw_fields
    for candidate_key in [
        "discount", "line_discount", "discount_amount", "discount_rate",
        "discount_pct", "discount_percentage", "disc", "disc_amt", "disc_rate"
    ]:
        if item.get(candidate_key) is not None:
            raw_disc = item.get(candidate_key)
            source_key = candidate_key
            break
        if raw_fields.get(candidate_key) is not None:
            raw_disc = raw_fields.get(candidate_key)
            source_key = candidate_key
            break

    # Also check any key in raw_fields that looks like a discount header
    if raw_disc is None and raw_fields:
        for k, v in raw_fields.items():
            k_norm = re.sub(r"[^a-z0-9%]+", " ", str(k).lower()).strip()
            if "disc" in k_norm or "rebate" in k_norm:
                raw_disc = v
                source_key = k
                break

    if raw_disc is None:
        return 0.0, "amount", None

    # Determine explicit discount_type if passed directly
    explicit_type = item.get("discount_type") or raw_fields.get("discount_type")
    if explicit_type:
        explicit_type = str(explicit_type).strip().lower()

    disc_str = str(raw_disc).strip()
    norm_source_key = re.sub(r"[^a-z0-9%]+", " ", str(source_key or "").lower()).strip()

    has_percent_symbol = "%" in disc_str or "%" in norm_source_key
    has_currency_symbol = any(cur in disc_str for cur in ["₹", "rs", "inr", "$", "eur", "usd", "gbp", "rs."]) or \
                          any(cur in norm_source_key for cur in ["₹", "inr", "rs"])

    # Clean numeric value
    num_val = parse_clean_numeric(raw_disc)
    if num_val is None:
        return None, None, None

    if num_val < 0:
        return num_val, None, "NEGATIVE_DISCOUNT"

    # CASE 1: Explicit percentage
    if explicit_type == "percentage" or has_percent_symbol or (norm_source_key in PERCENTAGE_HEADERS):
        if num_val > 100.0:
            return num_val, "percentage", "INVALID_DISCOUNT_PERCENTAGE"
        return num_val, "percentage", None

    # CASE 2: Explicit absolute amount
    if explicit_type == "amount" or has_currency_symbol or (norm_source_key in AMOUNT_HEADERS):
        return num_val, "amount", None

    # If discount is 0, type doesn't create mathematical ambiguity
    if num_val == 0.0:
        return 0.0, "amount", None

    # CASE 3: Ambiguous bare numeric discount - DO NOT GUESS
    return num_val, None, "AMBIGUOUS_DISCOUNT_CLASSIFICATION"


class FinancialValidator:
    """
    Deterministic Financial Validation and Reconciliation Engine.
    Independently verifies mathematical consistency of invoice financial fields
    without LLM guesswork or silently overwriting source data.
    """

    def __init__(self, tolerance: float = DEFAULT_TOLERANCE):
        self.tolerance = tolerance

    @staticmethod
    def extract_state_code(gstin: Optional[str]) -> Optional[str]:
        """Extracts the 2-digit Indian State/UT code from a 15-character GSTIN."""
        if not gstin or len(gstin.strip()) < 2:
            return None
        code = gstin.strip()[:2]
        if code.isdigit():
            return code
        return None

    @classmethod
    def determine_supply_type(
        cls,
        vendor_gstin: Optional[str],
        customer_gstin: Optional[str],
        place_of_supply: Optional[str] = None,
    ) -> str:
        """
        Determines whether the invoice is INTRA_STATE (CGST + SGST) or INTER_STATE (IGST).
        Defaults to INTRA_STATE if vendor and customer share state code.
        """
        vendor_state = cls.extract_state_code(vendor_gstin)
        customer_state = cls.extract_state_code(customer_gstin)

        if vendor_state and customer_state:
            return "INTRA_STATE" if vendor_state == customer_state else "INTER_STATE"

        if place_of_supply and vendor_state:
            if vendor_state in place_of_supply:
                return "INTRA_STATE"
            return "INTER_STATE"

        return "INTRA_STATE"

    @classmethod
    def validate_invoice_math(
        cls,
        data: Dict[str, Any],
        tolerance: float = 0.05,
    ) -> Tuple[bool, List[str], Dict[str, float]]:
        """
        Validates basic invoice arithmetic:
        Subtotal + Tax Total - Discount + Shipping + Other + Roundoff == Total Amount (+/- tolerance)
        """
        errors = []

        subtotal = float(data.get("subtotal") or 0.0)
        discount_total = float(data.get("discount_total") or 0.0)
        tax_total = float(data.get("tax_total") or 0.0)
        shipping = float(data.get("shipping_charges") or 0.0)
        other_charges = float(data.get("other_charges") or 0.0)
        adjustment = float(data.get("adjustment") or 0.0)
        round_off = float(data.get("round_off") or 0.0)
        total_amount = float(data.get("total_amount") or 0.0)

        line_items = data.get("line_items") or []
        line_taxable_sum = 0.0
        line_tax_sum = 0.0
        line_total_sum = 0.0

        for idx, item in enumerate(line_items, 1):
            qty = float(item.get("quantity") or 1.0)
            unit_price = float(item.get("unit_price") or 0.0)
            taxable = float(item.get("taxable_amount") or (qty * unit_price))
            cgst = float(item.get("cgst_amount") or 0.0)
            sgst = float(item.get("sgst_amount") or 0.0)
            igst = float(item.get("igst_amount") or 0.0)
            item_total = float(item.get("total") or (taxable + cgst + sgst + igst))

            line_taxable_sum += taxable
            line_tax_sum += (cgst + sgst + igst)
            line_total_sum += item_total

        effective_subtotal = subtotal or float(data.get("taxable_amount") or 0.0)
        if line_items and effective_subtotal > 0:
            diff = abs(line_taxable_sum - effective_subtotal)
            max_allowed_diff = max(0.50, len(line_items) * 0.10)
            if diff > max_allowed_diff and abs(line_taxable_sum - (effective_subtotal - discount_total)) > max_allowed_diff:
                errors.append(
                    f"Line taxable sum (₹{line_taxable_sum:.2f}) does not match header subtotal (₹{effective_subtotal:.2f})"
                )

        expected_grand_total = round(
            subtotal + tax_total - discount_total + shipping + other_charges + adjustment + round_off, 2
        )

        if total_amount > 0 and abs(expected_grand_total - total_amount) > tolerance:
            errors.append(
                f"Computed total (₹{expected_grand_total:.2f}) does not match invoice total (₹{total_amount:.2f})"
            )

        is_valid = len(errors) == 0
        computed_values = {
            "subtotal": subtotal,
            "tax_total": tax_total,
            "discount_total": discount_total,
            "computed_grand_total": expected_grand_total,
            "declared_grand_total": total_amount,
            "difference": round(abs(expected_grand_total - total_amount), 2),
        }

        return is_valid, errors, computed_values

    def validate_financials(
        self,
        invoice_data: Dict[str, Any],
        gst_result: Optional[Dict[str, Any]] = None,
        tolerance: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Alias for validate_invoice."""
        return self.validate_invoice(invoice_data, gst_result, tolerance)

    def validate_invoice(
        self,
        invoice_data: Dict[str, Any],
        gst_result: Optional[Dict[str, Any]] = None,
        tolerance: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Performs full deterministic financial reconciliation on an invoice.
        Compares Source/Extracted values vs Calculated values.
        """
        tol = tolerance if tolerance is not None else self.tolerance

        if not isinstance(invoice_data, dict):
            invoice_data = {}

        data_obj = invoice_data.get("data") if isinstance(invoice_data.get("data"), dict) else invoice_data

        # 1. Extract and normalize source values
        from app.services.gst_engine import extract_tax_value

        def _resolve_key(obj: Dict[str, Any], keys: List[str]) -> Any:
            for k in keys:
                if k in obj and obj[k] is not None:
                    return obj[k]
            return None

        # Robust numeric header resolution with conflict detection
        conflicting_header_issues: List[str] = []

        def _resolve_numeric_key(obj: Dict[str, Any], keys: List[str], field_label: str) -> Optional[float]:
            found: Dict[str, float] = {}
            for k in keys:
                if k in obj and obj[k] is not None:
                    val = parse_clean_numeric(obj[k])
                    if val is not None:
                        found[k] = val

            if not found:
                return None

            # Check if any two parsed aliases differ beyond tolerance
            vals = list(found.values())
            first_val = vals[0]
            for k, v in found.items():
                if abs(v - first_val) > tol:
                    issue = f"CONFLICTING_HEADER_ALIASES ({field_label}: {found})"
                    if issue not in conflicting_header_issues:
                        conflicting_header_issues.append(issue)
                    break
            return first_val

        src_subtotal = _resolve_numeric_key(data_obj, ["subtotal", "taxable_amount"], "subtotal")
        src_discount = _resolve_numeric_key(data_obj, ["discount_total", "discount"], "discount") or 0.0
        src_shipping = _resolve_numeric_key(data_obj, ["shipping_charges", "shipping"], "shipping") or 0.0
        src_other = _resolve_numeric_key(data_obj, ["other_charges", "additional_charges"], "other_charges") or 0.0
        src_adjustment = _resolve_numeric_key(data_obj, ["adjustment"], "adjustment") or 0.0
        src_round_off = _resolve_numeric_key(data_obj, ["round_off", "roundoff"], "round_off")
        src_total_amount = _resolve_numeric_key(data_obj, ["total_amount", "grand_total", "invoice_total"], "total_amount")

        # Source tax values
        src_cgst = extract_tax_value(data_obj, "cgst")
        src_sgst = extract_tax_value(data_obj, "sgst")
        src_igst = extract_tax_value(data_obj, "igst")
        src_cess = extract_tax_value(data_obj, "cess")
        src_tax_total = _resolve_numeric_key(data_obj, ["tax_total", "total_tax"], "tax_total")

        # Fallback to gst_result if provided and top-level fields are None
        if gst_result and isinstance(gst_result, dict):
            ext_gst = gst_result.get("extracted") or {}
            if src_cgst is None:
                src_cgst = ext_gst.get("cgst_amount")
            if src_sgst is None:
                src_sgst = ext_gst.get("sgst_amount")
            if src_igst is None:
                src_igst = ext_gst.get("igst_amount")
            if src_tax_total is None:
                src_tax_total = ext_gst.get("tax_total")

        raw_line_items = data_obj.get("line_items") or []

        checks: List[Dict[str, Any]] = []
        errors: List[str] = []
        warnings: List[str] = []
        has_mismatch = False
        has_review = False

        # -------------------------------------------------------------
        # CHECK 1: Line Item Math & Line Total Validation
        # (qty * unit_price - discount = taxable, AND taxable + line_taxes = line_total)
        # -------------------------------------------------------------
        line_item_checks: List[Dict[str, Any]] = []
        calc_line_taxables: List[float] = []
        calc_line_grosses: List[float] = []
        calc_line_discounts: List[float] = []
        
        # Line-level tax component accumulators for Header vs Line reconciliation
        calc_line_cgsts: List[float] = []
        calc_line_sgsts: List[float] = []
        calc_line_igsts: List[float] = []
        calc_line_cesses: List[float] = []
        calc_line_taxes: List[float] = []
        lines_with_tax_count = 0
        total_items_count = 0

        all_lines_valid = True

        hdr_tax_total_val = src_tax_total if src_tax_total is not None else 0.0

        if raw_line_items:
            for idx, item in enumerate(raw_line_items, 1):
                if not isinstance(item, dict):
                    continue

                desc = str(item.get("description") or f"Line {idx}")
                qty = parse_clean_numeric(item.get("quantity"))
                price = parse_clean_numeric(item.get("unit_price") or item.get("rate") or item.get("price"))
                
                # Step 1: Explicit taxable_amount
                ext_taxable = parse_clean_numeric(item.get("taxable_amount"))

                # Step 4 & 5: Determine explicit line total and handle aliases
                # Collect explicit total candidates
                explicit_total_aliases: Dict[str, float] = {}
                for k in ["total", "line_total", "item_total", "amount_total"]:
                    if item.get(k) is not None:
                        val_t = parse_clean_numeric(item[k])
                        if val_t is not None:
                            explicit_total_aliases[k] = val_t

                conflicting_totals = False
                unique_totals: List[float] = []
                for val_t in explicit_total_aliases.values():
                    if not any(abs(val_t - u) <= tol for u in unique_totals):
                        unique_totals.append(val_t)

                if len(unique_totals) > 1:
                    conflicting_totals = True

                ext_total: Optional[float] = next(iter(explicit_total_aliases.values())) if explicit_total_aliases else None

                # Check ambiguous 'amount' field
                raw_amount_val = parse_clean_numeric(item.get("amount"))
                ambiguous_amount_issue: Optional[str] = None
                if raw_amount_val is not None:
                    if ext_taxable is not None:
                        if abs(raw_amount_val - ext_taxable) <= tol:
                            # 'amount' matches taxable_amount within tolerance -> treat as taxable alias
                            pass
                        elif ext_total is not None:
                            if abs(raw_amount_val - ext_total) > tol:
                                ambiguous_amount_issue = "CONFLICTING_LINE_TOTAL_ALIASES"
                        else:
                            # 'amount' differs from taxable_amount and ext_total is absent -> represents line total
                            ext_total = raw_amount_val
                    elif ext_total is not None:
                        if abs(raw_amount_val - ext_total) > tol:
                            ambiguous_amount_issue = "CONFLICTING_LINE_TOTAL_ALIASES"
                    else:
                        # Neither ext_taxable nor ext_total was explicitly provided, only 'amount' exists
                        if hdr_tax_total_val == 0.0:
                            # Zero-tax invoice: amount can safely represent taxable and line total
                            ext_taxable = raw_amount_val
                            ext_total = raw_amount_val
                        else:
                            # Taxed invoice: ambiguous whether 'amount' is pre-tax or post-tax
                            ext_taxable = raw_amount_val
                            ambiguous_amount_issue = "AMBIGUOUS_AMOUNT_FIELD"

                # Step 2: Resolve line-level taxes (treat 0.00 as valid number, avoid truthiness 'or')
                raw_l_cgst = item.get("cgst_amount") if item.get("cgst_amount") is not None else item.get("cgst")
                raw_l_sgst = item.get("sgst_amount") if item.get("sgst_amount") is not None else item.get("sgst")
                raw_l_igst = item.get("igst_amount") if item.get("igst_amount") is not None else item.get("igst")
                l_cgst_amt = parse_clean_numeric(raw_l_cgst) if raw_l_cgst is not None else None
                l_sgst_amt = parse_clean_numeric(raw_l_sgst) if raw_l_sgst is not None else None
                l_igst_amt = parse_clean_numeric(raw_l_igst) if raw_l_igst is not None else None
                
                # Line-level Cess extraction supporting all standard aliases
                l_cess_candidates: List[float] = []
                for cess_k in [
                    "cess_amount",
                    "cess",
                    "cess_total",
                    "total_cess",
                    "compensation_cess",
                    "compensation_cess_amount",
                    "compensation cess",
                    "comp_cess",
                ]:
                    if item.get(cess_k) is not None:
                        c_val = parse_clean_numeric(item[cess_k])
                        if c_val is not None and c_val not in l_cess_candidates:
                            l_cess_candidates.append(c_val)

                l_cess_amt: Optional[float] = None
                conflicting_line_cess_issue = False
                if l_cess_candidates:
                    # If multiple conflicting candidates exist, flag review
                    unique_cess = []
                    for v in l_cess_candidates:
                        if not any(abs(v - u) <= tol for u in unique_cess):
                            unique_cess.append(v)
                    if len(unique_cess) > 1:
                        conflicting_line_cess_issue = True
                        all_lines_valid = False
                        has_review = True
                        warnings.append(f"Line {idx} has conflicting Cess aliases: CONFLICTING_LINE_CESS_ALIASES")
                    l_cess_amt = l_cess_candidates[0]

                has_explicit_line_tax = any(x is not None for x in [l_cgst_amt, l_sgst_amt, l_igst_amt, l_cess_amt])
                line_tax_total: float = round(
                    (l_cgst_amt or 0.0) + (l_sgst_amt or 0.0) + (l_igst_amt or 0.0) + (l_cess_amt or 0.0), 2
                )

                # Step 3: Rate-derived line tax
                l_cgst_rate = parse_clean_numeric(item.get("cgst_rate"))
                l_sgst_rate = parse_clean_numeric(item.get("sgst_rate"))
                l_igst_rate = parse_clean_numeric(item.get("igst_rate"))
                l_cess_rate = parse_clean_numeric(item.get("cess_rate"))
                has_explicit_tax_rates = any(x is not None and x >= 0.0 for x in [l_cgst_rate, l_sgst_rate, l_igst_rate, l_cess_rate])

                disc_val, disc_type, disc_issue = parse_discount_semantics(item)
                l_disc = disc_val if disc_val is not None else 0.0

                l_check: Dict[str, Any] = {
                    "line_index": idx,
                    "description": desc,
                    "quantity": qty,
                    "unit_price": price,
                    "discount": l_disc,
                    "discount_type": disc_type,
                    "discount_amount": 0.0,
                    "extracted_taxable": ext_taxable,
                    "calculated_taxable": None,
                    "cgst_amount": l_cgst_amt,
                    "sgst_amount": l_sgst_amt,
                    "igst_amount": l_igst_amt,
                    "cess_amount": l_cess_amt,
                    "line_tax_total": line_tax_total if has_explicit_line_tax else None,
                    "extracted_total": ext_total,
                    "expected_total": None,
                    "difference": 0.0,
                    "total_difference": 0.0,
                    "status": "REVIEW_REQUIRED",
                }

                # Step 1: Establish taxable base (T_line)
                resolved_taxable: Optional[float] = None
                taxable_mismatch = False

                if disc_issue == "AMBIGUOUS_DISCOUNT_CLASSIFICATION":
                    all_lines_valid = False
                    has_review = True
                    l_check["status"] = "REVIEW_REQUIRED"
                    l_check["issue"] = "AMBIGUOUS_DISCOUNT_CLASSIFICATION"
                    l_check["note"] = f"Line {idx} discount value '{l_disc}' is ambiguous (AMBIGUOUS_DISCOUNT_CLASSIFICATION: cannot determine percentage vs amount). Manual review required."
                    warnings.append(f"Line {idx} discount classification ambiguous: AMBIGUOUS_DISCOUNT_CLASSIFICATION")
                    if ext_taxable is not None:
                        resolved_taxable = ext_taxable
                elif disc_issue == "INVALID_DISCOUNT_PERCENTAGE":
                    all_lines_valid = False
                    has_review = True
                    l_check["status"] = "REVIEW_REQUIRED"
                    l_check["issue"] = "INVALID_DISCOUNT_PERCENTAGE"
                    l_check["note"] = f"Line {idx} percentage discount '{l_disc}%' exceeds 100%. Invalid discount."
                    warnings.append(f"Line {idx} has invalid discount percentage: {l_disc}%")
                    if ext_taxable is not None:
                        resolved_taxable = ext_taxable
                elif disc_issue == "NEGATIVE_DISCOUNT":
                    all_lines_valid = False
                    has_review = True
                    l_check["status"] = "REVIEW_REQUIRED"
                    l_check["issue"] = "NEGATIVE_DISCOUNT"
                    l_check["note"] = f"Line {idx} has negative discount '{l_disc}', which cannot be processed automatically."
                    warnings.append(f"Line {idx} has negative discount: {l_disc}")
                    if ext_taxable is not None:
                        resolved_taxable = ext_taxable
                elif qty is not None and price is not None:
                    gross = round(qty * price, 2)
                    calc_line_grosses.append(gross)
                    if disc_type == "percentage":
                        disc_amount = round(gross * l_disc / 100.0, 2)
                    else:
                        disc_amount = round(l_disc, 2)
                    calc_line_discounts.append(disc_amount)

                    calc_taxable = round(gross - disc_amount, 2)
                    l_check["discount_amount"] = disc_amount
                    l_check["calculated_taxable"] = calc_taxable

                    if ext_taxable is not None:
                        t_diff = round(abs(ext_taxable - calc_taxable), 2)
                        l_check["difference"] = t_diff
                        if t_diff <= tol:
                            resolved_taxable = calc_taxable
                        else:
                            taxable_mismatch = True
                            all_lines_valid = False
                            has_mismatch = True
                            disc_repr = f"{l_disc}%" if disc_type == "percentage" else f"₹{disc_amount:,.2f}"
                            errors.append(f"Line {idx} math mismatch: {qty} × ₹{price:,.2f} - {disc_repr} = ₹{calc_taxable:,.2f}, but extracted amount is ₹{ext_taxable:,.2f} (diff: ₹{t_diff:,.2f}).")
                            resolved_taxable = ext_taxable
                    else:
                        resolved_taxable = calc_taxable
                elif ext_taxable is not None:
                    resolved_taxable = ext_taxable
                    l_check["calculated_taxable"] = ext_taxable
                    l_check["note"] = "Quantity or unit price not provided; used extracted taxable amount."
                else:
                    all_lines_valid = False
                    has_review = True
                    l_check["status"] = "REVIEW_REQUIRED"
                    l_check["note"] = "Insufficient pricing details to establish taxable base."
                    warnings.append(f"Line {idx} has insufficient pricing details to verify taxable amount.")

                if resolved_taxable is not None:
                    calc_line_taxables.append(resolved_taxable)

                # If taxable math already mismatched or has discount issue, skip line total evaluation
                if taxable_mismatch:
                    l_check["status"] = "MISMATCH"
                    line_item_checks.append(l_check)
                    continue
                if l_check["status"] == "REVIEW_REQUIRED" and l_check.get("issue") in [
                    "AMBIGUOUS_DISCOUNT_CLASSIFICATION", "INVALID_DISCOUNT_PERCENTAGE", "NEGATIVE_DISCOUNT"
                ]:
                    line_item_checks.append(l_check)
                    continue
                if resolved_taxable is None:
                    line_item_checks.append(l_check)
                    continue

                # Step 4 & 5 conflict / ambiguity checks
                if conflicting_totals:
                    all_lines_valid = False
                    has_review = True
                    l_check["status"] = "REVIEW_REQUIRED"
                    l_check["issue"] = "CONFLICTING_LINE_TOTAL_ALIASES"
                    l_check["note"] = f"Line {idx} has conflicting line total aliases ({explicit_total_aliases})."
                    warnings.append(f"Line {idx} has conflicting line total aliases: CONFLICTING_LINE_TOTAL_ALIASES")
                    line_item_checks.append(l_check)
                    continue

                if conflicting_line_cess_issue:
                    all_lines_valid = False
                    has_review = True
                    l_check["status"] = "REVIEW_REQUIRED"
                    l_check["issue"] = "CONFLICTING_LINE_CESS_ALIASES"
                    l_check["note"] = f"Line {idx} has conflicting Cess aliases with different values."
                    line_item_checks.append(l_check)
                    continue

                if ambiguous_amount_issue == "CONFLICTING_LINE_TOTAL_ALIASES":
                    all_lines_valid = False
                    has_review = True
                    l_check["status"] = "REVIEW_REQUIRED"
                    l_check["issue"] = "CONFLICTING_LINE_TOTAL_ALIASES"
                    l_check["note"] = f"Line {idx} amount field (₹{raw_amount_val:,.2f}) conflicts with line total (₹{ext_total:,.2f})."
                    warnings.append(f"Line {idx} amount conflicts with total: CONFLICTING_LINE_TOTAL_ALIASES")
                    line_item_checks.append(l_check)
                    continue
                elif ambiguous_amount_issue == "AMBIGUOUS_AMOUNT_FIELD":
                    all_lines_valid = False
                    has_review = True
                    l_check["status"] = "REVIEW_REQUIRED"
                    l_check["issue"] = "AMBIGUOUS_AMOUNT_FIELD"
                    l_check["note"] = f"Line {idx} has ambiguous 'amount' column (₹{raw_amount_val:,.2f}) without separate pre-tax/post-tax specification."
                    warnings.append(f"Line {idx} has ambiguous amount field: AMBIGUOUS_AMOUNT_FIELD")
                    line_item_checks.append(l_check)
                    continue

                # Step 7: Tax rate vs Tax amount consistency check
                tax_rate_amount_conflict = False
                if has_explicit_line_tax and has_explicit_tax_rates:
                    for comp_name, r_val, a_val in [
                        ("CGST", l_cgst_rate, l_cgst_amt),
                        ("SGST", l_sgst_rate, l_sgst_amt),
                        ("IGST", l_igst_rate, l_igst_amt),
                        ("CESS", l_cess_rate, l_cess_amt),
                    ]:
                        if r_val is not None and a_val is not None and resolved_taxable >= 0:
                            exp_comp_tax = round(resolved_taxable * r_val / 100.0, 2)
                            if abs(exp_comp_tax - a_val) > tol:
                                tax_rate_amount_conflict = True
                                all_lines_valid = False
                                has_review = True
                                l_check["status"] = "REVIEW_REQUIRED"
                                l_check["issue"] = "TAX_RATE_AMOUNT_CONFLICT"
                                l_check["note"] = f"Line {idx} {comp_name} rate ({r_val}%) implies ₹{exp_comp_tax:,.2f} tax, but extracted amount is ₹{a_val:,.2f}."
                                warnings.append(f"Line {idx} has tax rate vs amount conflict for {comp_name}: TAX_RATE_AMOUNT_CONFLICT")
                                break

                if tax_rate_amount_conflict:
                    line_item_checks.append(l_check)
                    continue

                # Step 3: Derive expected line tax from rates if explicit amounts absent
                effective_line_tax = line_tax_total
                if not has_explicit_line_tax and has_explicit_tax_rates:
                    derived_rates_sum = (l_cgst_rate or 0.0) + (l_sgst_rate or 0.0) + (l_igst_rate or 0.0) + (l_cess_rate or 0.0)
                    effective_line_tax = round(resolved_taxable * derived_rates_sum / 100.0, 2)
                    has_explicit_line_tax = True
                    l_check["line_tax_total"] = effective_line_tax
                    l_check["note"] = "Line tax derived from explicit tax rates."

                # Step 6: Line-Total Reconciliation State Machine
                if ext_total is None:
                    # CASE A: Line total is omitted on invoice
                    expected_tot = round(resolved_taxable + (effective_line_tax if has_explicit_line_tax else 0.0), 2)
                    l_check["expected_total"] = expected_tot
                    l_check["line_total_treatment"] = "LINE_TOTAL_OMITTED_CALCULATED"
                    l_check["status"] = "PASSED"
                elif has_explicit_line_tax:
                    # CASE B: Line taxes are available
                    expected_tot = round(resolved_taxable + effective_line_tax, 2)
                    l_check["expected_total"] = expected_tot
                    tot_diff = round(abs(ext_total - expected_tot), 2)
                    l_check["total_difference"] = tot_diff
                    if tot_diff <= tol:
                        l_check["status"] = "PASSED"
                        l_check["line_total_treatment"] = "EXPLICIT_LINE_TAXES_MATCH"
                    else:
                        l_check["status"] = "MISMATCH"
                        all_lines_valid = False
                        has_mismatch = True
                        l_check["line_total_treatment"] = "EXPLICIT_LINE_TOTAL_MISMATCH"
                        errors.append(
                            f"Line {idx} total mismatch: Taxable ₹{resolved_taxable:,.2f} + Taxes ₹{effective_line_tax:,.2f} = ₹{expected_tot:,.2f}, but line total is ₹{ext_total:,.2f} (diff: ₹{tot_diff:,.2f})."
                        )
                elif hdr_tax_total_val == 0.0:
                    # CASE C: No line tax AND header tax is zero
                    expected_tot = resolved_taxable
                    l_check["expected_total"] = expected_tot
                    tot_diff = round(abs(ext_total - expected_tot), 2)
                    l_check["total_difference"] = tot_diff
                    if tot_diff <= tol:
                        l_check["status"] = "PASSED"
                        l_check["line_total_treatment"] = "ZERO_TAX_LINE_MATCH"
                    else:
                        l_check["status"] = "MISMATCH"
                        all_lines_valid = False
                        has_mismatch = True
                        l_check["line_total_treatment"] = "ZERO_TAX_LINE_MISMATCH"
                        errors.append(
                            f"Line {idx} total mismatch on zero-tax invoice: Expected ₹{expected_tot:,.2f}, but line total is ₹{ext_total:,.2f} (diff: ₹{tot_diff:,.2f})."
                        )
                else:
                    # CASE D: No line tax BUT header tax exists (> 0)
                    expected_tot = resolved_taxable
                    l_check["expected_total"] = expected_tot
                    all_lines_valid = False
                    has_review = True
                    l_check["status"] = "REVIEW_REQUIRED"
                    l_check["issue"] = "UNALLOCATED_HEADER_TAX"
                    l_check["note"] = f"Line {idx} total (₹{ext_total:,.2f}) cannot be verified without line-level tax breakdown when invoice header has tax (₹{hdr_tax_total_val:,.2f}): UNALLOCATED_HEADER_TAX."
                    warnings.append(f"Line {idx} has unallocated header tax: UNALLOCATED_HEADER_TAX")

                total_items_count += 1
                if has_explicit_line_tax:
                    lines_with_tax_count += 1
                    # Use explicit amount or rate-derived component
                    actual_l_cgst = l_cgst_amt if l_cgst_amt is not None else (round(resolved_taxable * l_cgst_rate / 100.0, 2) if l_cgst_rate else None)
                    actual_l_sgst = l_sgst_amt if l_sgst_amt is not None else (round(resolved_taxable * l_sgst_rate / 100.0, 2) if l_sgst_rate else None)
                    actual_l_igst = l_igst_amt if l_igst_amt is not None else (round(resolved_taxable * l_igst_rate / 100.0, 2) if l_igst_rate else None)
                    actual_l_cess = l_cess_amt if l_cess_amt is not None else (round(resolved_taxable * l_cess_rate / 100.0, 2) if l_cess_rate else None)

                    if actual_l_cgst is not None:
                        calc_line_cgsts.append(actual_l_cgst)
                    if actual_l_sgst is not None:
                        calc_line_sgsts.append(actual_l_sgst)
                    if actual_l_igst is not None:
                        calc_line_igsts.append(actual_l_igst)
                    if actual_l_cess is not None:
                        calc_line_cesses.append(actual_l_cess)
                    calc_line_taxes.append(effective_line_tax)

                line_item_checks.append(l_check)

        line_math_status = "PASSED" if (line_item_checks and all_lines_valid) else ("MISMATCH" if has_mismatch else ("NOT_APPLICABLE" if not raw_line_items else "REVIEW_REQUIRED"))
        checks.append({
            "name": "line_item_math",
            "type": "LINE_TOTAL",
            "description": "Per-line arithmetic verification (quantity × unit_price - discount = taxable, and taxable + line taxes = line total)",
            "status": line_math_status,
            "total_lines_checked": len(line_item_checks),
            "line_breakdowns": line_item_checks,
        })

        # -------------------------------------------------------------
        # CHECK 2: Line Item Sum vs Subtotal
        # -------------------------------------------------------------
        calculated_subtotal: Optional[float] = None
        g_lines_sum = round(sum(calc_line_grosses), 2) if calc_line_grosses else None
        d_lines_sum = round(sum(calc_line_discounts), 2) if calc_line_discounts else 0.0
        t_lines_sum = round(sum(calc_line_taxables), 2) if calc_line_taxables else None

        # Determine whether subtotal represents gross or net taxable
        is_subtotal_gross = False
        if src_subtotal is not None and g_lines_sum is not None and t_lines_sum is not None:
            if abs(src_subtotal - g_lines_sum) <= tol and abs(src_subtotal - t_lines_sum) > tol:
                is_subtotal_gross = True

        if is_subtotal_gross:
            calculated_subtotal = g_lines_sum
        elif t_lines_sum is not None:
            calculated_subtotal = t_lines_sum

        if calculated_subtotal is not None and src_subtotal is not None:
            subtotal_diff = round(abs(src_subtotal - calculated_subtotal), 2)
            if subtotal_diff <= tol:
                sub_status = "PASSED"
            else:
                sub_status = "MISMATCH"
                all_lines_valid = False
                has_mismatch = True
                errors.append(f"Subtotal mismatch: Sum of line items is ₹{calculated_subtotal:,.2f}, but extracted subtotal is ₹{src_subtotal:,.2f} (diff: ₹{subtotal_diff:,.2f}).")

            checks.append({
                "name": "line_item_sum_vs_subtotal",
                "type": "SUBTOTAL",
                "description": "Sum of line items vs extracted invoice subtotal",
                "status": sub_status,
                "source_value": src_subtotal,
                "calculated_value": calculated_subtotal,
                "difference": subtotal_diff,
            })
        elif src_subtotal is not None:
            checks.append({
                "name": "line_item_sum_vs_subtotal",
                "type": "SUBTOTAL",
                "description": "Sum of line items vs extracted invoice subtotal",
                "status": "PASSED" if not raw_line_items else "REVIEW_REQUIRED",
                "source_value": src_subtotal,
                "calculated_value": src_subtotal,
                "difference": 0.0,
                "note": "Subtotal verified directly from invoice header." if not raw_line_items else "Line items not available to aggregate subtotal.",
            })
            if raw_line_items:
                has_review = True
        else:
            checks.append({
                "name": "line_item_sum_vs_subtotal",
                "type": "SUBTOTAL",
                "description": "Sum of line items vs extracted invoice subtotal",
                "status": "NOT_VALIDATED",
                "source_value": None,
                "calculated_value": calculated_subtotal,
                "difference": 0.0,
                "note": "Extracted subtotal missing from invoice.",
            })
            has_review = True

        # -------------------------------------------------------------
        # CHECK 3: GST Components vs GST Total
        # -------------------------------------------------------------
        has_gst_components = (src_cgst is not None or src_sgst is not None or src_igst is not None or src_cess is not None)
        calculated_gst_total: Optional[float] = None

        if has_gst_components:
            calculated_gst_total = round((src_cgst or 0.0) + (src_sgst or 0.0) + (src_igst or 0.0) + (src_cess or 0.0), 2)

        if calculated_gst_total is not None and src_tax_total is not None:
            gst_diff = round(abs(src_tax_total - calculated_gst_total), 2)
            if gst_diff <= tol:
                gst_status = "PASSED"
            else:
                gst_status = "MISMATCH"
                has_mismatch = True
                errors.append(f"GST components sum (₹{calculated_gst_total:,.2f}) does not match extracted Tax Total (₹{src_tax_total:,.2f}) (diff: ₹{gst_diff:,.2f}).")

            checks.append({
                "name": "gst_components_vs_gst_total",
                "type": "TAX",
                "description": "Sum of GST components (CGST + SGST + IGST + Cess) vs extracted Tax Total",
                "status": gst_status,
                "source_value": src_tax_total,
                "calculated_value": calculated_gst_total,
                "difference": gst_diff,
            })
        elif calculated_gst_total is not None:
            checks.append({
                "name": "gst_components_vs_gst_total",
                "type": "TAX",
                "description": "Sum of GST components (CGST + SGST + IGST + Cess) vs extracted Tax Total",
                "status": "PASSED",
                "source_value": calculated_gst_total,
                "calculated_value": calculated_gst_total,
                "difference": 0.0,
                "note": "GST components sum established from individual taxes.",
            })
        elif src_tax_total is not None:
            calculated_gst_total = src_tax_total
            checks.append({
                "name": "gst_components_vs_gst_total",
                "type": "TAX",
                "description": "Sum of GST components (CGST + SGST + IGST + Cess) vs extracted Tax Total",
                "status": "REVIEW_REQUIRED",
                "source_value": src_tax_total,
                "calculated_value": None,
                "difference": 0.0,
                "note": "Individual CGST/SGST/IGST breakdown missing; used extracted Tax Total.",
            })
            warnings.append("Individual GST tax components (CGST/SGST/IGST) not explicitly broken down.")
        elif calc_line_taxes and lines_with_tax_count > 0:
            calculated_gst_total = round(sum(calc_line_taxes), 2)
            checks.append({
                "name": "gst_components_vs_gst_total",
                "type": "TAX",
                "description": "Sum of GST components (CGST + SGST + IGST + Cess) vs extracted Tax Total",
                "status": "PASSED",
                "source_value": calculated_gst_total,
                "calculated_value": calculated_gst_total,
                "difference": 0.0,
                "note": "GST tax established from line-level taxes (header tax omitted).",
            })
        else:
            checks.append({
                "name": "gst_components_vs_gst_total",
                "type": "TAX",
                "description": "Sum of GST components (CGST + SGST + IGST + Cess) vs extracted Tax Total",
                "status": "NOT_VALIDATED",
                "source_value": None,
                "calculated_value": None,
                "difference": 0.0,
                "note": "No GST amounts found on invoice.",
            })

        # -------------------------------------------------------------
        # CHECK 3B: Header GST vs Line GST Reconciliation
        # Reconciles line-level tax component sums against header tax values
        # -------------------------------------------------------------
        # Decision Matrix:
        # A. Full Header + Line available: reconcile components & total -> MISMATCH if diff > tol
        # B. Header only (lines_with_tax_count == 0): do not force line taxes -> PASS/NOT_APPLICABLE
        # C. Line only (header taxes missing): allow line taxes -> PASS
        # D. Partial Line Breakdown (0 < lines_with_tax_count < total_items_count and hdr tax > 0): REVIEW_REQUIRED
        if lines_with_tax_count > 0 and lines_with_tax_count < total_items_count and (src_tax_total is not None and src_tax_total > 0.0 or has_gst_components):
            all_lines_valid = False
            has_review = True
            checks.append({
                "name": "header_gst_vs_line_gst_reconciliation",
                "description": "Reconciliation of line-level GST components vs header tax components",
                "status": "REVIEW_REQUIRED",
                "issue": "PARTIAL_LINE_TAX_BREAKDOWN",
                "note": f"Only {lines_with_tax_count} of {total_items_count} lines have explicit tax breakdown while header specifies tax: PARTIAL_LINE_TAX_BREAKDOWN.",
            })
            warnings.append("Partial line-level GST breakdown: PARTIAL_LINE_TAX_BREAKDOWN")
        elif lines_with_tax_count > 0:
            # Lines have explicit taxes
            line_cgst_sum = round(sum(calc_line_cgsts), 2) if calc_line_cgsts else None
            line_sgst_sum = round(sum(calc_line_sgsts), 2) if calc_line_sgsts else None
            line_igst_sum = round(sum(calc_line_igsts), 2) if calc_line_igsts else None
            line_cess_sum = round(sum(calc_line_cesses), 2) if calc_line_cesses else None
            total_line_taxes_sum = round(sum(calc_line_taxes), 2)

            recon_mismatches: List[str] = []
            recon_details: Dict[str, Any] = {
                "line_cgst_sum": line_cgst_sum,
                "line_sgst_sum": line_sgst_sum,
                "line_igst_sum": line_igst_sum,
                "line_cess_sum": line_cess_sum,
                "total_line_taxes_sum": total_line_taxes_sum,
                "header_cgst": src_cgst,
                "header_sgst": src_sgst,
                "header_igst": src_igst,
                "header_cess": src_cess,
                "header_tax_total": src_tax_total,
            }

            # 1. Component: CGST
            if src_cgst is not None and (line_cgst_sum is not None or has_explicit_line_tax):
                c_sum = line_cgst_sum if line_cgst_sum is not None else 0.0
                diff_cgst = round(abs(src_cgst - c_sum), 2)
                if diff_cgst > tol:
                    recon_mismatches.append(f"HEADER_LINE_CGST_MISMATCH (Header: ₹{src_cgst:,.2f}, Lines: ₹{c_sum:,.2f}, diff: ₹{diff_cgst:,.2f})")
            
            # 2. Component: SGST
            if src_sgst is not None and (line_sgst_sum is not None or has_explicit_line_tax):
                s_sum = line_sgst_sum if line_sgst_sum is not None else 0.0
                diff_sgst = round(abs(src_sgst - s_sum), 2)
                if diff_sgst > tol:
                    recon_mismatches.append(f"HEADER_LINE_SGST_MISMATCH (Header: ₹{src_sgst:,.2f}, Lines: ₹{s_sum:,.2f}, diff: ₹{diff_sgst:,.2f})")

            # 3. Component: IGST
            if src_igst is not None and (line_igst_sum is not None or has_explicit_line_tax):
                i_sum = line_igst_sum if line_igst_sum is not None else 0.0
                diff_igst = round(abs(src_igst - i_sum), 2)
                if diff_igst > tol:
                    recon_mismatches.append(f"HEADER_LINE_IGST_MISMATCH (Header: ₹{src_igst:,.2f}, Lines: ₹{i_sum:,.2f}, diff: ₹{diff_igst:,.2f})")

            # 4. Component: Cess
            if src_cess is not None and (line_cess_sum is not None or has_explicit_line_tax):
                ce_sum = line_cess_sum if line_cess_sum is not None else 0.0
                diff_cess = round(abs(src_cess - ce_sum), 2)
                if diff_cess > tol:
                    recon_mismatches.append(f"HEADER_LINE_CESS_MISMATCH (Header: ₹{src_cess:,.2f}, Lines: ₹{ce_sum:,.2f}, diff: ₹{diff_cess:,.2f})")

            # 5. Total Tax: Header tax_total vs total_line_taxes_sum
            if src_tax_total is not None and lines_with_tax_count == total_items_count:
                diff_tot_tax = round(abs(src_tax_total - total_line_taxes_sum), 2)
                if diff_tot_tax > tol:
                    recon_mismatches.append(f"HEADER_LINE_TAX_TOTAL_MISMATCH (Header Tax Total: ₹{src_tax_total:,.2f}, Line Taxes Sum: ₹{total_line_taxes_sum:,.2f}, diff: ₹{diff_tot_tax:,.2f})")

            if recon_mismatches:
                has_mismatch = True
                for mm in recon_mismatches:
                    errors.append(f"Header vs Line GST mismatch: {mm}.")
                checks.append({
                    "name": "header_gst_vs_line_gst_reconciliation",
                    "type": "TAX",
                    "description": "Reconciliation of line-level GST components vs header tax components",
                    "status": "MISMATCH",
                    "difference": max(diff_cgst if 'diff_cgst' in locals() else 0.0, diff_sgst if 'diff_sgst' in locals() else 0.0, diff_tot_tax if 'diff_tot_tax' in locals() else 0.0),
                    "details": recon_details,
                    "mismatches": recon_mismatches,
                })
            else:
                checks.append({
                    "name": "header_gst_vs_line_gst_reconciliation",
                    "type": "TAX",
                    "description": "Reconciliation of line-level GST components vs header tax components",
                    "status": "PASSED",
                    "details": recon_details,
                    "note": "Line-level tax components agree with header tax components within tolerance.",
                })
        else:
            # Header only or zero tax lines -> valid, do not force line taxes
            checks.append({
                "name": "header_gst_vs_line_gst_reconciliation",
                "type": "TAX",
                "description": "Reconciliation of line-level GST components vs header tax components",
                "status": "PASSED" if (not raw_line_items or hdr_tax_total_val == 0.0) else "NOT_APPLICABLE",
                "note": "Header tax summary present without explicit line taxes or zero tax invoice." if (raw_line_items and hdr_tax_total_val == 0.0) else ("Header tax summary present without explicit line taxes." if raw_line_items else "No line items to reconcile."),
            })

        # -------------------------------------------------------------
        # CHECK 4: Grand Total Equation with Deterministic Discount Reconciliation
        # -------------------------------------------------------------
        effective_tax = calculated_gst_total if calculated_gst_total is not None else (src_tax_total or 0.0)
        round_off_val = src_round_off if src_round_off is not None else 0.0
        charges_val = src_shipping + src_other + src_adjustment + round_off_val

        # Variables for reconciliation
        d_header = src_discount
        has_line_discounts = (d_lines_sum > 0.0)
        has_header_discount = (d_header > 0.0)
        is_subtotal_missing = (src_subtotal is None)

        calculated_grand_total: Optional[float] = None
        discount_treatment: str = "STANDARD"
        discount_reconcile_issue: Optional[str] = None

        if is_subtotal_missing and has_line_discounts and has_header_discount:
            # CASE 6: MISSING SUBTOTAL WITH BOTH LINE & HEADER DISCOUNTS
            # Cannot determine whether subtotal was gross or net -> AMBIGUOUS
            discount_reconcile_issue = "AMBIGUOUS_HEADER_DISCOUNT_RECONCILIATION"
            has_review = True
            warnings.append("Missing subtotal with concurrent line and header discounts: AMBIGUOUS_HEADER_DISCOUNT_RECONCILIATION")
            # Baseline expected if subtotal was net
            if t_lines_sum is not None:
                calculated_grand_total = round(t_lines_sum + effective_tax + charges_val, 2)
        elif not has_line_discounts:
            # CASE 1: NO LINE DISCOUNT -> Header discount is sole deduction from subtotal
            eff_sub = calculated_subtotal if calculated_subtotal is not None else src_subtotal
            if eff_sub is not None:
                calculated_grand_total = round(eff_sub - d_header + effective_tax + charges_val, 2)
                discount_treatment = "SOLE_HEADER_DISCOUNT"
        elif not has_header_discount:
            # Standard: Line discounts only, no header discount
            eff_sub = calculated_subtotal if calculated_subtotal is not None else src_subtotal
            if eff_sub is not None:
                calculated_grand_total = round(eff_sub + effective_tax + charges_val, 2)
                discount_treatment = "LINE_DISCOUNTS_ONLY"
        else:
            # BOTH LINE DISCOUNTS AND HEADER DISCOUNT PRESENT (D_lines > 0 and D_header > 0)
            t_base = t_lines_sum if t_lines_sum is not None else (src_subtotal or 0.0)
            g_base = g_lines_sum if g_lines_sum is not None else (src_subtotal or 0.0)

            cand_total_summary = round(t_base + effective_tax + charges_val, 2)
            cand_total_additional = round(t_base - d_header + effective_tax + charges_val, 2)
            cand_total_gross = round(g_base - d_header + effective_tax + charges_val, 2)

            match_summary = (src_total_amount is not None and abs(src_total_amount - cand_total_summary) <= tol)
            match_additional = (src_total_amount is not None and abs(src_total_amount - cand_total_additional) <= tol)
            match_gross = (src_total_amount is not None and abs(src_total_amount - cand_total_gross) <= tol)

            # Check CASE 5: Dual-hypothesis match / small discount collision (D_header <= 1.0)
            if match_summary and match_additional:
                discount_reconcile_issue = "AMBIGUOUS_HEADER_DISCOUNT_RECONCILIATION"
                has_review = True
                calculated_grand_total = cand_total_summary
                warnings.append("Header discount reconciliation ambiguous (both summary and additional hypotheses match within tolerance): AMBIGUOUS_HEADER_DISCOUNT_RECONCILIATION")
            elif is_subtotal_gross and abs(d_header - d_lines_sum) <= tol and match_gross:
                # CASE 3: GROSS / PRE-DISCOUNT SUBTOTAL
                calculated_grand_total = cand_total_gross
                discount_treatment = "GROSS_SUBTOTAL_HEADER_DEDUCTION"
            elif abs(d_header - d_lines_sum) <= tol:
                # D_header == D_lines
                if match_summary and not match_additional:
                    # CASE 2: LINE DISCOUNTS + SUMMARY HEADER DISCOUNT
                    calculated_grand_total = cand_total_summary
                    discount_treatment = "SUMMARY_HEADER_DISCOUNT"
                elif match_additional:
                    # CASE 7: D_header == D_lines but printed total shows a second deduction
                    # Fundamentally ambiguous: duplicate summary deduction vs legitimate identical second discount
                    discount_reconcile_issue = "AMBIGUOUS_HEADER_DISCOUNT_RECONCILIATION"
                    has_review = True
                    calculated_grand_total = cand_total_additional
                    warnings.append("Header discount equals line discount sum but grand total shows second deduction: AMBIGUOUS_HEADER_DISCOUNT_RECONCILIATION")
                else:
                    # Neither matched
                    calculated_grand_total = cand_total_summary
            elif abs(d_header - d_lines_sum) > tol:
                # D_header != D_lines
                if match_additional and not match_summary:
                    # CASE 4: ADDITIONAL HEADER DISCOUNT
                    calculated_grand_total = cand_total_additional
                    discount_treatment = "ADDITIONAL_HEADER_DISCOUNT"
                else:
                    # CASE 8: Header discount conflict / neither corroborated
                    discount_reconcile_issue = "AMBIGUOUS_HEADER_DISCOUNT_RECONCILIATION"
                    has_review = True
                    calculated_grand_total = cand_total_additional
                    warnings.append(f"Header discount (₹{d_header:,.2f}) conflicts with line discount sum (₹{d_lines_sum:,.2f}) and lacks sufficient corroboration: AMBIGUOUS_HEADER_DISCOUNT_RECONCILIATION")

        # Fallback if calculated_grand_total is still None
        if calculated_grand_total is None:
            eff_sub = calculated_subtotal if calculated_subtotal is not None else src_subtotal
            if eff_sub is not None:
                calculated_grand_total = round(eff_sub - d_header + effective_tax + charges_val, 2)

        if calculated_grand_total is not None and src_total_amount is not None:
            total_diff = round(abs(src_total_amount - calculated_grand_total), 2)
            if discount_reconcile_issue:
                total_status = "REVIEW_REQUIRED"
                check_note = f"Discount reconciliation requires manual review: {discount_reconcile_issue}."
            elif total_diff <= tol:
                total_status = "PASSED"
                check_note = f"Grand total matched with discount treatment: {discount_treatment}."
            else:
                total_status = "MISMATCH"
                has_mismatch = True
                check_note = None
                errors.append(f"Grand Total mismatch: Expected ₹{calculated_grand_total:,.2f} (Treatment: {discount_treatment}), but extracted total is ₹{src_total_amount:,.2f} (diff: ₹{total_diff:,.2f}).")

            check_entry: Dict[str, Any] = {
                "name": "extracted_total_vs_calculated_total",
                "type": "GRAND_TOTAL",
                "field": "total_amount",
                "status": total_status,
                "invoice_value": src_total_amount,
                "source_value": src_total_amount,
                "calculated_value": calculated_grand_total,
                "difference": total_diff,
                "discount_treatment": discount_treatment,
                "message": check_note or f"Grand total mismatch: Extracted ₹{src_total_amount:,.2f}, Calculated ₹{calculated_grand_total:,.2f} (diff: ₹{total_diff:,.2f}).",
            }
            if check_note:
                check_entry["note"] = check_note
            if discount_reconcile_issue:
                check_entry["issue"] = discount_reconcile_issue
            checks.append(check_entry)
        elif src_total_amount is not None:
            checks.append({
                "name": "extracted_total_vs_calculated_total",
                "type": "GRAND_TOTAL",
                "field": "total_amount",
                "status": "NOT_VALIDATED",
                "invoice_value": src_total_amount,
                "source_value": src_total_amount,
                "calculated_value": calculated_grand_total,
                "difference": 0.0,
                "message": "Subtotal or tax components missing to compute expected Grand Total.",
                "note": "Subtotal or tax components missing to compute expected Grand Total.",
            })
            has_review = True
        else:
            checks.append({
                "name": "extracted_total_vs_calculated_total",
                "type": "GRAND_TOTAL",
                "field": "total_amount",
                "status": "NOT_VALIDATED",
                "invoice_value": None,
                "source_value": None,
                "calculated_value": calculated_grand_total,
                "difference": 0.0,
                "message": "Extracted total amount is missing.",
                "note": "Extracted Grand Total missing from invoice.",
            })
            has_review = True

        # -------------------------------------------------------------
        # CHECK 5: Round-Off Consistency
        # -------------------------------------------------------------
        if src_round_off is not None and calculated_grand_total is not None and src_total_amount is not None:
            unrounded_total = round(calculated_grand_total - round_off_val, 2)
            expected_rounded = round(unrounded_total + src_round_off, 2)
            ro_diff = round(abs(expected_rounded - src_total_amount), 2)
            if ro_diff <= tol:
                ro_status = "PASSED"
            else:
                ro_status = "MISMATCH"
                has_mismatch = True
                errors.append(f"Round off mismatch: Unrounded total ₹{unrounded_total:,.2f} + Round-off ₹{src_round_off:,.2f} = ₹{expected_rounded:,.2f}, but total is ₹{src_total_amount:,.2f}.")

            checks.append({
                "name": "round_off_consistency",
                "description": "Verification of round-off adjustment consistency",
                "status": ro_status,
                "source_value": src_round_off,
                "calculated_value": round(src_total_amount - unrounded_total, 2),
                "difference": ro_diff,
            })

        # -------------------------------------------------------------
        # CHECK 6: Conflicting Header Numeric Aliases
        # -------------------------------------------------------------
        if conflicting_header_issues:
            has_review = True
            for ci in conflicting_header_issues:
                warnings.append(f"Conflicting header aliases detected: {ci}")
            checks.append({
                "name": "conflicting_header_aliases",
                "description": "Verification that duplicate header numeric aliases are consistent",
                "status": "REVIEW_REQUIRED",
                "issues": conflicting_header_issues,
                "note": "Multiple header aliases found with conflicting values beyond tolerance.",
            })

        # -------------------------------------------------------------
        # CHECK 7: Upstream GST Engine Validation Linkage
        # -------------------------------------------------------------
        if gst_result and isinstance(gst_result, dict):
            gst_v_status = gst_result.get("validation_status")
            gst_errs = gst_result.get("errors") or []
            gst_warns = gst_result.get("warnings") or []

            if gst_v_status == "GST_MISMATCH":
                has_mismatch = True
                for ge in gst_errs:
                    if ge not in errors:
                        errors.append(f"GST Engine error: {ge}")
                checks.append({
                    "name": "gst_engine_linkage",
                    "description": "Integration of upstream Stage 4 GST Engine validation status",
                    "status": "MISMATCH",
                    "gst_validation_status": gst_v_status,
                    "errors": gst_errs,
                })
            elif gst_v_status == "REVIEW_REQUIRED":
                has_review = True
                for gw in gst_warns:
                    if gw not in warnings:
                        warnings.append(f"GST Engine warning: {gw}")
                checks.append({
                    "name": "gst_engine_linkage",
                    "description": "Integration of upstream Stage 4 GST Engine validation status",
                    "status": "REVIEW_REQUIRED",
                    "gst_validation_status": gst_v_status,
                    "warnings": gst_warns,
                })

        # -------------------------------------------------------------
        # Overall Status (Legacy Contract Preservation) & New validation_status
        # -------------------------------------------------------------
        if has_mismatch:
            overall_status = "MISMATCH"
        elif has_review or src_total_amount is None:
            overall_status = "REVIEW_REQUIRED"
        else:
            overall_status = "PASSED"

        # Derive new structured validation_status:
        # - MISMATCH if any mathematical check failed
        # - PARTIAL if some checks passed but others were NOT_VALIDATED or missing fields
        # - VALID if all applicable checks passed
        # - NOT_VALIDATED if insufficient data existed
        mismatch_checks = [c for c in checks if c.get("status") in ("MISMATCH", "FAILED")]
        passed_checks = [c for c in checks if c.get("status") in ("PASSED", "MATCH")]
        not_val_checks = [c for c in checks if c.get("status") in ("NOT_VALIDATED", "REVIEW_REQUIRED")]

        if mismatch_checks:
            validation_status = "MISMATCH"
        elif passed_checks and not_val_checks:
            validation_status = "PARTIAL"
        elif passed_checks and not mismatch_checks:
            validation_status = "VALID"
        else:
            validation_status = "NOT_VALIDATED"

        # Construct differences dictionary
        differences: Dict[str, Any] = {}
        if calculated_subtotal is not None and src_subtotal is not None:
            differences["subtotal"] = round(src_subtotal - calculated_subtotal, 2)
        if calculated_gst_total is not None and src_tax_total is not None:
            differences["tax_total"] = round(src_tax_total - calculated_gst_total, 2)
        if calculated_grand_total is not None and src_total_amount is not None:
            differences["total_amount"] = round(src_total_amount - calculated_grand_total, 2)

        return {
            "overall_status": overall_status,
            "validation_status": validation_status,
            "tolerance": tol,
            "source": {
                "subtotal": src_subtotal,
                "cgst_amount": src_cgst,
                "sgst_amount": src_sgst,
                "igst_amount": src_igst,
                "cess_amount": src_cess,
                "tax_total": src_tax_total,
                "discount_total": src_discount,
                "shipping_charges": src_shipping,
                "other_charges": src_other,
                "round_off": src_round_off,
                "total_amount": src_total_amount,
            },
            "calculated": {
                "subtotal": calculated_subtotal,
                "gst_total": calculated_gst_total,
                "grand_total": calculated_grand_total,
            },
            "differences": differences,
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
        }


# Singleton instance
financial_validator = FinancialValidator()
