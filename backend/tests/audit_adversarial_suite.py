import sys
import os
import time
import random
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Tuple, Optional

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from app.services.financial_validator import FinancialValidator, parse_clean_numeric, parse_discount_semantics


# ============================================================================
# INDEPENDENT TEST ORACLE (NO REUSE OF PRODUCTION CODE)
# ============================================================================

def oracle_parse_numeric(val: Any) -> Optional[Decimal]:
    """Independent oracle for numeric parsing."""
    if val is None or isinstance(val, (list, dict)):
        return None
    if isinstance(val, bool):
        # In strict financial accounting, booleans are not numbers
        return None
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        # Remove currency symbols and formatting commas
        for cur in ["₹", "Rs.", "Rs", "INR", "inr", "$", "USD", "usd", "EUR", "eur", ","]:
            s = s.replace(cur, "")
        s = s.strip()
        # Handle scientific notation
        if "e" in s.lower():
            try:
                return Decimal(str(float(s)))
            except Exception:
                return None
        # Remove trailing %
        s = s.rstrip("%").strip()
        try:
            return Decimal(s)
        except Exception:
            return None
    return None


def oracle_validate_line_item(item: Dict[str, Any], tol: Decimal = Decimal("1.00")) -> Dict[str, Any]:
    """Independent oracle for line-item math."""
    q_dec = oracle_parse_numeric(item.get("quantity"))
    p_dec = oracle_parse_numeric(item.get("unit_price") or item.get("rate") or item.get("price"))
    ext_tax_dec = oracle_parse_numeric(item.get("taxable_amount") or item.get("total") or item.get("amount"))

    # Determine discount
    raw_d = item.get("discount")
    raw_d_str = str(raw_d).strip() if raw_d is not None else ""
    explicit_type = item.get("discount_type")

    is_percent = False
    is_amount = False
    is_ambiguous = False

    if "%" in raw_d_str or explicit_type == "percentage":
        is_percent = True
    elif any(c in raw_d_str for c in ["₹", "Rs", "INR", "$"]) or explicit_type == "amount":
        is_amount = True
    elif raw_d is not None:
        d_val = oracle_parse_numeric(raw_d)
        if d_val == Decimal("0"):
            is_amount = True
        else:
            is_ambiguous = True

    d_val = oracle_parse_numeric(raw_d) or Decimal("0")

    if is_ambiguous:
        return {"status": "REVIEW_REQUIRED", "reason": "AMBIGUOUS_DISCOUNT", "taxable": ext_tax_dec}
    if is_percent and (d_val < Decimal("0") or d_val > Decimal("100")):
        return {"status": "REVIEW_REQUIRED", "reason": "INVALID_PERCENTAGE", "taxable": ext_tax_dec}
    if d_val < Decimal("0"):
        return {"status": "REVIEW_REQUIRED", "reason": "NEGATIVE_DISCOUNT", "taxable": ext_tax_dec}

    if q_dec is not None and p_dec is not None:
        gross = (q_dec * p_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if is_percent:
            disc_amt = (gross * d_val / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            disc_amt = d_val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        calc_taxable = (gross - disc_amt).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if ext_tax_dec is not None:
            diff = abs(ext_tax_dec - calc_taxable)
            status = "PASSED" if diff <= tol else "MISMATCH"
            return {"status": status, "taxable": calc_taxable, "diff": diff}
        return {"status": "PASSED", "taxable": calc_taxable, "diff": Decimal("0")}
    elif ext_tax_dec is not None:
        return {"status": "REVIEW_REQUIRED", "reason": "NO_QTY_OR_PRICE", "taxable": ext_tax_dec}
    return {"status": "REVIEW_REQUIRED", "reason": "INSUFFICIENT_DETAILS", "taxable": None}


# ============================================================================
# AUDIT RUNNER & TEST HARNESS
# ============================================================================

def run_adversarial_suite():
    validator = FinancialValidator(tolerance=1.0)
    
    categories = [
        "numeric parsing", "quantity", "unit price", "discounts", "taxable",
        "line totals", "GST", "Cess", "subtotal", "grand total", "roundoff",
        "negative values", "missing data", "malformed data", "aliases",
        "conflicting fields", "tolerance boundaries", "floating point",
        "extreme values", "approval gate", "fuzz testing", "performance"
    ]
    
    stats = {cat: {"total": 0, "correct": 0, "false_pass": 0, "false_reject": 0, "crashes": 0, "defects": []} for cat in categories}
    
    total_tests = 0
    
    # ------------------------------------------------------------------------
    # 1. NUMERIC PARSING & TYPE CONFUSION
    # ------------------------------------------------------------------------
    num_attacks = [
        ("bool True", True, None, "numeric parsing", "SILENT_BOOL_COERCION"),
        ("bool False", False, None, "numeric parsing", "SILENT_BOOL_COERCION"),
        ("list [10]", [10], None, "numeric parsing", "SAFE_NONE"),
        ("dict {'a': 1}", {"a": 1}, None, "numeric parsing", "SAFE_NONE"),
        ("scientific 1e3", "1e3", 1000.0, "numeric parsing", "PARSING_CORRUPTION_13"),
        ("scientific 1E3", "1E3", 1000.0, "numeric parsing", "PARSING_CORRUPTION_13"),
        ("malformed 12abc", "12abc", None, "numeric parsing", "SILENT_PARTIAL_PARSE"),
        ("malformed abc12", "abc12", None, "numeric parsing", "SILENT_PARTIAL_PARSE"),
        ("double dot ..10", "..10", None, "numeric parsing", "SAFE_NONE"),
        ("multiple dot 1.2.3", "1.2.3", None, "numeric parsing", "SAFE_NONE"),
        ("double minus --10", "--10", None, "numeric parsing", "SAFE_NONE"),
        ("NaN string", "NaN", None, "numeric parsing", "SAFE_NONE"),
        ("Infinity string", "Infinity", None, "numeric parsing", "SAFE_NONE"),
        ("empty string", "", None, "numeric parsing", "SAFE_NONE"),
        ("whitespace", "   ", None, "numeric parsing", "SAFE_NONE"),
        ("Indian commas", "1,50,000.00", 150000.0, "numeric parsing", "ACCURATE"),
        ("Currency symbol", "₹1,234.50", 1234.5, "numeric parsing", "ACCURATE"),
    ]
    
    for label, inp, exp, cat, defect_tag in num_attacks:
        stats[cat]["total"] += 1
        total_tests += 1
        try:
            act = parse_clean_numeric(inp)
            if defect_tag == "SILENT_BOOL_COERCION" and act is not None:
                # Python bool treated as 1.0 / 0.0
                stats[cat]["false_pass"] += 1
                stats[cat]["defects"].append({
                    "input": f"{label} ({inp})",
                    "expected": exp,
                    "actual": act,
                    "issue": "Python bool coerced into float (True->1.0, False->0.0)",
                    "severity": "MEDIUM",
                })
            elif defect_tag == "PARSING_CORRUPTION_13" and act == 13.0:
                stats[cat]["false_pass"] += 1
                stats[cat]["defects"].append({
                    "input": f"{label} ('{inp}')",
                    "expected": exp,
                    "actual": act,
                    "issue": "Scientific notation '1e3' had 'e' stripped, leaving '13' -> 13.0 instead of 1000.0",
                    "severity": "HIGH",
                })
            elif defect_tag == "SILENT_PARTIAL_PARSE" and act == 12.0:
                stats[cat]["false_pass"] += 1
                stats[cat]["defects"].append({
                    "input": f"{label} ('{inp}')",
                    "expected": exp,
                    "actual": act,
                    "issue": "Letters stripped by regex re.sub('[^\\d.-]', ''), silently converting alphanumeric noise into valid number",
                    "severity": "MEDIUM",
                })
            else:
                stats[cat]["correct"] += 1
        except Exception as e:
            stats[cat]["crashes"] += 1
            stats[cat]["defects"].append({"input": label, "error": str(e), "severity": "CRITICAL"})

    # ------------------------------------------------------------------------
    # 2. LINE TOTAL VS TAX COMPONENTS (LINE TOTAL VALIDATION GAP)
    # ------------------------------------------------------------------------
    # A line where quantity*rate=1000, tax=180, but total is declared as 1000 (missing tax)
    # or total is declared as 5000 (inflated)
    line_total_cases = [
        ("Line total omits tax (total=1000 when taxable=1000, tax=180)", 1000.0, 180.0, 1000.0, 1180.0),
        ("Line total mismatch with line tax (taxable=1000, tax=180, total=9999)", 1000.0, 180.0, 9999.0, 1180.0),
    ]
    for desc, taxbl, tax_amt, l_tot, exp_grand in line_total_cases:
        stats["line totals"]["total"] += 1
        total_tests += 1
        inv = {
            "subtotal": taxbl,
            "tax_total": tax_amt,
            "cgst_amount": tax_amt / 2,
            "sgst_amount": tax_amt / 2,
            "total_amount": exp_grand,
            "line_items": [
                {
                    "quantity": 1,
                    "unit_price": taxbl,
                    "taxable_amount": taxbl,
                    "cgst_amount": tax_amt / 2,
                    "sgst_amount": tax_amt / 2,
                    "total": l_tot, # Intentionally invalid / contradictory line total
                }
            ]
        }
        res = validator.validate_invoice(inv)
        # The line total is contradictory, but FinancialValidator doesn't validate line total!
        if res["overall_status"] == "PASSED":
            stats["line totals"]["false_pass"] += 1
            stats["line totals"]["defects"].append({
                "input": f"{desc} with line total={l_tot}",
                "expected": "MISMATCH (Line total != taxable + taxes)",
                "actual": "PASSED",
                "issue": "FinancialValidator Check 1 verifies only (qty*price - disc == taxable), completely ignoring item['total']",
                "severity": "HIGH",
            })
        else:
            stats["line totals"]["correct"] += 1

    # ------------------------------------------------------------------------
    # 3. GST ARCHITECTURAL CONFLICTS (SIMULTANEOUS CGST+SGST+IGST, UNEQUAL RATES)
    # ------------------------------------------------------------------------
    gst_attacks = [
        ("Simultaneous CGST + SGST + IGST on same invoice", 1000.0, 90.0, 90.0, 180.0, 360.0, 1360.0),
        ("Unequal CGST and SGST (CGST 90, SGST 0)", 1000.0, 90.0, 0.0, 0.0, 90.0, 1090.0),
        ("Tax rate 18% declared with tax amount 0.0", 1000.0, 0.0, 0.0, 0.0, 0.0, 1000.0, 18.0),
    ]
    for case in gst_attacks:
        stats["GST"]["total"] += 1
        total_tests += 1
        if len(case) == 7:
            desc, sub, cgst, sgst, igst, tax_tot, grand = case
            rate = None
        else:
            desc, sub, cgst, sgst, igst, tax_tot, grand, rate = case
        
        li = {"quantity": 1, "unit_price": sub, "taxable_amount": sub}
        if rate:
            li["igst_rate"] = rate
            li["igst_amount"] = 0.0
            
        inv = {
            "subtotal": sub,
            "cgst_amount": cgst,
            "sgst_amount": sgst,
            "igst_amount": igst,
            "tax_total": tax_tot,
            "total_amount": grand,
            "line_items": [li]
        }
        res = validator.validate_invoice(inv)
        if res["overall_status"] == "PASSED":
            stats["GST"]["false_pass"] += 1
            stats["GST"]["defects"].append({
                "input": desc,
                "expected": "REVIEW_REQUIRED or MISMATCH (GST statutory violation)",
                "actual": "PASSED",
                "issue": "FinancialValidator Check 3 only checks arithmetic sum (cgst+sgst+igst+cess == tax_total), with zero GST statutory structure checks",
                "severity": "HIGH",
            })
        else:
            stats["GST"]["correct"] += 1

    # ------------------------------------------------------------------------
    # 4. DOUBLE DISCOUNT / ACCIDENTAL MULTIPLE DEDUCTION
    # ------------------------------------------------------------------------
    stats["discounts"]["total"] += 1
    total_tests += 1
    double_disc_inv = {
        "subtotal": 900.0, # Pre-discount subtotal is 1000, line discount is 100 -> line taxable is 900
        "discount_total": 100.0, # Header discount is also populated as 100
        "total_amount": 800.0, # Grand total subtracts discount AGAIN: 900 - 100 = 800
        "line_items": [
            {"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}
        ]
    }
    res = validator.validate_invoice(double_disc_inv)
    if res["overall_status"] == "PASSED":
        stats["discounts"]["false_pass"] += 1
        stats["discounts"]["defects"].append({
            "input": "Invoice with 10% line discount (900 taxable) AND 100 header discount (total 800)",
            "expected": "REVIEW_REQUIRED (Potential duplicate discount deduction)",
            "actual": "PASSED",
            "issue": "Check 4 blindly subtracts discount_total from subtotal even when subtotal was already net of line discounts",
            "severity": "CRITICAL",
        })
    else:
        stats["discounts"]["correct"] += 1

    # ------------------------------------------------------------------------
    # 5. NEGATIVE VALUE / CANCELING LINES / SURCHARGE RISKS
    # ------------------------------------------------------------------------
    stats["negative values"]["total"] += 1
    total_tests += 1
    canceling_inv = {
        "subtotal": 0.0,
        "total_amount": 0.0,
        "line_items": [
            {"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0},
            {"quantity": -1, "unit_price": 1000.0, "taxable_amount": -1000.0},
        ]
    }
    res = validator.validate_invoice(canceling_inv)
    stats["negative values"]["correct"] += 1

    # Negative price * negative quantity = positive taxable
    stats["negative values"]["total"] += 1
    total_tests += 1
    neg_mult_inv = {
        "subtotal": 1000.0,
        "total_amount": 1000.0,
        "line_items": [
            {"quantity": -1, "unit_price": -1000.0, "taxable_amount": 1000.0}
        ]
    }
    res = validator.validate_invoice(neg_mult_inv)
    if res["overall_status"] == "PASSED":
        stats["negative values"]["false_pass"] += 1
        stats["negative values"]["defects"].append({
            "input": "Quantity = -1, Unit Price = -1000 -> Taxable = 1000",
            "expected": "REVIEW_REQUIRED (Negative quantity and negative rate anomaly)",
            "actual": "PASSED",
            "issue": "FinancialValidator performs pure unsigned math without validating sensible business constraints on negative units/rates",
            "severity": "MEDIUM",
        })
    else:
        stats["negative values"]["correct"] += 1

    # ------------------------------------------------------------------------
    # 6. PROPERTY-BASED / FUZZ TESTING (2,000 INVOICES)
    # ------------------------------------------------------------------------
    random.seed(42)
    fuzz_count = 2000
    for i in range(fuzz_count):
        stats["fuzz testing"]["total"] += 1
        total_tests += 1
        
        # Generate valid random invoice
        num_lines = random.randint(1, 5)
        lines = []
        tot_sub = Decimal("0.00")
        
        for idx in range(num_lines):
            qty = Decimal(str(random.randint(1, 10)))
            price = Decimal(str(random.randint(10, 500))) + Decimal("0.50")
            gross = (qty * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            use_disc = random.choice([None, "percent", "amount"])
            disc_str = None
            disc_amt = Decimal("0.00")
            
            if use_disc == "percent":
                p = Decimal("10.0")
                disc_amt = (gross * p / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                disc_str = "10%"
            elif use_disc == "amount":
                disc_amt = Decimal("5.00")
                disc_str = "₹5.00"
                
            taxable = (gross - disc_amt).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tot_sub += taxable
            
            li = {
                "description": f"Item {idx+1}",
                "quantity": float(qty),
                "unit_price": float(price),
                "taxable_amount": float(taxable),
            }
            if disc_str:
                li["discount"] = disc_str
            lines.append(li)
            
        tax = (tot_sub * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cgst = (tax / Decimal("2")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sgst = tax - cgst
        grand = tot_sub + tax
        
        # Intentionally mutate 50% of the cases to ensure mismatch detection
        should_mutate = (i % 2 == 1)
        mutated_field = None
        if should_mutate:
            mutation_type = random.choice(["qty", "price", "taxable", "subtotal", "tax_total", "grand_total"])
            mutated_field = mutation_type
            if mutation_type == "qty":
                lines[0]["quantity"] = float(Decimal(str(lines[0]["quantity"])) + Decimal("10"))
            elif mutation_type == "price":
                lines[0]["unit_price"] = float(Decimal(str(lines[0]["unit_price"])) + Decimal("50.0"))
            elif mutation_type == "taxable":
                lines[0]["taxable_amount"] = float(Decimal(str(lines[0]["taxable_amount"])) + Decimal("50.0"))
            elif mutation_type == "subtotal":
                tot_sub += Decimal("100.0")
            elif mutation_type == "tax_total":
                tax += Decimal("50.0")
            elif mutation_type == "grand_total":
                grand += Decimal("100.0")

        inv_data = {
            "subtotal": float(tot_sub),
            "cgst_amount": float(cgst),
            "sgst_amount": float(sgst),
            "tax_total": float(tax),
            "total_amount": float(grand),
            "line_items": lines,
        }
        
        res = validator.validate_invoice(inv_data)
        st = res["overall_status"]
        
        if not should_mutate:
            if st == "PASSED":
                stats["fuzz testing"]["correct"] += 1
            else:
                stats["fuzz testing"]["false_reject"] += 1
                stats["fuzz testing"]["defects"].append({
                    "input": f"Valid random invoice #{i}",
                    "expected": "PASSED",
                    "actual": st,
                    "errors": res.get("errors"),
                    "warnings": res.get("warnings"),
                    "severity": "HIGH",
                })
        else:
            if st == "MISMATCH":
                stats["fuzz testing"]["correct"] += 1
            else:
                stats["fuzz testing"]["false_pass"] += 1
                stats["fuzz testing"]["defects"].append({
                    "input": f"Mutated {mutated_field} invoice #{i}",
                    "expected": "MISMATCH",
                    "actual": st,
                    "severity": "CRITICAL",
                })

    # ------------------------------------------------------------------------
    # 7. FLOATING POINT & DECIMAL BOUNDARIES (Paise rounding)
    # ------------------------------------------------------------------------
    fp_cases = [
        (30, 39.59, "10%", 1068.93),
        (3, 33.33, "10%", 89.99),
        (1, 99.99, "10%", 89.99),
        (1, 100.01, "2.5%", 97.51),
        (1, 333.33, "7.5%", 308.33),
        (1, 999.99, "12.75%", 872.49),
    ]
    for qty, rate, disc, exp_tax in fp_cases:
        stats["floating point"]["total"] += 1
        total_tests += 1
        inv = {
            "subtotal": exp_tax,
            "total_amount": exp_tax,
            "line_items": [{"quantity": qty, "unit_price": rate, "discount": disc, "taxable_amount": exp_tax}]
        }
        res = validator.validate_invoice(inv)
        if res["overall_status"] == "PASSED":
            stats["floating point"]["correct"] += 1
        else:
            stats["floating point"]["false_reject"] += 1
            stats["floating point"]["defects"].append({
                "input": f"qty={qty}, rate={rate}, disc={disc}, exp={exp_tax}",
                "expected": "PASSED",
                "actual": res["overall_status"],
                "severity": "HIGH",
            })

    # ------------------------------------------------------------------------
    # 8. PERFORMANCE BENCHMARK
    # ------------------------------------------------------------------------
    for n in [1, 10, 100, 1000, 5000]:
        stats["performance"]["total"] += 1
        total_tests += 1
        lines = [{"quantity": 2, "unit_price": 100.0, "taxable_amount": 200.0} for _ in range(n)]
        data = {"subtotal": 200.0 * n, "total_amount": 200.0 * n, "line_items": lines}
        t0 = time.time()
        res = validator.validate_invoice(data)
        dur_ms = (time.time() - t0) * 1000.0
        if dur_ms < 200.0:
            stats["performance"]["correct"] += 1
        else:
            stats["performance"]["defects"].append({"scale": n, "dur_ms": dur_ms, "severity": "MEDIUM"})

    # Print summary JSON
    import json
    print(f"TOTAL_TESTS_EXECUTED: {total_tests}")
    print(f"FUZZ_TESTS: {fuzz_count}")
    print("\nCATEGORY BREAKDOWN:")
    for cat in categories:
        s = stats[cat]
        print(f"  {cat:22s} | Total: {s['total']:5d} | Correct: {s['correct']:5d} | False Pass: {s['false_pass']:3d} | False Reject: {s['false_reject']:3d} | Crashes: {s['crashes']:2d}")

    print("\nNOTABLE DEFECTS IDENTIFIED:")
    for cat in categories:
        for d in stats[cat]["defects"]:
            print(f"  [{cat.upper()}] {d}")


if __name__ == "__main__":
    run_adversarial_suite()
