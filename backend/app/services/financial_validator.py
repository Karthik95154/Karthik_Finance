import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FinancialValidator:
    """Validates mathematical consistency, GST rules, and tax equations on invoices."""

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
            # Check if place of supply mentions vendor state code
            if vendor_state in place_of_supply:
                return "INTRA_STATE"
            return "INTER_STATE"

        return "INTRA_STATE"  # Default assumption if unspecified

    @classmethod
    def validate_invoice_math(
        cls,
        data: Dict[str, Any],
        tolerance: float = 0.05,
    ) -> Tuple[bool, List[str], Dict[str, float]]:
        """
        Validates invoice arithmetic:
        Subtotal + Tax Total - Discount + Shipping + Other + Roundoff == Total Amount (+/- tolerance)
        """
        errors = []

        subtotal = float(data.get("subtotal") or 0.0)
        discount_total = float(data.get("discount_total") or 0.0)
        tax_total = float(data.get("tax_total") or 0.0)
        shipping = float(data.get("shipping_charges") or 0.0)
        other_charges = float(data.get("other_charges") or 0.0)
        round_off = float(data.get("round_off") or 0.0)
        total_amount = float(data.get("total_amount") or 0.0)

        # 1. Sum up line items if present
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

        # Reconcile line items against header
        if line_items and subtotal > 0 and abs(line_taxable_sum - subtotal) > (len(line_items) * tolerance):
            errors.append(
                f"Line taxable sum (₹{line_taxable_sum:.2f}) does not match header subtotal (₹{subtotal:.2f})"
            )

        expected_grand_total = round(
            subtotal + tax_total - discount_total + shipping + other_charges + round_off, 2
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


financial_validator = FinancialValidator()
