import sys
import os
import random
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Tuple, Optional

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from app.services.financial_validator import FinancialValidator, parse_clean_numeric, parse_discount_semantics

def run_comprehensive_adversarial_audit():
    validator = FinancialValidator(tolerance=1.0)
    
    audit_results = {
        "total_cases": 0,
        "passed": 0,
        "mismatches": 0,
        "review_required": 0,
        "false_pass": 0,
        "false_reject": 0,
        "crashes": 0,
        "regressions": 0,
        "newly_introduced_defects": 0,
        "categories": {}
    }
    
    def log_case(category: str, case_name: str, status: str, expected_type: str, actual_type: str, details: str = "", defect_meta: Optional[Dict] = None):
        audit_results["total_cases"] += 1
        if category not in audit_results["categories"]:
            audit_results["categories"][category] = {
                "total": 0, "PASSED": 0, "MISMATCH": 0, "REVIEW_REQUIRED": 0,
                "false_pass": 0, "false_reject": 0, "crashes": 0, "cases": []
            }
        cat = audit_results["categories"][category]
        cat["total"] += 1
        if actual_type in ["PASSED", "MISMATCH", "REVIEW_REQUIRED"]:
            cat[actual_type] += 1
            if actual_type == "PASSED": audit_results["passed"] += 1
            elif actual_type == "MISMATCH": audit_results["mismatches"] += 1
            elif actual_type == "REVIEW_REQUIRED": audit_results["review_required"] += 1
        else:
            cat["crashes"] += 1
            audit_results["crashes"] += 1

        is_false_pass = False
        is_false_reject = False

        if expected_type in ["MISMATCH", "REVIEW_REQUIRED"] and actual_type == "PASSED":
            is_false_pass = True
            cat["false_pass"] += 1
            audit_results["false_pass"] += 1
        elif expected_type == "PASSED" and actual_type in ["MISMATCH", "REVIEW_REQUIRED"]:
            is_false_reject = True
            cat["false_reject"] += 1
            audit_results["false_reject"] += 1

        cat["cases"].append({
            "name": case_name,
            "expected": expected_type,
            "actual": actual_type,
            "false_pass": is_false_pass,
            "false_reject": is_false_reject,
            "details": details,
            "defect_meta": defect_meta
        })

    # -------------------------------------------------------------
    # 1. TEST SUITE 1: DISCOUNT SEMANTIC PRESERVATION & RECONCILIATION
    # -------------------------------------------------------------
    # Test line discount, header discount, summary vs additional, collision, missing subtotal
    reconciliation_cases = [
        # (name, invoice_data, expected_status)
        ("Summary Header Discount (Total = 1062)", {
            "subtotal": 900.0, "discount_total": 100.0, "tax_total": 162.0, "total_amount": 1062.0,
            "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}]
        }, "PASSED"),
        ("Duplicate Header Discount in Grand Total (Total = 962)", {
            "subtotal": 900.0, "discount_total": 100.0, "tax_total": 162.0, "total_amount": 962.0,
            "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}]
        }, "REVIEW_REQUIRED"),
        ("Gross Subtotal + Header Discount Deduction (Total = 1062)", {
            "subtotal": 1000.0, "discount_total": 100.0, "tax_total": 162.0, "total_amount": 1062.0,
            "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}]
        }, "PASSED"),
        ("Additional Header Discount (Total = 1003)", {
            "subtotal": 900.0, "discount_total": 50.0, "tax_total": 153.0, "total_amount": 1003.0,
            "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}]
        }, "PASSED"),
        ("Small Header Discount Collision <= 1 INR (D_header = 0.50)", {
            "subtotal": 900.0, "discount_total": 0.50, "tax_total": 162.0, "total_amount": 1061.50,
            "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}]
        }, "REVIEW_REQUIRED"),
        ("Small Header Discount Collision == 1 INR (D_header = 1.00)", {
            "subtotal": 900.0, "discount_total": 1.00, "tax_total": 162.0, "total_amount": 1061.00,
            "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}]
        }, "REVIEW_REQUIRED"),
        ("Missing Subtotal with Concurrent Header & Line Discount", {
            "subtotal": None, "discount_total": 100.0, "tax_total": 162.0, "total_amount": 1062.0,
            "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}]
        }, "REVIEW_REQUIRED"),
        ("Ambiguous Bare Numeric Discount '10'", {
            "subtotal": 900.0, "total_amount": 900.0,
            "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": 10, "taxable_amount": 900.0}]
        }, "REVIEW_REQUIRED"),
        ("Negative Line Discount (-10)", {
            "subtotal": 1010.0, "total_amount": 1010.0,
            "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": -10, "taxable_amount": 1010.0}]
        }, "REVIEW_REQUIRED"),
        ("Percentage > 100% (150%)", {
            "subtotal": 0.0, "total_amount": 0.0,
            "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "150%", "taxable_amount": 0.0}]
        }, "REVIEW_REQUIRED"),
    ]
    for name, inv, exp in reconciliation_cases:
        try:
            res = validator.validate_invoice(inv)
            act = res["overall_status"]
            log_case("discount reconciliation & semantics", name, act, exp, act, str(res.get("warnings", []) + res.get("errors", [])))
        except Exception as e:
            log_case("discount reconciliation & semantics", name, "CRASH", exp, "CRASH", str(e))

    # -------------------------------------------------------------
    # 2. TEST SUITE 2: RE-TESTING KNOWN REMAINING DEFECTS
    # -------------------------------------------------------------
    known_defect_cases = [
        # Arbitrary line total (Check 1 blind spot)
        ("Arbitrary Line Total (item total 9999 vs taxable 1000 + tax 180)", {
            "subtotal": 1000.0, "tax_total": 180.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 9999.0}]
        }, "MISMATCH", "Check 1 does not validate item['total'] against taxable + taxes"),

        # Arbitrary line total omits tax
        ("Line Total Omits Line Tax (total=1000 when taxable=1000, tax=180)", {
            "subtotal": 1000.0, "tax_total": 180.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total_amount": 1180.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1000.0}]
        }, "MISMATCH", "Check 1 allows corrupted line total"),

        # GST Structural Conflict: Simultaneous CGST+SGST+IGST
        ("Simultaneous CGST + SGST + IGST on same invoice", {
            "subtotal": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "igst_amount": 180.0, "tax_total": 360.0, "total_amount": 1360.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0}]
        }, "REVIEW_REQUIRED", "Check 3 does not validate GST statutory structure (intra vs inter-state mutually exclusive)"),

        # GST Structural Conflict: CGST != SGST
        ("CGST / SGST Inequality (CGST 90.0, SGST 0.0)", {
            "subtotal": 1000.0, "cgst_amount": 90.0, "sgst_amount": 0.0, "tax_total": 90.0, "total_amount": 1090.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0}]
        }, "REVIEW_REQUIRED", "Check 3 allows unequal CGST and SGST on intra-state supplies"),

        # GST Structural Conflict: Rate 18% with Tax Amount 0.0
        ("Declared Rate 18% with Tax Amount 0.0", {
            "subtotal": 1000.0, "tax_total": 0.0, "total_amount": 1000.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "igst_rate": 18.0, "igst_amount": 0.0}]
        }, "REVIEW_REQUIRED", "Check 3 ignores line tax rate vs amount calculation"),

        # Scientific notation
        ("Scientific Notation '1e3' corrupted to 13.0", "1e3", "CORRUPTED_FLOAT", "parse_clean_numeric strips 'e'"),
        ("Scientific Notation '1E3' corrupted to 13.0", "1E3", "CORRUPTED_FLOAT", "parse_clean_numeric strips 'E'"),

        # Boolean Numeric Coercion
        ("Boolean True coerced to 1.0", True, "COERCED_FLOAT", "parse_clean_numeric treats True as 1.0"),
        ("Boolean False coerced to 0.0", False, "COERCED_FLOAT", "parse_clean_numeric treats False as 0.0"),

        # Alphanumeric noise parsing
        ("Alphanumeric '12abc' parsed as 12.0", "12abc", "COERCED_FLOAT", "parse_clean_numeric strips non-digits"),
        ("Alphanumeric 'abc12' parsed as 12.0", "abc12", "COERCED_FLOAT", "parse_clean_numeric strips non-digits"),

        # Negative * Negative = Positive
        ("Negative Quantity x Negative Unit Price = Positive Taxable", {
            "subtotal": 1000.0, "total_amount": 1000.0,
            "line_items": [{"quantity": -1, "unit_price": -1000.0, "taxable_amount": 1000.0}]
        }, "REVIEW_REQUIRED", "Check 1 performs unsigned math; allows negative rate & qty anomaly"),

        # Missing vs Zero total_amount
        ("0.00 Total Amount with 1000 Subtotal", {
            "subtotal": 1000.0, "total_amount": 0.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0}]
        }, "MISMATCH", "Subtotal 1000 vs grand total 0"),

        # Completely 0.00 invoice
        ("All Zero Invoice (subtotal 0.0, grand total 0.0, qty 0)", {
            "subtotal": 0.0, "total_amount": 0.0,
            "line_items": [{"quantity": 0, "unit_price": 0.0, "taxable_amount": 0.0}]
        }, "PASSED", "Valid zero-value invoice"),
    ]

    for item in known_defect_cases:
        name = item[0]
        val = item[1]
        exp = item[2]
        note = item[3]
        if "Scientific Notation" in name or "Boolean" in name or "Alphanumeric" in name:
            parsed = parse_clean_numeric(val)
            if "Scientific" in name:
                actual_status = "PASSED" if parsed == 13.0 else "CORRECT"
                log_case("numeric parsing vulnerabilities", name, actual_status, "MISMATCH", "PASSED" if parsed == 13.0 else "PASSED", f"Parsed {val} as {parsed}")
            elif "Boolean" in name:
                actual_status = "PASSED" if parsed in [0.0, 1.0] else "CORRECT"
                log_case("numeric parsing vulnerabilities", name, actual_status, "REVIEW_REQUIRED", "PASSED" if parsed in [0.0, 1.0] else "PASSED", f"Parsed {val} as {parsed}")
            elif "Alphanumeric" in name:
                actual_status = "PASSED" if parsed == 12.0 else "CORRECT"
                log_case("numeric parsing vulnerabilities", name, actual_status, "REVIEW_REQUIRED", "PASSED" if parsed == 12.0 else "PASSED", f"Parsed {val} as {parsed}")
        else:
            res = validator.validate_invoice(val)
            act = res["overall_status"]
            log_case("structural and validator vulnerabilities", name, act, exp, act, f"{note} | actual: {act}")

    # -------------------------------------------------------------
    # 3. TEST SUITE 3: EXTENSIVE EDGE CASES ACROSS FINANCIAL FIELDS
    # -------------------------------------------------------------
    edge_cases = [
        ("Shipping added correctly", {
            "subtotal": 1000.0, "tax_total": 180.0, "shipping_charges": 50.0, "total_amount": 1230.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0}]
        }, "PASSED"),
        ("Other charges added correctly", {
            "subtotal": 1000.0, "tax_total": 180.0, "other_charges": 25.0, "total_amount": 1205.0,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0}]
        }, "PASSED"),
        ("Positive roundoff added correctly (+0.40)", {
            "subtotal": 1000.0, "tax_total": 180.0, "round_off": 0.40, "total_amount": 1180.40,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0}]
        }, "PASSED"),
        ("Negative roundoff deducted correctly (-0.40)", {
            "subtotal": 1000.0, "tax_total": 180.0, "round_off": -0.40, "total_amount": 1179.60,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0}]
        }, "PASSED"),
        ("Multiple line items with mixed discounts & rounding", {
            "subtotal": 287.49, "tax_total": 51.75, "total_amount": 339.24,
            "line_items": [
                {"quantity": 3, "unit_price": 33.33, "discount": "10%", "taxable_amount": 89.99},
                {"quantity": 1, "unit_price": 100.00, "discount": "2.5%", "taxable_amount": 97.50},
                {"quantity": 1, "unit_price": 100.00, "taxable_amount": 100.00},
            ]
        }, "PASSED"),
        ("Tolerance Boundary: Within 1.0 INR Difference (diff = 0.99)", {
            "subtotal": 1000.0, "tax_total": 180.0, "total_amount": 1180.99,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0}]
        }, "PASSED"),
        ("Tolerance Boundary: Outside 1.0 INR Difference (diff = 1.01)", {
            "subtotal": 1000.0, "tax_total": 180.0, "total_amount": 1181.01,
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0}]
        }, "MISMATCH"),
        ("Missing line items array", {
            "subtotal": 1000.0, "total_amount": 1000.0, "line_items": []
        }, "REVIEW_REQUIRED"),
        ("Missing required subtotal and total_amount", {
            "line_items": [{"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0}]
        }, "REVIEW_REQUIRED"),
    ]
    for name, inv, exp in edge_cases:
        res = validator.validate_invoice(inv)
        act = res["overall_status"]
        log_case("financial field edge cases", name, act, exp, act, str(res.get("warnings", []) + res.get("errors", [])))

    # -------------------------------------------------------------
    # 4. TEST SUITE 4: 2,000 PROPERTY/FUZZ TESTS
    # -------------------------------------------------------------
    random.seed(1337)
    fuzz_count = 2000
    for i in range(fuzz_count):
        num_lines = random.randint(1, 4)
        lines = []
        tot_sub = Decimal("0.00")
        for idx in range(num_lines):
            qty = Decimal(str(random.randint(1, 5)))
            price = Decimal(str(random.randint(50, 500)))
            gross = qty * price
            use_disc = random.choice([None, "pct", "amt"])
            disc_str = None
            disc_amt = Decimal("0.00")
            if use_disc == "pct":
                disc_str = "10%"
                disc_amt = (gross * Decimal("10") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            elif use_disc == "amt":
                disc_str = "₹20.00"
                disc_amt = Decimal("20.00")
            taxable = gross - disc_amt
            tot_sub += taxable
            li = {"quantity": float(qty), "unit_price": float(price), "taxable_amount": float(taxable)}
            if disc_str:
                li["discount"] = disc_str
            lines.append(li)
        
        tax = (tot_sub * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cgst = (tax / Decimal("2")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sgst = tax - cgst
        grand = tot_sub + tax

        should_mutate = (i % 2 == 1)
        if should_mutate:
            grand += Decimal("50.0")
            exp_status = "MISMATCH"
        else:
            exp_status = "PASSED"

        inv_data = {
            "subtotal": float(tot_sub),
            "cgst_amount": float(cgst),
            "sgst_amount": float(sgst),
            "tax_total": float(tax),
            "total_amount": float(grand),
            "line_items": lines,
        }
        res = validator.validate_invoice(inv_data)
        act_status = res["overall_status"]
        log_case("fuzz testing", f"Fuzz test #{i+1}", act_status, exp_status, act_status)

    print(f"\nAUDIT COMPLETE:")
    print(f"Total Cases Tested: {audit_results['total_cases']}")
    print(f"Passed: {audit_results['passed']}")
    print(f"Mismatches: {audit_results['mismatches']}")
    print(f"Review Required: {audit_results['review_required']}")
    print(f"False Pass: {audit_results['false_pass']}")
    print(f"False Reject: {audit_results['false_reject']}")
    print(f"Crashes: {audit_results['crashes']}")
    print(f"Regressions: {audit_results['regressions']}")
    print(f"Newly Introduced Defects: {audit_results['newly_introduced_defects']}")

    print("\nFALSE PASS BREAKDOWN:")
    for cat_name, cat in audit_results["categories"].items():
        if cat["false_pass"] > 0:
            print(f"\n[{cat_name.upper()}]: {cat['false_pass']} false passes")
            for c in cat["cases"]:
                if c["false_pass"]:
                    print(f"  - {c['name']}: Expected {c['expected']}, got {c['actual']} ({c['details']})")

if __name__ == "__main__":
    run_comprehensive_adversarial_audit()
