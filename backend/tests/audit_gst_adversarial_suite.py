"""
Dedicated GST Structural & Rate-Amount Adversarial Audit Suite.
DO NOT MODIFY PRODUCTION CODE.
Uses an independent Decimal-based oracle to test:
- Group A: GST Structure (CGST+SGST, IGST, illegal combos, POS vs supply type, equality, Cess, zero-tax, 0.00 presence)
- Group B: GST Rate <-> Amount (matching, mismatch, 0.00 amount, missing amounts, tolerance boundaries, negative/malformed)
- Group C: Header vs Line GST (header-only, line-only, mismatches, multi-line)
- Group D: Adversarial Attacks (simultaneous CGST+SGST+IGST, unequal CGST/SGST, 18% with 0, 0% with tax, None vs 0)
- Group E: 5,000 Property-based Fuzz Tests
"""
import sys
import os
import random
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Tuple, Optional

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from app.services.financial_validator import FinancialValidator, parse_clean_numeric
from app.services.gst_engine import gst_engine


# ==============================================================================
# INDEPENDENT DECIMAL ORACLE FOR GST STRUCTURE AND RATE-AMOUNT
# ==============================================================================

class IndependentGSTOracle:
    """
    Independent Decimal Oracle for Indian Statutory GST Structure and Line Math.
    Evaluates:
    - Mathematical Inconsistency (taxable * rate / 100 != amount, or sum != total)
    - Structural Inconsistency (inter vs intra conflict, simultaneous CGST+SGST+IGST, CGST != SGST)
    - Ambiguity (missing tax details requiring human review)
    """
    TOLERANCE = Decimal("1.00")

    @staticmethod
    def to_dec(val: Any) -> Optional[Decimal]:
        if val is None or isinstance(val, (list, dict, bool)):
            return None
        if isinstance(val, (int, float)):
            return Decimal(str(val))
        if isinstance(val, str):
            s = val.strip()
            for cur in ["₹", "Rs.", "Rs", "INR", "$", ","]:
                s = s.replace(cur, "")
            s = s.strip()
            if "e" in s.lower():
                try: return Decimal(str(float(s)))
                except Exception: return None
            s = s.rstrip("%").strip()
            if s.lower() in ["nan", "infinity", "-infinity"]:
                return None
            try: return Decimal(s)
            except Exception: return None
        return None

    @classmethod
    def evaluate_gst(cls, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determines the strictly correct deterministic status of the invoice
        under statutory Indian GST rules and mathematical truth.
        """
        subtotal = cls.to_dec(invoice_data.get("subtotal"))
        tax_total = cls.to_dec(invoice_data.get("tax_total"))
        cgst_hdr = cls.to_dec(invoice_data.get("cgst_amount"))
        sgst_hdr = cls.to_dec(invoice_data.get("sgst_amount"))
        igst_hdr = cls.to_dec(invoice_data.get("igst_amount"))
        cess_hdr = cls.to_dec(invoice_data.get("cess_amount") or invoice_data.get("cess"))

        # Check explicit supply type / place of supply
        pos = str(invoice_data.get("place_of_supply") or "").strip()
        v_gstin = str(invoice_data.get("vendor_gstin") or "").strip()
        c_gstin = str(invoice_data.get("customer_gstin") or "").strip()

        has_cgst = cgst_hdr is not None and cgst_hdr > Decimal("0")
        has_sgst = sgst_hdr is not None and sgst_hdr > Decimal("0")
        has_igst = igst_hdr is not None and igst_hdr > Decimal("0")
        has_cess = cess_hdr is not None and cess_hdr > Decimal("0")

        # Check line items
        lines = invoice_data.get("line_items") or []
        line_cgst_sum = Decimal("0")
        line_sgst_sum = Decimal("0")
        line_igst_sum = Decimal("0")
        line_cess_sum = Decimal("0")
        has_line_taxes = False

        reasons = []
        is_mismatch = False
        is_review_required = False

        # --- A. STRUCTURAL GST AUDIT ---
        # 1. Simultaneous CGST/SGST and IGST is illegal on the same invoice (unless distinct lines exist with distinct tax regimes, but on header level mutually exclusive)
        if (has_cgst or has_sgst) and has_igst:
            is_review_required = True
            reasons.append("Simultaneous CGST/SGST and IGST on same invoice (structural conflict)")

        # 2. Intra-state supply requires equal CGST and SGST
        if (has_cgst or has_sgst):
            if cgst_hdr is not None and sgst_hdr is not None:
                if abs(cgst_hdr - sgst_hdr) > cls.TOLERANCE:
                    is_review_required = True
                    reasons.append(f"CGST ({cgst_hdr}) and SGST ({sgst_hdr}) are unequal on intra-state supply")
            elif (has_cgst and not has_sgst) or (has_sgst and not has_cgst):
                is_review_required = True
                reasons.append("Unpaired CGST or SGST (must co-exist for intra-state supply)")

        # 3. Supply type vs tax components check if GSTINs/POS available
        v_state = v_gstin[:2] if len(v_gstin) >= 2 and v_gstin[:2].isdigit() else None
        c_state = c_gstin[:2] if len(c_gstin) >= 2 and c_gstin[:2].isdigit() else None
        pos_state = pos[:2] if len(pos) >= 2 and pos[:2].isdigit() else (c_state if c_state else None)

        if v_state and pos_state:
            if v_state == pos_state and has_igst:
                is_mismatch = True
                reasons.append(f"Intra-state supply (State {v_state}) charged with unexpected IGST")
            elif v_state != pos_state and (has_cgst or has_sgst):
                is_mismatch = True
                reasons.append(f"Inter-state supply (Vendor {v_state} vs POS {pos_state}) charged with unexpected CGST/SGST")

        # --- B. LINE-LEVEL RATE <-> AMOUNT AND LINE MATH ---
        for idx, item in enumerate(lines, 1):
            qty = cls.to_dec(item.get("quantity"))
            price = cls.to_dec(item.get("unit_price") or item.get("rate") or item.get("price"))
            taxable = cls.to_dec(item.get("taxable_amount"))
            if taxable is None and qty is not None and price is not None:
                taxable = (qty * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            l_c_amt = cls.to_dec(item.get("cgst_amount"))
            l_s_amt = cls.to_dec(item.get("sgst_amount"))
            l_i_amt = cls.to_dec(item.get("igst_amount"))
            l_ce_amt = cls.to_dec(item.get("cess_amount") or item.get("cess"))

            l_c_rate = cls.to_dec(item.get("cgst_rate"))
            l_s_rate = cls.to_dec(item.get("sgst_rate"))
            l_i_rate = cls.to_dec(item.get("igst_rate"))
            l_ce_rate = cls.to_dec(item.get("cess_rate"))

            # Rate <-> Amount checks
            for c_name, r, a in [("CGST", l_c_rate, l_c_amt), ("SGST", l_s_rate, l_s_amt), ("IGST", l_i_rate, l_i_amt), ("Cess", l_ce_rate, l_ce_amt)]:
                if r is not None and a is not None and taxable is not None and taxable > Decimal("0"):
                    calc_a = (taxable * r / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if abs(calc_a - a) > cls.TOLERANCE:
                        is_review_required = True
                        reasons.append(f"Line {idx} {c_name} rate {r}% implies {calc_a}, but reported amount is {a}")
                elif r is not None and r > Decimal("0") and a is not None and a == Decimal("0"):
                    is_review_required = True
                    reasons.append(f"Line {idx} {c_name} has rate {r}% but zero tax amount")

            # Accumulate line taxes
            if any(x is not None for x in [l_c_amt, l_s_amt, l_i_amt, l_ce_amt]):
                has_line_taxes = True
                line_cgst_sum += l_c_amt or Decimal("0")
                line_sgst_sum += l_s_amt or Decimal("0")
                line_igst_sum += l_i_amt or Decimal("0")
                line_cess_sum += l_ce_amt or Decimal("0")

        # --- C. HEADER VS LINE RECONCILIATION ---
        if has_line_taxes:
            line_tax_total = line_cgst_sum + line_sgst_sum + line_igst_sum + line_cess_sum
            if tax_total is not None and abs(tax_total - line_tax_total) > cls.TOLERANCE:
                is_mismatch = True
                reasons.append(f"Header Tax Total ({tax_total}) does not match Line Taxes Sum ({line_tax_total})")

        # Check scalar component sum vs tax_total
        hdr_comp_sum = Decimal("0")
        has_hdr_comps = any(x is not None for x in [cgst_hdr, sgst_hdr, igst_hdr, cess_hdr])
        if has_hdr_comps:
            hdr_comp_sum = (cgst_hdr or Decimal("0")) + (sgst_hdr or Decimal("0")) + (igst_hdr or Decimal("0")) + (cess_hdr or Decimal("0"))
            if tax_total is not None and abs(tax_total - hdr_comp_sum) > cls.TOLERANCE:
                is_mismatch = True
                reasons.append(f"Header tax components sum ({hdr_comp_sum}) != Tax Total ({tax_total})")

        if is_mismatch:
            return {"status": "MISMATCH", "reasons": reasons}
        elif is_review_required:
            return {"status": "REVIEW_REQUIRED", "reasons": reasons}
        else:
            return {"status": "PASSED", "reasons": []}


# ==============================================================================
# AUDIT RUNNER ACROSS ALL GROUPS (A, B, C, D, E)
# ==============================================================================

def run_gst_adversarial_audit():
    validator = FinancialValidator(tolerance=1.0)
    oracle = IndependentGSTOracle()

    categories = [
        "A. GST Structure",
        "B. GST Rate <-> Amount",
        "C. Header vs Line GST",
        "D. Adversarial Cases",
        "E. Property Fuzz Testing",
    ]

    stats = {cat: {"total": 0, "correct_pass": 0, "correct_mismatch": 0, "correct_review": 0, "false_pass": 0, "false_reject": 0, "crashes": 0, "defects": []} for cat in categories}

    def evaluate_and_record(cat: str, name: str, invoice_data: Dict[str, Any]):
        stats[cat]["total"] += 1
        oracle_res = oracle.evaluate_gst(invoice_data)
        exp = oracle_res["status"]

        try:
            # Also run gst_engine to see if it passed or was evaluated
            gst_res = gst_engine.evaluate_gst(invoice_data) if (invoice_data.get("vendor_gstin") or invoice_data.get("place_of_supply")) else None
            val_res = validator.validate_invoice(invoice_data, gst_result=gst_res)
            act = val_res["overall_status"]
        except Exception as e:
            stats[cat]["crashes"] += 1
            stats[cat]["defects"].append({"name": name, "issue": f"CRASH: {str(e)}", "expected": exp, "actual": "CRASH"})
            return

        is_fp = False
        is_fr = False

        if exp == act:
            if act == "PASSED": stats[cat]["correct_pass"] += 1
            elif act == "MISMATCH": stats[cat]["correct_mismatch"] += 1
            elif act == "REVIEW_REQUIRED": stats[cat]["correct_review"] += 1
        elif exp in ["MISMATCH", "REVIEW_REQUIRED"] and act == "PASSED":
            is_fp = True
            stats[cat]["false_pass"] += 1
            stats[cat]["defects"].append({
                "name": name,
                "expected": exp,
                "actual": act,
                "reasons": oracle_res["reasons"],
                "validator_errors": val_res.get("errors", []),
                "validator_warnings": val_res.get("warnings", []),
            })
        elif exp == "PASSED" and act in ["MISMATCH", "REVIEW_REQUIRED"]:
            is_fr = True
            stats[cat]["false_reject"] += 1
            stats[cat]["defects"].append({
                "name": name,
                "expected": exp,
                "actual": act,
                "validator_errors": val_res.get("errors", []),
                "validator_warnings": val_res.get("warnings", []),
            })
        else:
            # e.g. MISMATCH vs REVIEW_REQUIRED or vice versa
            if act == "REVIEW_REQUIRED": stats[cat]["correct_review"] += 1
            else: stats[cat]["correct_mismatch"] += 1

    # ==========================================================================
    # GROUP A: GST STRUCTURE
    # ==========================================================================
    group_a_cases = [
        ("A1. CGST + SGST together -> valid", {
            "subtotal": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "tax_total": 180.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0}]
        }),
        ("A2. IGST alone -> valid", {
            "subtotal": 1000.0, "igst_amount": 180.0, "tax_total": 180.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "igst_amount": 180.0, "total": 1180.0}]
        }),
        ("A3. CGST + SGST + IGST together -> invalid structural conflict", {
            "subtotal": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "igst_amount": 180.0, "tax_total": 360.0, "total_amount": 1360.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "total": 1360.0}]
        }),
        ("A4. IGST + CGST (no SGST) -> invalid structural conflict", {
            "subtotal": 1000.0, "cgst_amount": 90.0, "igst_amount": 90.0, "tax_total": 180.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "total": 1180.0}]
        }),
        ("A5. IGST + SGST (no CGST) -> invalid structural conflict", {
            "subtotal": 1000.0, "sgst_amount": 90.0, "igst_amount": 90.0, "tax_total": 180.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "total": 1180.0}]
        }),
        ("A6. Intra-state supply with CGST + SGST", {
            "vendor_gstin": "27AABCU9603R1ZM", "place_of_supply": "27-Maharashtra",
            "subtotal": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "tax_total": 180.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0}]
        }),
        ("A7. Inter-state supply with IGST", {
            "vendor_gstin": "27AABCU9603R1ZM", "place_of_supply": "29-Karnataka",
            "subtotal": 1000.0, "igst_amount": 180.0, "tax_total": 180.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "igst_amount": 180.0, "total": 1180.0}]
        }),
        ("A8. CGST and SGST unequal (CGST=90, SGST=0) -> structural conflict", {
            "subtotal": 1000.0, "cgst_amount": 90.0, "sgst_amount": 0.0, "tax_total": 90.0, "total_amount": 1090.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 0.0, "total": 1090.0}]
        }),
        ("A9. Cess coexists independently with CGST + SGST", {
            "subtotal": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "cess_amount": 120.0, "tax_total": 300.0, "total_amount": 1300.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "cess_amount": 120.0, "total": 1300.0}]
        }),
        ("A10. Zero-tax / exempt invoice (subtotal=1000, tax=0, total=1000)", {
            "subtotal": 1000.0, "tax_total": 0.0, "total_amount": 1000.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "total": 1000.0}]
        }),
        ("A11. Explicit 0.00 tax components present (subtotal=1000, cgst=0.0, sgst=0.0, total=1000)", {
            "subtotal": 1000.0, "cgst_amount": 0.0, "sgst_amount": 0.0, "tax_total": 0.0, "total_amount": 1000.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 0.0, "sgst_amount": 0.0, "total": 1000.0}]
        }),
    ]
    for name, inv in group_a_cases:
        evaluate_and_record("A. GST Structure", name, inv)

    # ==========================================================================
    # GROUP B: GST RATE <-> AMOUNT
    # ==========================================================================
    group_b_cases = [
        ("B1. Rate present + amount present + matching: 9% -> 90.0", {
            "subtotal": 1000.0, "tax_total": 180.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_rate": 9.0, "cgst_amount": 90.0, "sgst_rate": 9.0, "sgst_amount": 90.0, "total": 1180.0}]
        }),
        ("B2. Rate present (18%) + amount wrong (90.0) -> conflict", {
            "subtotal": 1000.0, "tax_total": 180.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_rate": 18.0, "cgst_amount": 90.0, "sgst_rate": 9.0, "sgst_amount": 90.0, "total": 1180.0}]
        }),
        ("B3. Rate present (9%) + amount 0.00 -> conflict", {
            "subtotal": 1000.0, "tax_total": 0.0, "cgst_amount": 0.0, "sgst_amount": 0.0, "total_amount": 1000.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_rate": 9.0, "cgst_amount": 0.0, "sgst_rate": 9.0, "sgst_amount": 0.0, "total": 1000.0}]
        }),
        ("B4. Tax amount present (90) + rate missing -> valid", {
            "subtotal": 1000.0, "tax_total": 180.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0}]
        }),
        ("B5. Both rate and amount missing on line, header tax=180 -> unallocated", {
            "subtotal": 1000.0, "tax_total": 180.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "total": 1180.0}]
        }),
        ("B6. Rate/amount diff within ₹1.00 tolerance (1000 * 9% = 90.0, amt = 90.50)", {
            "subtotal": 1000.0, "tax_total": 181.0, "cgst_amount": 90.5, "sgst_amount": 90.5, "total_amount": 1181.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_rate": 9.0, "cgst_amount": 90.5, "sgst_rate": 9.0, "sgst_amount": 90.5, "total": 1181.0}]
        }),
        ("B7. Rate/amount diff outside ₹1.00 tolerance (1000 * 9% = 90.0, amt = 92.00)", {
            "subtotal": 1000.0, "tax_total": 184.0, "cgst_amount": 92.0, "sgst_amount": 92.0, "total_amount": 1184.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_rate": 9.0, "cgst_amount": 92.0, "sgst_rate": 9.0, "sgst_amount": 92.0, "total": 1184.0}]
        }),
        ("B8. 0% rate with 0.00 amount -> matching", {
            "subtotal": 1000.0, "tax_total": 0.0, "cgst_amount": 0.0, "sgst_amount": 0.0, "total_amount": 1000.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_rate": 0.0, "cgst_amount": 0.0, "sgst_rate": 0.0, "sgst_amount": 0.0, "total": 1000.0}]
        }),
        ("B9. Rate given as string '9%' vs numeric -> matching", {
            "subtotal": 1000.0, "tax_total": 180.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_rate": "9%", "cgst_amount": 90.0, "sgst_rate": "9%", "sgst_amount": 90.0, "total": 1180.0}]
        }),
    ]
    for name, inv in group_b_cases:
        evaluate_and_record("B. GST Rate <-> Amount", name, inv)

    # ==========================================================================
    # GROUP C: HEADER VS LINE GST
    # ==========================================================================
    group_c_cases = [
        ("C1. Header tax only (no line taxes, single line) -> review required", {
            "subtotal": 1000.0, "tax_total": 180.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "total": 1180.0}]
        }),
        ("C2. Line tax only (header tax omitted -> derived from lines)", {
            "subtotal": 1000.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0}]
        }),
        ("C3. Header total agrees with line components (180 == 90 + 90)", {
            "subtotal": 1000.0, "tax_total": 180.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0}]
        }),
        ("C4. Line component sums disagree with header tax total (line sum 180 vs header tax 200)", {
            "subtotal": 1000.0, "tax_total": 200.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total_amount": 1200.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0}]
        }),
        ("C5. Multiple lines with one corrupted tax component (Line 2 CGST 999)", {
            "subtotal": 2000.0, "tax_total": 360.0, "cgst_amount": 180.0, "sgst_amount": 180.0, "total_amount": 2360.0,
            "line_items": [
                {"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0},
                {"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 999.0, "sgst_amount": 90.0, "total": 2089.0},
            ]
        }),
    ]
    for name, inv in group_c_cases:
        evaluate_and_record("C. Header vs Line GST", name, inv)

    # ==========================================================================
    # GROUP D: ADVERSARIAL CASES
    # ==========================================================================
    group_d_cases = [
        ("D1. Simultaneous CGST + SGST + IGST matching scalar sum", {
            "subtotal": 1000.0, "cgst_amount": 45.0, "sgst_amount": 45.0, "igst_amount": 90.0, "tax_total": 180.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "total": 1180.0}]
        }),
        ("D2. CGST != SGST (CGST 100, SGST 80, tax_total 180)", {
            "subtotal": 1000.0, "cgst_amount": 100.0, "sgst_amount": 80.0, "tax_total": 180.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 100.0, "sgst_amount": 80.0, "total": 1180.0}]
        }),
        ("D3. 18% CGST rate declared with 0.00 tax amount", {
            "subtotal": 1000.0, "tax_total": 0.0, "cgst_amount": 0.0, "sgst_amount": 0.0, "total_amount": 1000.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_rate": 18.0, "cgst_amount": 0.0, "total": 1000.0}]
        }),
        ("D4. 18% IGST with incorrect amount (18% on 1000 = 180, but amt = 150)", {
            "subtotal": 1000.0, "tax_total": 150.0, "igst_amount": 150.0, "total_amount": 1150.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "igst_rate": 18.0, "igst_amount": 150.0, "total": 1150.0}]
        }),
        ("D5. 0% GST rate with non-zero tax amount (rate 0%, amt 180)", {
            "subtotal": 1000.0, "tax_total": 180.0, "igst_amount": 180.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "igst_rate": 0.0, "igst_amount": 180.0, "total": 1180.0}]
        }),
        ("D6. Negative tax on positive taxable (taxable 1000, tax -180)", {
            "subtotal": 1000.0, "tax_total": -180.0, "cgst_amount": -90.0, "sgst_amount": -90.0, "total_amount": 820.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": -90.0, "sgst_amount": -90.0, "total": 820.0}]
        }),
        ("D7. Malformed string rate 'NaN' on line item", {
            "subtotal": 1000.0, "tax_total": 180.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_rate": "NaN", "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0}]
        }),
    ]
    for name, inv in group_d_cases:
        evaluate_and_record("D. Adversarial Cases", name, inv)

    # ==========================================================================
    # GROUP E: 5,000 PROPERTY/FUZZ TESTS
    # ==========================================================================
    random.seed(42)
    fuzz_count = 5000
    for i in range(fuzz_count):
        q = random.randint(1, 5)
        p = random.randint(50, 400)
        taxable = Decimal(str(q * p))

        # Test various GST combinations
        combo = random.choice(["INTRA", "INTER", "ILLEGAL_SIMULTANEOUS", "UNEQUAL_CGST_SGST", "RATE_MUTATION"])
        
        if combo == "INTRA":
            cgst = (taxable * Decimal("9") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            sgst = cgst
            inv = {
                "subtotal": float(taxable), "cgst_amount": float(cgst), "sgst_amount": float(sgst),
                "tax_total": float(cgst + sgst), "total_amount": float(taxable + cgst + sgst),
                "line_items": [{"quantity": q, "unit_price": p, "taxable_amount": float(taxable), "cgst_amount": float(cgst), "sgst_amount": float(sgst), "total": float(taxable + cgst + sgst)}]
            }
        elif combo == "INTER":
            igst = (taxable * Decimal("18") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            inv = {
                "subtotal": float(taxable), "igst_amount": float(igst),
                "tax_total": float(igst), "total_amount": float(taxable + igst),
                "line_items": [{"quantity": q, "unit_price": p, "taxable_amount": float(taxable), "igst_amount": float(igst), "total": float(taxable + igst)}]
            }
        elif combo == "ILLEGAL_SIMULTANEOUS":
            cgst = (taxable * Decimal("4.5") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            sgst = cgst
            igst = (taxable * Decimal("9") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tot_tax = cgst + sgst + igst
            inv = {
                "subtotal": float(taxable), "cgst_amount": float(cgst), "sgst_amount": float(sgst), "igst_amount": float(igst),
                "tax_total": float(tot_tax), "total_amount": float(taxable + tot_tax),
                "line_items": [{"quantity": q, "unit_price": p, "taxable_amount": float(taxable), "total": float(taxable + tot_tax)}]
            }
        elif combo == "UNEQUAL_CGST_SGST":
            cgst = (taxable * Decimal("9") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            sgst = cgst + Decimal("10.00")
            tot_tax = cgst + sgst
            inv = {
                "subtotal": float(taxable), "cgst_amount": float(cgst), "sgst_amount": float(sgst),
                "tax_total": float(tot_tax), "total_amount": float(taxable + tot_tax),
                "line_items": [{"quantity": q, "unit_price": p, "taxable_amount": float(taxable), "cgst_amount": float(cgst), "sgst_amount": float(sgst), "total": float(taxable + tot_tax)}]
            }
        elif combo == "RATE_MUTATION":
            cgst = (taxable * Decimal("9") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            sgst = cgst
            tot_tax = cgst + sgst
            # Deliberately corrupt rate to 18% on line
            inv = {
                "subtotal": float(taxable), "cgst_amount": float(cgst), "sgst_amount": float(sgst),
                "tax_total": float(tot_tax), "total_amount": float(taxable + tot_tax),
                "line_items": [{"quantity": q, "unit_price": p, "taxable_amount": float(taxable), "cgst_rate": 18.0, "cgst_amount": float(cgst), "sgst_rate": 9.0, "sgst_amount": float(sgst), "total": float(taxable + tot_tax)}]
            }

        evaluate_and_record("E. Property Fuzz Testing", f"Fuzz #{i+1} ({combo})", inv)

    print("\n" + "="*80)
    print("GST STRUCTURAL & RATE-AMOUNT ADVERSARIAL AUDIT RESULTS")
    print("="*80)

    total_all = sum(s["total"] for s in stats.values())
    total_fp = sum(s["false_pass"] for s in stats.values())
    total_fr = sum(s["false_reject"] for s in stats.values())
    total_cr = sum(s["crashes"] for s in stats.values())
    total_cp = sum(s["correct_pass"] for s in stats.values())
    total_cm = sum(s["correct_mismatch"] for s in stats.values())
    total_crv = sum(s["correct_review"] for s in stats.values())

    print(f"Total Cases:     {total_all}")
    print(f"Correct Pass:    {total_cp}")
    print(f"Correct Mismatch:{total_cm}")
    print(f"Correct Review:  {total_crv}")
    print(f"False PASS:      {total_fp}")
    print(f"False REJECT:    {total_fr}")
    print(f"Crashes:         {total_cr}")

    print("\nCATEGORY SUMMARY TABLE:")
    header = f"| {'Category':<28} | {'Total':<6} | {'Pass':<6} | {'Mismatch':<8} | {'Review':<6} | {'False PASS':<10} | {'False REJECT':<12} | {'Crash':<5} |"
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    for cat in categories:
        s = stats[cat]
        print(f"| {cat:<28} | {s['total']:<6} | {s['correct_pass']:<6} | {s['correct_mismatch']:<8} | {s['correct_review']:<6} | {s['false_pass']:<10} | {s['false_reject']:<12} | {s['crashes']:<5} |")
    print("-" * len(header))

    print("\nSAMPLE FALSE PASSES (Where GST structure or rates violated statutory rules but validator PASSED):")
    for cat in categories:
        fps = stats[cat]["defects"]
        if fps:
            print(f"\n--- {cat} ({len(fps)} defects) ---")
            for d in fps[:5]:
                print(f"  * {d['name']} -> Actual: {d['actual']} (Expected: {d['expected']}) | Reasons: {d.get('reasons')}")


if __name__ == "__main__":
    run_gst_adversarial_audit()
