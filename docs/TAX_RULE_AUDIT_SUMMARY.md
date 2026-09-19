# SAKSHI FINANCE — TAX RULE AUDIT EXECUTIVE SUMMARY (P0 / P1 ISSUES)
**Date:** September 11, 2026  
**Purpose:** High-priority statutory compliance and accounting risk brief for CA / Leadership review.  
**Strict Restriction:** AUDIT ONLY (NO CODE MODIFIED).

---

## TOP CRITICAL (P0) STATUTORY FINDINGS

### 1. Section 393 Global `"393"` Substring Bug ([`tds_engine.py:870`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/tds_engine.py#L870))
- **Statutory Error:** Post-April 2026 transactions use `Section 393` provisions. The condition `elif "PROFESSIONAL" in sec_str or "393" in sec_str or "194J" in sec_str:` intercepts **ALL** Section 393 tables (including **Table 8(ii) Goods @ 0.1%**, **Table 7 Dividends @ 10%**, **Table 2 Rent @ 10%**, and **Section 393(2) Non-Resident @ 20%**) and defaults them to **2.0% TDS**.
- **Impact:** Gross tax withholding errors across goods, rent, dividends, and foreign vendor payments.

### 2. Purchase of Goods (194Q / Table 8(ii)) Threshold & Rate Failure
- **Statutory Error:** 
  1. Statutory rate under 194Q / Section 393(1) Table 8(ii) is **0.10%**, but backend assigned **2.0%**.
  2. 194Q legally requires **Buyer Annual Turnover > ₹10 Cr** and **Cumulative FY Purchases > ₹50 Lakhs** from the vendor. The system currently evaluates standalone goods invoices as TDS-applicable without checking cumulative FY purchase history.
- **Impact:** Erroneous cash withholding on everyday tangible goods purchases.

### 3. Silent 2.0% Universal Fallback ([`tds_engine.py:527`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/tds_engine.py#L527))
- **Statutory Error:** If an invoice section is not recognized or rate is missing, `get_effective_tds_data` executes `else: rate_float = 2.0`.
- **Impact:** Unknown or ambiguous invoices are silently forced into 2.0% TDS rather than being flagged for manual review (`REVIEW_REQUIRED`).

### 4. Zero Automatic RCM (Reverse Charge) Detection ([`itc_engine.py:944`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/itc_engine.py#L944), [`export_service.py:662`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/export_service.py#L662))
- **Statutory Error:** RCM evaluation relies 100% on explicit text strings on the invoice (e.g. `"Whether tax is payable under Reverse Charge?" == "Yes"`). Under Notification 13/2017-CT(R), **Advocate Legal Fees (SAC 9982)**, **GTA Freight (SAC 9965)**, and **Director Services** are statutory RCM supplies where the recipient MUST pay tax in cash.
- **Impact:** If a lawyer or transporter issues an invoice without printing an explicit "Reverse Charge: Yes" label, the system processes it as standard forward charge GST, causing statutory non-compliance.

---

## HIGH PRIORITY (P1) ISSUES

### 5. SAC 9982 (Legal / Accounting) Misclassified as Technical Services (2%)
- **Statutory Error:** In `model_response_adapter.py:730`, SAC `9982` is included in `is_tech_candidate`. Legal and CA/Audit fees are strictly **10.0% Professional Fees** (Section 194J(1)(a) / Section 393(1) Table 6(iii)(D)(b)).
- **Impact:** Legal and CA invoices are under-deducted at 2% instead of 10%.

### 6. GSTR-2B External API Gap
- **Statutory Error:** Section 16(2)(aa) requires invoice reflection in GSTR-2B. The backend has a deterministic multi-field matching algorithm, but lacks a live GSTN portal API connection.
- **Impact:** System relies on supplied mock/static dicts rather than live portal verification.

---

## ACTION SUMMARY TABLE

| Priority | Engine | Area | Exact Defect | Recommended Canonical Resolution |
| :---: | :---: | :---: | :---: | :---: |
| 🔴 **P0** | **TDS** | Section 393 Matching | `"393"` substring in line 870 forces 2% on all tables | Replace with exact canonical table code matching (`Table 8(ii)`, `Table 7`, `Table 6(iii)`) |
| 🔴 **P0** | **TDS** | Purchase of Goods | 2% rate & no ₹50L threshold check | Set canonical rate to 0.10%; gate on FY aggregate > ₹50L |
| 🔴 **P0** | **TDS** | Engine Fallbacks | Silent `else: rate = 2.0` | Remove silent defaults; set `rate = None`, `status = "REVIEW_REQUIRED"` |
| 🔴 **P0** | **RCM** | Auto-detection | Relies 100% on invoice print flags | Auto-detect Legal (9982), GTA (9965), Director fees from SAC/nature |
| 🟠 **P1** | **TDS** | SAC 9982 | SAC 9982 mapped to 2% tech candidate | Reassign SAC 9982 strictly to 10% Professional Fees |
| 🟠 **P1** | **ITC** | GSTR-2B | Mock/offline dependency only | Connect live GSTN GSTR-2B sync pipeline |

---
*Full detailed audit report and Master Matrix available at:*
- `docs/TAX_RULE_COVERAGE_AUDIT.md`
- `docs/TAX_RULE_MASTER_MATRIX.csv`
