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
    Returns None if missing or unparseable.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = re.sub(r"[^\d.\-]", "", val.strip())
        if not cleaned or cleaned == "-" or cleaned == ".":
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


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
        discount_total = float(data.get("discount_total") or data.get("discount") or 0.0)
        tax_total = float(data.get("tax_total") or data.get("total_tax") or 0.0)
        shipping = float(data.get("shipping_charges") or data.get("shipping") or 0.0)
        other_charges = float(data.get("other_charges") or data.get("additional_charges") or 0.0)
        round_off = float(data.get("round_off") or data.get("roundoff") or 0.0)
        total_amount = float(data.get("total_amount") or data.get("invoice_total") or 0.0)

        line_items = data.get("line_items") or []
        line_taxable_sum = 0.0
        line_tax_sum = 0.0
        line_total_sum = 0.0

        for idx, item in enumerate(line_items, 1):
            qty = float(item.get("quantity") or 1.0)
            unit_price = float(item.get("unit_price") or item.get("rate") or item.get("price") or 0.0)
            l_disc = float(item.get("discount") or item.get("line_discount") or item.get("discount_percent") or item.get("discount_rate") or 0.0)
            
            calc_flat = round((qty * unit_price) - l_disc, 2)
            calc_pct = round((qty * unit_price) * (1.0 - (l_disc / 100.0)), 2) if 0 <= l_disc <= 100 else calc_flat
            
            ext_taxable = item.get("taxable_amount")
            if ext_taxable is not None:
                ext_f = float(ext_taxable)
                if abs(ext_f - calc_pct) <= tolerance:
                    taxable = calc_pct
                elif abs(ext_f - calc_flat) <= tolerance:
                    taxable = calc_flat
                else:
                    taxable = ext_f
            else:
                taxable = calc_pct if (0 < l_disc <= 100) else calc_flat

            cgst = float(item.get("cgst_amount") or 0.0)
            sgst = float(item.get("sgst_amount") or 0.0)
            igst = float(item.get("igst_amount") or 0.0)
            item_total = float(item.get("total") or (taxable + cgst + sgst + igst))

            line_taxable_sum += taxable
            line_tax_sum += (cgst + sgst + igst)
            line_total_sum += item_total

        if line_items and subtotal > 0 and abs(line_taxable_sum - subtotal) > (len(line_items) * tolerance):
            errors.append(
                f"Line taxable sum (₹{line_taxable_sum:.2f}) does not match header subtotal (₹{subtotal:.2f})"
            )

        expected_grand_total_hdr = round(
            subtotal + tax_total - discount_total + shipping + other_charges + round_off, 2
        )
        expected_grand_total_line = round(
            subtotal + tax_total + shipping + other_charges + round_off, 2
        )

        expected_grand_total = expected_grand_total_hdr
        if total_amount > 0:
            diff_hdr = abs(expected_grand_total_hdr - total_amount)
            diff_line = abs(expected_grand_total_line - total_amount)
            if diff_line <= tolerance and (discount_total == 0.0 or diff_line <= diff_hdr):
                expected_grand_total = expected_grand_total_line
            elif diff_hdr <= tolerance:
                expected_grand_total = expected_grand_total_hdr
            else:
                expected_grand_total = expected_grand_total_line if diff_line < diff_hdr else expected_grand_total_hdr

            if abs(expected_grand_total - total_amount) > tolerance:
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

        src_subtotal = parse_clean_numeric(data_obj.get("subtotal"))
        src_discount = parse_clean_numeric(data_obj.get("discount_total") or data_obj.get("discount")) or 0.0
        src_shipping = parse_clean_numeric(data_obj.get("shipping_charges") or data_obj.get("shipping")) or 0.0
        src_other = parse_clean_numeric(data_obj.get("other_charges") or data_obj.get("additional_charges")) or 0.0
        src_round_off = parse_clean_numeric(data_obj.get("round_off") or data_obj.get("roundoff"))
        src_total_amount = parse_clean_numeric(data_obj.get("total_amount") or data_obj.get("invoice_total"))

        # Source tax values
        src_cgst = extract_tax_value(data_obj, "cgst")
        src_sgst = extract_tax_value(data_obj, "sgst")
        src_igst = extract_tax_value(data_obj, "igst")
        src_cess = extract_tax_value(data_obj, "cess")
        src_tax_total = parse_clean_numeric(data_obj.get("tax_total") or data_obj.get("total_tax"))

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
        # CHECK 1: Line Item Math (quantity * unit_price - discount = taxable)
        # -------------------------------------------------------------
        line_item_checks: List[Dict[str, Any]] = []
        calc_line_taxables: List[float] = []
        all_lines_valid = True

        if raw_line_items:
            for idx, item in enumerate(raw_line_items, 1):
                if not isinstance(item, dict):
                    continue

                desc = str(item.get("description") or f"Line {idx}")
                qty = parse_clean_numeric(item.get("quantity"))
                price = parse_clean_numeric(item.get("unit_price") or item.get("rate") or item.get("price"))
                l_disc = parse_clean_numeric(item.get("discount") or item.get("line_discount") or item.get("discount_percent") or item.get("discount_rate")) or 0.0
                ext_taxable = parse_clean_numeric(item.get("taxable_amount") or item.get("total") or item.get("amount"))

                l_check: Dict[str, Any] = {
                    "line_index": idx,
                    "description": desc,
                    "quantity": qty,
                    "unit_price": price,
                    "discount": l_disc,
                    "extracted_taxable": ext_taxable,
                    "calculated_taxable": None,
                    "difference": 0.0,
                    "status": "REVIEW_REQUIRED",
                }

                if qty is not None and price is not None:
                    # 1. Flat discount: (qty * price) - l_disc
                    calc_flat = round((qty * price) - l_disc, 2)
                    
                    # 2. Percentage discount: (qty * price) * (1 - l_disc / 100)
                    calc_pct = round((qty * price) * (1.0 - (l_disc / 100.0)), 2) if (0 <= l_disc <= 100) else calc_flat

                    calc_taxable = calc_flat
                    diff = round(abs(ext_taxable - calc_flat), 2) if ext_taxable is not None else 0.0
                    disc_type = "FLAT"

                    if ext_taxable is not None:
                        diff_flat = round(abs(ext_taxable - calc_flat), 2)
                        diff_pct = round(abs(ext_taxable - calc_pct), 2) if (0 <= l_disc <= 100) else 999999.0

                        if diff_pct <= tol:
                            calc_taxable = calc_pct
                            diff = diff_pct
                            disc_type = "PERCENTAGE"
                        elif diff_flat <= tol:
                            calc_taxable = calc_flat
                            diff = diff_flat
                            disc_type = "FLAT"
                        else:
                            if diff_pct < diff_flat and 0 <= l_disc <= 100:
                                calc_taxable = calc_pct
                                diff = diff_pct
                                disc_type = "PERCENTAGE"
                            else:
                                calc_taxable = calc_flat
                                diff = diff_flat
                                disc_type = "FLAT"

                        l_check["calculated_taxable"] = calc_taxable
                        l_check["difference"] = diff
                        l_check["discount_type"] = disc_type

                        if diff <= tol:
                            l_check["status"] = "PASSED"
                            calc_line_taxables.append(calc_taxable)
                        else:
                            l_check["status"] = "MISMATCH"
                            all_lines_valid = False
                            has_mismatch = True
                            disc_repr = f"{l_disc}%" if disc_type == "PERCENTAGE" else f"₹{l_disc:,.2f}"
                            errors.append(f"Line {idx} math mismatch: {qty} × ₹{price:,.2f} - discount ({disc_repr}) = ₹{calc_taxable:,.2f}, but extracted amount is ₹{ext_taxable:,.2f} (diff: ₹{diff:,.2f}).")
                            calc_line_taxables.append(ext_taxable)
                    else:
                        calc_taxable = calc_pct if (0 < l_disc <= 100) else calc_flat
                        l_check["calculated_taxable"] = calc_taxable
                        l_check["status"] = "PASSED"
                        calc_line_taxables.append(calc_taxable)
                elif ext_taxable is not None:
                    calc_line_taxables.append(ext_taxable)
                    l_check["calculated_taxable"] = ext_taxable
                    l_check["status"] = "REVIEW_REQUIRED"
                    l_check["note"] = "Quantity or unit price not provided; used extracted taxable amount."
                else:
                    l_check["status"] = "REVIEW_REQUIRED"
                    all_lines_valid = False
                    has_review = True
                    warnings.append(f"Line {idx} has insufficient pricing details to verify taxable amount.")

                line_item_checks.append(l_check)

        line_math_status = "PASSED" if (line_item_checks and all_lines_valid) else ("MISMATCH" if has_mismatch else ("NOT_APPLICABLE" if not raw_line_items else "REVIEW_REQUIRED"))
        checks.append({
            "name": "line_item_math",
            "description": "Per-line arithmetic verification (quantity × unit_price - discount = taxable amount)",
            "status": line_math_status,
            "total_lines_checked": len(line_item_checks),
            "line_breakdowns": line_item_checks,
        })

        # -------------------------------------------------------------
        # CHECK 2: Line Item Sum vs Subtotal
        # -------------------------------------------------------------
        calculated_subtotal: Optional[float] = None
        if calc_line_taxables:
            calculated_subtotal = round(sum(calc_line_taxables), 2)

        if calculated_subtotal is not None and src_subtotal is not None:
            subtotal_diff = round(abs(src_subtotal - calculated_subtotal), 2)
            if subtotal_diff <= tol:
                sub_status = "PASSED"
            else:
                sub_status = "MISMATCH"
                has_mismatch = True
                errors.append(f"Subtotal mismatch: Sum of line items is ₹{calculated_subtotal:,.2f}, but extracted subtotal is ₹{src_subtotal:,.2f} (diff: ₹{subtotal_diff:,.2f}).")

            checks.append({
                "name": "line_item_sum_vs_subtotal",
                "description": "Sum of line items vs extracted invoice subtotal",
                "status": sub_status,
                "source_value": src_subtotal,
                "calculated_value": calculated_subtotal,
                "difference": subtotal_diff,
            })
        elif src_subtotal is not None:
            checks.append({
                "name": "line_item_sum_vs_subtotal",
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
                "description": "Sum of line items vs extracted invoice subtotal",
                "status": "REVIEW_REQUIRED",
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
                "description": "Sum of GST components (CGST + SGST + IGST + Cess) vs extracted Tax Total",
                "status": gst_status,
                "source_value": src_tax_total,
                "calculated_value": calculated_gst_total,
                "difference": gst_diff,
            })
        elif calculated_gst_total is not None:
            checks.append({
                "name": "gst_components_vs_gst_total",
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
                "description": "Sum of GST components (CGST + SGST + IGST + Cess) vs extracted Tax Total",
                "status": "REVIEW_REQUIRED",
                "source_value": src_tax_total,
                "calculated_value": None,
                "difference": 0.0,
                "note": "Individual CGST/SGST/IGST breakdown missing; used extracted Tax Total.",
            })
            warnings.append("Individual GST tax components (CGST/SGST/IGST) not explicitly broken down.")
        else:
            checks.append({
                "name": "gst_components_vs_gst_total",
                "description": "Sum of GST components (CGST + SGST + IGST + Cess) vs extracted Tax Total",
                "status": "REVIEW_REQUIRED",
                "source_value": None,
                "calculated_value": None,
                "difference": 0.0,
                "note": "No GST amounts found on invoice.",
            })

        # -------------------------------------------------------------
        # CHECK 4: Grand Total Equation
        # Subtotal - Discount + GST + Shipping + Other Charges +/- Round Off = Total Amount
        # -------------------------------------------------------------
        effective_subtotal = calculated_subtotal if calculated_subtotal is not None else src_subtotal
        effective_tax = calculated_gst_total if calculated_gst_total is not None else (src_tax_total or 0.0)

        calculated_grand_total: Optional[float] = None
        if effective_subtotal is not None:
            round_off_val = src_round_off if src_round_off is not None else 0.0
            
            # Scenario A: Header discount deducted from gross subtotal
            grand_total_hdr_disc = round(
                effective_subtotal - src_discount + effective_tax + src_shipping + src_other + round_off_val,
                2,
            )
            # Scenario B: Line discounts were already subtracted in subtotal (standard GST invoice)
            grand_total_line_disc = round(
                effective_subtotal + effective_tax + src_shipping + src_other + round_off_val,
                2,
            )

            if src_total_amount is not None:
                diff_hdr = round(abs(src_total_amount - grand_total_hdr_disc), 2)
                diff_line = round(abs(src_total_amount - grand_total_line_disc), 2)

                if diff_line <= tol and (src_discount == 0.0 or diff_line <= diff_hdr):
                    calculated_grand_total = grand_total_line_disc
                    total_diff = diff_line
                elif diff_hdr <= tol:
                    calculated_grand_total = grand_total_hdr_disc
                    total_diff = diff_hdr
                else:
                    if diff_line < diff_hdr:
                        calculated_grand_total = grand_total_line_disc
                        total_diff = diff_line
                    else:
                        calculated_grand_total = grand_total_hdr_disc
                        total_diff = diff_hdr

                if total_diff <= tol:
                    total_status = "PASSED"
                else:
                    total_status = "MISMATCH"
                    has_mismatch = True
                    errors.append(f"Grand Total mismatch: Expected ₹{calculated_grand_total:,.2f} (Subtotal ₹{effective_subtotal:,.2f} + Tax ₹{effective_tax:,.2f} + Ship ₹{src_shipping:,.2f} + Other ₹{src_other:,.2f} + Round ₹{round_off_val:,.2f}), but extracted total is ₹{src_total_amount:,.2f} (diff: ₹{total_diff:,.2f}).")

                checks.append({
                    "name": "extracted_total_vs_calculated_total",
                    "description": "Expected Grand Total equation (Subtotal - Discount + Tax + Shipping + Other +/- RoundOff) vs extracted Grand Total",
                    "status": total_status,
                    "source_value": src_total_amount,
                    "calculated_value": calculated_grand_total,
                    "difference": total_diff,
                })
            else:
                calculated_grand_total = grand_total_line_disc
                checks.append({
                    "name": "extracted_total_vs_calculated_total",
                    "description": "Expected Grand Total equation vs extracted Grand Total",
                    "status": "REVIEW_REQUIRED",
                    "source_value": None,
                    "calculated_value": calculated_grand_total,
                    "difference": 0.0,
                    "note": "Extracted Grand Total missing from invoice.",
                })
                has_review = True
        elif src_total_amount is not None:
            checks.append({
                "name": "extracted_total_vs_calculated_total",
                "description": "Expected Grand Total equation vs extracted Grand Total",
                "status": "REVIEW_REQUIRED",
                "source_value": src_total_amount,
                "calculated_value": calculated_grand_total,
                "difference": 0.0,
                "note": "Subtotal or tax components missing to compute expected Grand Total.",
            })
            has_review = True
        else:
            checks.append({
                "name": "extracted_total_vs_calculated_total",
                "description": "Expected Grand Total equation vs extracted Grand Total",
                "status": "REVIEW_REQUIRED",
                "source_value": None,
                "calculated_value": calculated_grand_total,
                "difference": 0.0,
                "note": "Extracted Grand Total missing from invoice.",
            })
            has_review = True

        # -------------------------------------------------------------
        # CHECK 5: Round-Off Consistency
        # -------------------------------------------------------------
        if src_round_off is not None and effective_subtotal is not None and src_total_amount is not None:
            unrounded_total = round(
                effective_subtotal - src_discount + effective_tax + src_shipping + src_other,
                2,
            )
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
        # Overall Status
        # -------------------------------------------------------------
        if has_mismatch:
            overall_status = "MISMATCH"
        elif has_review or src_total_amount is None:
            overall_status = "REVIEW_REQUIRED"
        else:
            overall_status = "PASSED"

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
