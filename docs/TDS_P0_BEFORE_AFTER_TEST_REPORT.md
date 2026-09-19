# TDS Section 397(2) & Section 393 Classification Hardening — Before vs After Test Report

## 1. Executive Summary

This report documents the verification and regression results for the **P0 Hardening of Section 397(2) Missing/Invalid PAN Higher-Rate TDS Logic** and **Section 393 Statutory Category Binding** under the *Income-tax Act, 2025*.

All 10 deterministic JSON test fixtures were executed against:
1. **PREVIOUS IMPLEMENTATION** (Commit `3c5c19d`): Pre-fix logic utilizing Section 206AA blanket rates, missing-PAN omissions, and text-matching heuristics.
2. **CURRENT IMPLEMENTATION** (Hardened): Authoritative statutory classification through `resolve_tds_tax_details()`, exact `category_key` binding, Section 397(2) category-specific 5% rates (`PURCHASE_OF_GOODS` & `ECOMMERCE`), 20% default higher rates, and unresolved bare Section 393 review gating.

### BEFORE FIX Summary
| Defect Area | Previous Behavior | Statutory Problem |
| :--- | :--- | :--- |
| **Purchase of Goods + Invalid PAN** | Applied blanket 20% (₹20,000 on ₹100,000) | **₹15,000 Over-deduction** (Sec 397(2)(b)(i) prescribes 5%) |
| **E-commerce + Invalid PAN** | Applied blanket 20% (₹20,000 on ₹100,000) | **₹15,000 Over-deduction** (Sec 397(2)(b)(i) prescribes 5%) |
| **Missing PAN Handling** | Treated `vendor_pan=None` as `pan_valid=True`, defaulting to normal/arbitrary rate | **Critical Compliance Risk** (failed to trigger higher withholding) |
| **Bare Section 393** | Defaulted to 10% rate without review | **Non-compliant Guesswork** (unspecified nature must require review) |
| **Goods with Valid PAN** | Fallback matched `"393"` in string and applied 10% | **100x Over-deduction** (statutory rate is 0.10%) |

### AFTER FIX Summary
| Fix Area | Current Behavior | Statutory Result |
| :--- | :--- | :--- |
| **Purchase of Goods + Missing/Invalid PAN** | Exact canonical category `PURCHASE_OF_GOODS` $\rightarrow$ 5.0% (₹5,000) | **Exact Statutory Match** under Section 397(2) Table 8(ii) |
| **E-commerce + Missing/Invalid PAN** | Exact canonical category `ECOMMERCE` $\rightarrow$ 5.0% (₹5,000) | **Exact Statutory Match** under Section 397(2) Table 8(v) |
| **Missing PAN Symmetry** | `vendor_pan=None` strictly evaluated as missing PAN | **Full Compliance** with Section 397(2) higher deduction |
| **Other Applicable Categories + Invalid PAN** | Tech Services, Prof Services, Contractors, etc. $\rightarrow$ 20.0% | **Exact Statutory Match** under Section 397(2)(b)(ii) |
| **Bare Section 393** | Flags `tds_needs_review=True`, `tds_conflict_code="TDS_AMBIGUOUS_SAC"` | **Auditable Safety Barrier** (zero default rate assumptions) |
| **Cross-Classification Defense** | "Goods" keyword in Tech/Prof invoice resolves to Tech/Prof (20%) | **Immune to Keyword Injection / Cross-classification** |

---

## 2. Before vs After Comparison Table

Base Amount for all cases: **₹100,000.00**

| Test Case | Fixture | BEFORE Rate | BEFORE TDS | AFTER Rate | AFTER TDS | Expected | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Technical + Invalid PAN** | `technical_invalid_pan.json` | 20.0% | ₹20,000.00 | **20.0%** | **₹20,000.00** | 20.0% | **PASS** |
| **2. Professional + Invalid PAN** | `professional_invalid_pan.json` | 20.0% | ₹20,000.00 | **20.0%** | **₹20,000.00** | 20.0% | **PASS** |
| **3. Goods + Invalid PAN** | `purchase_goods_invalid_pan.json` | 20.0% | ₹20,000.00 | **5.0%** | **₹5,000.00** | 5.0% | **PASS** |
| **4. E-commerce + Invalid PAN** | `ecommerce_invalid_pan.json` | 20.0% | ₹20,000.00 | **5.0%** | **₹5,000.00** | 5.0% | **PASS** |
| **5. Goods + Valid PAN** | `purchase_goods_valid_pan.json` | 10.0% | ₹10,000.00 | **0.1%** | **₹100.00** | 0.1% | **PASS** |
| **6. Technical + Missing PAN** | `technical_missing_pan.json` | 10.0% | ₹10,000.00 | **20.0%** | **₹20,000.00** | 20.0% | **PASS** |
| **7. Goods + Missing PAN** | `purchase_goods_missing_pan.json` | 10.0% | ₹10,000.00 | **5.0%** | **₹5,000.00** | 5.0% | **PASS** |
| **8. Bare Section 393 + Missing PAN** | `bare_section_393_missing_pan.json` | 10.0% | ₹10,000.00 | **None (Review)** | **None** | Review | **PASS** |
| **9. Goods Keyword + Technical** | `goods_keyword_but_technical_invalid_pan.json` | 20.0% | ₹20,000.00 | **20.0%** | **₹20,000.00** | 20.0% | **PASS** |
| **10. Goods Keyword + Professional** | `goods_keyword_but_professional_invalid_pan.json` | 20.0% | ₹20,000.00 | **20.0%** | **₹20,000.00** | 20.0% | **PASS** |

---

## 3. Business Impact Analysis

### Case 3: Purchase of Goods + Invalid PAN
- **BEFORE**: Blanket Section 206AA rate applied $\rightarrow$ 20% ($\text{₹}20,000.00$).
- **AFTER**: Canonical `PURCHASE_OF_GOODS` resolved $\rightarrow$ Section 397(2) statutory exception applied $\rightarrow$ 5% ($\text{₹}5,000.00$).
- **Impact**: **₹15,000.00 wrongful over-deduction eliminated**.

### Case 4: E-commerce + Invalid PAN
- **BEFORE**: Blanket Section 206AA rate applied $\rightarrow$ 20% ($\text{₹}20,000.00$).
- **AFTER**: Canonical `ECOMMERCE` resolved $\rightarrow$ Section 397(2) statutory exception applied $\rightarrow$ 5% ($\text{₹}5,000.00$).
- **Impact**: **₹15,000.00 wrongful over-deduction eliminated**.

### Case 5: Purchase of Goods + Valid PAN
- **BEFORE**: Loose string matching matched `"393"` in section string and assigned generic professional services rate $\rightarrow$ 10% ($\text{₹}10,000.00$).
- **AFTER**: Resolved to canonical `PURCHASE_OF_GOODS` with valid PAN $\rightarrow$ 0.10% ($\text{₹}100.00$).
- **Impact**: **₹9,900.00 wrongful over-deduction eliminated**.

### Case 6: Technical Services + Missing PAN
- **BEFORE**: Missing PAN (`None`) treated as valid, falling through to generic 10% rate ($\text{₹}10,000.00$).
- **AFTER**: Missing PAN correctly identified as `pan_missing_or_invalid`, triggering Section 397(2) 20% higher deduction ($\text{₹}20,000.00$).
- **Impact**: **Prevents ₹10,000.00 statutory under-withholding tax penalty**.

### Case 7: Purchase of Goods + Missing PAN
- **BEFORE**: Missing PAN treated as valid, falling through to 10% ($\text{₹}10,000.00$).
- **AFTER**: Missing PAN triggers Section 397(2) higher deduction for goods $\rightarrow$ 5% ($\text{₹}5,000.00$).
- **Impact**: **Prevents tax disputes and aligns withholding with statutory 5% rate**.

### Case 8: Bare Section 393 + Missing PAN
- **BEFORE**: Automatically deduced 10% ($\text{₹}10,000.00$) without checking provision or requiring review.
- **AFTER**: Unresolved Section 393 triggers `TDS_AMBIGUOUS_SAC` with `tds_needs_review=True` and `rate=None`.
- **Impact**: **Prevents incorrect automatic tax deduction on ambiguous invoices**.

### Cases 9 & 10: "Goods" in Description of Technical/Professional Services
- **BEFORE**: Could be vulnerable to keyword cross-classification.
- **AFTER**: Exact statutory clause classification prevails (`TECHNICAL_SERVICES` and `PROFESSIONAL_SERVICES`), correctly applying 20% higher rate for invalid PAN.
- **Impact**: **Complete isolation from keyword collision**.

---

## 4. Test Suite Execution & Validation

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance
plugins: asyncio-1.4.0, anyio-4.15.1

backend/tests/test_tds_p0_fixtures.py .                                  [ 1%]
backend/tests/test_stage4_journal.py ....                                [ 8%]
backend/tests/test_tds_sac_fallback_regression.py ..............         [32%]
backend/tests/test_tds_base_amount_resolution.py ...                     [37%]
backend/tests/test_tds_no_threshold.py .                                 [38%]
backend/tests/test_tds_export_single_source_of_truth.py .....            [47%]
backend/tests/test_generic_tds_zoho_mapping.py ..........                [64%]
backend/tests/test_tds_pan_higher_rate_section_397.py .............      [86%]
backend/tests/test_zoho_bill_mapping_e2e.py ........                     [100%]

======================== 59 passed, 5 warnings in 1.83s ========================
```

- **Total Test Files**: 9
- **Total Tests Run**: 59
- **Passed**: 59 (100%)
- **Failed**: 0
- **Execution Time**: 1.83 seconds
