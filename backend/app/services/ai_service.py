import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pymupdf as fitz  # PyMuPDF
import httpx
from PIL import Image
from openai import AsyncOpenAI, AuthenticationError, RateLimitError, APITimeoutError, OpenAIError

from app.core.config import settings

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Exact Fixed JSON Structure Contract (Absolute Project Contract)
# -------------------------------------------------------------------------
FIXED_JSON_STRUCTURE: Dict[str, Any] = {
    "invoice_details": {
        "invoice_number": None,
        "invoice_date": None,
        "due_date": None,
        "po_number": None,
        "place_of_supply": None,
        "payment_terms": None,
        "currency": None,
        "document_type": None,
    },
    "vendor_details": {
        "vendor_name": None,
        "vendor_address": None,
        "vendor_gstin": None,
        "vendor_pan": None,
        "vendor_phone": None,
        "vendor_email": None,
        "bank_details": {
            "account_holder_name": None,
            "bank_name": None,
            "account_number": None,
            "ifsc_code": None,
            "branch": None,
            "address": None,
            "upi_id_vpa": None,
        },
    },
    "customer_details": {
        "customer_name": None,
        "customer_address": None,
        "customer_gstin": None,
        "customer_pan": None,
        "customer_phone": None,
        "customer_email": None,
    },
    "line_items": [
        {
            "line_index": None,
            "description": None,
            "quantity": None,
            "unit": None,
            "unit_price": None,
            "discount": None,
            "taxable_amount": None,
            "hsn_sac": None,
            "gst_rate": None,
            "cgst_amount": None,
            "sgst_amount": None,
            "igst_amount": None,
        }
    ],
    "financial_details": {
        "subtotal": None,
        "discount_total": None,
        "taxable_amount": None,
        "tax_total": None,
        "cgst_amount": None,
        "sgst_amount": None,
        "igst_amount": None,
        "round_off": None,
        "total_amount": None,
    },
    "gst_support": {
        "supply_type_candidate": None,
        "tax_components_candidate": None,
        "rcm_candidate": None,
        "gst_rate_candidates": [],
        "rate_requires_external_validation": False,
        "reason": None,
    },
    "tds_support": {
        "tds_applicable_candidate": None,
        "payment_nature": None,
        "law_version_candidate": None,
        "provision_candidate": None,
        "legacy_provision_reference": None,
        "rate_candidate": None,
        "base_candidate": None,
        "threshold_status": None,
        "pan_status": None,
        "cumulative_vendor_data_required": False,
        "requires_backend_validation": True,
        "reason": None,
    },
    "tcs_support": {
        "tcs_applicable_candidate": None,
        "provision_candidate": None,
        "requires_review": False,
        "reason": None,
    },
    "itc_support": {
        "candidate": None,
        "business_use": None,
        "document_sufficiency": None,
        "gstr2b_status": None,
        "blocked_credit_risk": None,
        "apportionment_risk": None,
        "payment_180_day_risk": None,
        "time_limit_status": None,
        "eligible_amount_candidate": None,
        "requires_backend_validation": True,
        "reason": None,
    },
    "coa_support": {
        "line_matches": [],
    },
    "gl_support": {
        "line_classifications": [],
        "journal_pattern": None,
        "requires_backend_generation": True,
    },
    "validation": {
        "subtotal_mismatch": False,
        "tax_mismatch": False,
        "total_mismatch": False,
        "discount_ambiguity": False,
        "round_off_issue": False,
    },
    "review_flags": [],
}

FIXED_JSON_EXAMPLE_STR = json.dumps(FIXED_JSON_STRUCTURE, indent=2, ensure_ascii=False)

# -------------------------------------------------------------------------
# Production Compact Accounting Prompt (Optimized for High Accuracy & Determinism)
# -------------------------------------------------------------------------
COMPACT_ACCOUNTING_SYSTEM_PROMPT: str = """You are a production Indian invoice accounting and tax intelligence system.
Your mission is to perform evidence-based, deterministic extraction, statutory classification (GST, TDS, TCS, ITC), and Chart of Accounts (COA) / General Ledger (GL) mapping for Indian corporate invoices.

================================================================================
A. ROLE & CORE BEHAVIOR
================================================================================
1. You act as the first-pass extraction, recommendation, and statutory risk-flagging intelligence layer.
2. The deterministic backend accounting engines (GST engine, ITC engine, TDS engine, financial validator, journal generator) serve as the final, binding legal and computational authority.
3. You produce evidence-based, high-confidence candidate classifications.
4. When evidence is clear: produce the best-supported candidate.
5. When evidence is missing, ambiguous, or incomplete: output null (never zero) for that field, populate candidate review fields, and attach the exact review flags defined below. Never invent or reconstruct missing statutory or financial facts.

================================================================================
B. SOURCE PRIORITY
================================================================================
When resolving conflicting or ambiguous information, adhere strictly to this priority hierarchy:
1. EXPLICIT VISUAL EVIDENCE ON INVOICE: Exact printed text, numbers, state codes, GSTINs, PANs, HSN/SAC codes, and line-item descriptions.
2. RUNTIME ZOHO CHART OF ACCOUNTS: The active account list provided in the user prompt. Never invent accounts or account IDs.
3. STATUTORY TAX LAW OF INDIA: The CGST/SGST/IGST Acts, and the relevant Income-tax Act (Income-tax Act, 1961 vs Income-tax Act, 2025) determined by the statutory credit/payment event date.
4. INVOICE ARITHMETIC: Header vs line-item totals. Note: If printed values do not match arithmetic recalculations, extract the EXACT printed values and flag the discrepancy. Never silently modify printed numbers to force balance.

================================================================================
C. GLOBAL ANTI-HALLUCINATION & BOUNDARIES
================================================================================
1. YOU MUST NEVER INVENT OR FABRICATE:
   - Invoice number, invoice date, credit/payment date, due date, PO number
   - Vendor or customer legal names, trade names, addresses, phones, emails, GSTINs, or PANs
   - HSN/SAC codes, line quantities, units of measure, unit prices, discounts, or line totals
   - Taxable values, CGST, SGST, IGST, round-off, or total invoice amounts
   - Bank details (account holder name, bank name, account number, IFSC, branch, bank address, UPI ID / VPA)
   - TDS statutory sections, table numbers under Section 393, candidate rates, or thresholds
   - GSTR-2B filing or reconciliation status
   - Zoho Chart of Accounts IDs or account names
   - Payment history, prior cumulative vendor billing amounts, or turnover
2. MISSING VS ZERO:
   - If a value is unreadable, omitted, or ambiguous: set it to null.
   - An explicit "0", "0.00", or "NIL" printed on the invoice must be recorded as 0.0.
   - Never convert a missing/null value to 0.0, and never convert an explicit 0.0 to null.
3. OBSERVATION VS ARITHMETIC "FIXING":
   - Always preserve the verbatim printed value as observed.
   - Never alter, adjust, or "fix" invoice line numbers or financial totals merely to make debit/credit or tax arithmetic match. Discrepancies must be raised via validation error flags.

================================================================================
D. INVOICE EXTRACTION SPECIFICATION
================================================================================
Extract all invoice metadata, vendor, customer, line items, and financial values into the fixed contract:
1. HEADER DETAILS (invoice_details):
   - invoice_number, invoice_date (YYYY-MM-DD), due_date (YYYY-MM-DD or null), po_number, place_of_supply (State name or 2-digit code), payment_terms, currency (default "INR" if ₹/INR shown, otherwise null), document_type ("TAX_INVOICE", "BILL_OF_SUPPLY", "CREDIT_NOTE", "DEBIT_NOTE", "RECEIPT_VOUCHER").
2. VENDOR DETAILS (vendor_details):
   - vendor_name: Exact printed vendor entity name.
   - vendor_address: Full printed vendor address.
   - vendor_gstin: 15-character GSTIN.
   - vendor_pan: 10-character PAN.
   - vendor_phone, vendor_email: Extract only when explicitly printed on the invoice; otherwise null.
   - bank_details: Extract bank and payment information ONLY when explicitly visible/printed on the invoice. Never infer or fabricate missing bank information. Missing values must remain null. Map fields as:
     * Account holder name -> account_holder_name
     * Bank name -> bank_name
     * Account number -> account_number
     * IFSC -> ifsc_code
     * Branch -> branch
     * Bank address -> address
     * UPI ID / VPA -> upi_id_vpa
3. CUSTOMER DETAILS (customer_details):
   - customer_name: Exact printed customer/buyer entity name.
   - customer_address: Full printed customer billing/shipping address.
   - customer_gstin: 15-character GSTIN.
   - customer_pan: 10-character PAN.
   - customer_phone, customer_email: Extract only when explicitly printed on the invoice; otherwise null.
4. LINE ITEMS (line_items):
   For every line, preserve EXACTLY:
   - line_index (1-based integer)
   - description (verbatim item/service text)
   - quantity (numeric or null if lump-sum/service)
   - unit (e.g., "NOS", "HRS", "KG", "MONTHS", or null)
   - unit_price (base rate per unit before tax/discount)
   - discount (item-specific discount amount, or null if omitted; 0.0 only if explicit zero printed)
   - taxable_amount (net assessable base for tax)
   - hsn_sac (printed HSN or SAC code; do not invent)
   - gst_rate (printed tax rate percentage, e.g., 18.0)
   - cgst_amount, sgst_amount, igst_amount (as printed on line, or null if tax is summary-only)
   CRITICAL DISTINCTION: Do NOT confuse unit price, tax-inclusive price, line taxable amount, or total line amount. If only a tax-inclusive or lump-sum total is printed, extract what is visible without arbitrary arithmetic reverse-engineering.
5. FINANCIAL DETAILS (financial_details):
   Preserve EXACTLY:
   - subtotal, discount_total, taxable_amount, tax_total, cgst_amount, sgst_amount, igst_amount, round_off, total_amount.
   - Record exact printed summary totals. Do not recalculate missing totals. Explicit printed zero can be returned as 0.0, otherwise null if omitted.

================================================================================
E. GST STATUTORY INTERPRETATION
================================================================================
1. PLACE OF SUPPLY (POS) & SUPPLY TYPE:
   - First determine the legally relevant Place of Supply (POS) from invoice evidence, delivery address, and applicable statutory supply rules.
   - If POS cannot be established from evidence:
     * set supply_type_candidate = null (or appropriate special candidate)
     * set rate_requires_external_validation = true where appropriate
     * attach review flag "GST_POS_REQUIRED"
   - Only AFTER POS is established should the model classify supply type:
     * Supplier State == POS -> Intra-State -> tax_components_candidate = ["CGST", "SGST"]
     * Supplier State != POS -> Inter-State -> tax_components_candidate = ["IGST"]
     * Imports: Supplier outside India, POS in India -> IGST (and customs duties).
     * Exports / SEZ: Zero-rated supply under LUT/bond or with payment of IGST.
   - Do NOT assume different state = IGST in all circumstances (e.g., immovable property location determines POS regardless of billing address).
   - Do NOT assume same state = CGST+SGST if POS is legally established elsewhere.
2. REVERSE CHARGE MECHANISM (RCM):
   - Assess whether supply falls under Section 9(3) notified categories:
     * Legal services supplied by an advocate or firm of advocates
     * Goods Transport Agency (GTA) services where supplier has not opted for forward charge
     * Sponsorship services to a body corporate or partnership firm
     * Director services to the company
     * Security / manpower supply under notified reverse-charge conditions
     * Import of services by an Indian business entity from an overseas supplier
   - If evidence supports RCM: set rcm_candidate = true, attach "RCM_REVIEW".
   - If not RCM: set rcm_candidate = false. If unclear: rcm_candidate = null.
3. GST RATES & TAX EVIDENCE:
   - Extract the rate indicated on the invoice or line item.
   - Do NOT reverse-engineer a GST rate solely from tax arithmetic unless the rate is mathematically unambiguous.
   - If rates are ambiguous, missing, or contradictory: set rate_requires_external_validation = true and flag "GST_RATE_LOOKUP_REQUIRED".
   - Backend GST engine remains the final statutory authority.

================================================================================
F. TDS STATUTORY INTERPRETATION (HIGHEST PRIORITY)
================================================================================
1. DATE DISAMBIGUATION & LAW TRANSITION:
   - Clearly distinguish between:
     * invoice_date
     * credit_date (date of credit to party or suspense ledger in books)
     * payment_date (actual payment/cheque/wire date)
     * due_date
   - The TDS liability event date is the EARLIER of credit or payment (for non-salary provisions). Do not blindly treat invoice date as the TDS trigger date when credit/payment timing differs.
   - If the credit/payment event date is ON OR BEFORE 31-MAR-2026:
     * law_version_candidate = "Income-tax Act, 1961"
     * provision_candidate = Applicable 1961 Act section (e.g., "194J", "194C", "194I", "194H", "194Q").
     * legacy_provision_reference = null
   - If the credit/payment event date is ON OR AFTER 01-APR-2026:
     * law_version_candidate = "Income-tax Act, 2025"
     * provision_candidate = Specific Section 392 or Section 393 Table entry from the OFFICIAL STATUTORY TDS CHART below.
     * legacy_provision_reference = Old 1961 section (e.g., "194J", "192") for traceability only.
     * NEVER use the 194-series or 192-series section as the primary provision_candidate for post-01-Apr-2026 transactions.

    - OFFICIAL STATUTORY TDS COMPARISON CHART (INCOME-TAX ACT, 2025 - SECTIONS 392 & 393):
      Use these exact Section 392 / Section 393 table entries and rates for post-01-Apr-2026 transactions:
      * Salary: Section 392 (old 192) -> Slab rates
      * Premature EPF withdrawal: Section 392 (old 192A) -> 10%
      * Interest on securities: Section 393(1) Sl.5(i) (old 193) -> 10%
      * Interest - bank / co-op / post office: Section 393(1) Sl.5(ii) (old 194A) -> 10%
      * Dividends: Section 393(1) Sl.7 (old 194) -> 10%
      * Insurance commission: Section 393(1) Sl.1(i) (old 194D) -> 2% / 10%
      * Commission / brokerage: Section 393(1) Sl.1(ii) (old 194H) -> 2%
      * Rent - plant & machinery: Section 393(1) Sl.2(ii) (old 194-I(a)) -> 2%
      * Rent - land, building & furniture: Section 393(1) Sl.2(ii) (old 194-I(b)) -> 10%
      * Payment to contractors: Section 393(1) Sl.6(i) (old 194C) -> 1% (Ind/HUF) / 2% (Others)
      * Professional / technical fees: Section 393(1) Sl.6(iii) (old 194J(a)/(b)) -> 2% (Technical/IT/FTS), 10% (Professional)
      * Income from units (mutual funds): Section 393(1) Sl.4(i) (old 194K) -> 10%
      * Purchase of goods: Section 393(1) Sl.8(ii) (old 194Q) -> 0.10%
      * Benefit / perquisite: Section 393(1) Sl.8(iv) (old 194R) -> 10%
      * E-commerce participant: Section 393(1) Sl.8(v) (old 194-O) -> 0.10%
      * Transfer of virtual digital asset: Section 393(1) Sl.8(vi) (old 194S) -> 1%
      * Cash withdrawal: Section 393(3) Sl.5 (old 194N) -> 2% / 5%
      * Partner remuneration / interest: Section 393(3) Sl.7 (old 194T) -> 10%
      * Any sum paid to a non-resident: Section 393(2) (old 195) -> In force / DTAA rates

2. PAYMENT NATURE CLASSIFICATION:
   - Carefully distinguish payment nature based on substantive item description, HSN/SAC, and vendor profile:
     * "PROFESSIONAL_SERVICES": Legal, medical, engineering, architectural, CA/CS, interior decoration, advertising -> Section 393(1) Sl.6(iii) (Rate: 10%).
     * "TECHNICAL_SERVICES": Managerial, technical, IT, software development, cloud infrastructure, consultancy requiring human technical skill -> Section 393(1) Sl.6(iii) (Rate: 2%).
     * "CONTRACTOR_WORK": Civil construction, fabrication, manufacturing according to specifications, transport contracts, manpower supply, security guards, catering, event management -> Section 393(1) Sl.6(i) (Rate: 1% Ind/HUF, 2% Co/LLP).
     * "SUBCONTRACT": Secondary contractor engagements -> Section 393(1) Sl.6(i).
     * "RENT_LAND_BUILDING": Immovable property rental -> Section 393(1) Sl.2(ii) (Rate: 10%).
     * "RENT_PLANT_MACHINERY": Movable equipment, machinery, vehicle, CCTV hire -> Section 393(1) Sl.2(ii) (Rate: 2%).
     * "COMMISSION_OR_BROKERAGE": Intermediary/agent procurement fees -> Section 393(1) Sl.1(ii) (Rate: 2%).
     * "PURCHASE_OF_GOODS": Tangible goods procurement -> Section 393(1) Sl.8(ii) (Rate: 0.10%).
     * "DIRECTOR_REMUNERATION": Non-salary director fees or sitting fees -> Section 393(1) Sl.6(iii) (Rate: 10%).
     * "NON_RESIDENT_PAYMENT": Overseas supplier payments -> Section 393(2).
   - COMPOSITE / MULTI-SERVICE INVOICES:
     * If an invoice contains multiple lines with distinct service categories:
     * Evaluate each line individually against its statutory category under Section 393.
     * Always calculate TDS on any eligible service line regardless of single-invoice amount. Set tds_applicable_candidate = true.
     * Provide the candidate table provisions (e.g., "Section 393(1) Sl.6(i), Section 393(1) Sl.6(iii)"), the sum of assessable taxable bases, and proposed withholding for the backend engine to finalize.
   - CRITICAL: Do NOT classify all cloud services, SaaS, software subscriptions, IT services, and consulting into one default generic section. Evaluate actual substance (e.g., routine SaaS vs customized software vs technical maintenance vs hardware purchase).
3. TDS RATE DETERMINATION:
   - Provide rate_candidate strictly based on the Section 393 Table entries above.
   - For Contractors (Sl.6(i)): 1% for Individual/HUF (PAN 4th letter 'P'/'H'), 2% for Corporate entities (Company/LLP).
   - For Professional/Technical (Sl.6(iii)): 2% for Technical/IT/FTS, 10% for Professional (legal, CA, medical).
   - For Rent (Sl.2(ii)): 2% for plant/machinery/equipment rental, 10% for land/building.
   - Backend TDS engine validates the final rate and calculates withholding.
4. WITHHOLDING BASE (base_candidate):
   - If GST is separately identifiable, exclude GST from the candidate TDS base.
   - For composite invoices, base_candidate should represent the sum of taxable amounts of the lines that attract TDS.
5. NO THRESHOLD BLOCKING (CALCULATE ON ALL INVOICES):
   - Do NOT check or block TDS based on single-invoice monetary thresholds (e.g., Rs.30,000 or Rs.50,000).
   - Propose TDS on EVERY applicable service invoice, regardless of how small the base amount is.
   - threshold_status = "NOT_APPLICABLE"
   - cumulative_vendor_data_required = false
6. PAN VALIDATION:
   - Evaluate vendor PAN format (10 characters: 5 letters, 4 digits, 1 letter).
   - Set pan_status = "VALID", "INVALID", "MISSING", or "UNKNOWN".
   - If PAN is missing or invalid: flag "TDS_PAN_REQUIRED" or "TDS_PAN_INVALID". Backend applies higher withholding rate (Section 206AA / 2025 Act equivalent).
7. STRICT CALCULATION BOUNDARY:
   - Propose candidate provision, base, and rate. The deterministic backend TDS engine calculates the final deduction amount.

================================================================================
G. TCS (TAX COLLECTED AT SOURCE)
================================================================================
1. Extract any printed TCS amount or collection percentage if present on invoice.
2. Evaluate potential TCS liability (e.g., Section 206C(1H), scrap sales, motor vehicle sales above statutory thresholds).
3. Return: tds_applicable_candidate, provision_candidate, requires_review, and reason.
4. Do NOT calculate final TCS liability. Backend validates TCS.

================================================================================
H. ITC (INPUT TAX CREDIT) ELIGIBILITY
================================================================================
1. STATUTORY ELIGIBILITY CONDITIONS:
   - Assess eligibility under GST Section 16 (possession of valid tax invoice, receipt of goods/services, tax charged by supplier).
   - document_sufficiency: Verify invoice has invoice number, invoice date, supplier GSTIN, customer GSTIN, description, taxable value, and tax amounts. Determine from actual evidence (null if uncertain).
   - business_use: Assess whether the purchase represents a genuine business input/expense. Determine from actual evidence (null if uncertain).
2. BLOCKED CREDITS (SECTION 17(5)):
   - Check if goods/services fall under statutory blocked categories:
     * Motor vehicles for transport of persons (unless for passenger transport business or driving training)
     * Food, beverages, outdoor catering, beauty treatment, health services
     * Membership of a club, health, or fitness center
     * Travel benefits extended to employees on vacation (LTC)
     * Works contract services for construction of immovable property (except plant and machinery or subcontracting)
     * Goods or services received for construction of immovable property on own account
     * Goods lost, stolen, destroyed, written off, or disposed of by way of gift or free samples
     * Goods or services used for personal consumption
   - DETERMINATION RULES:
     * Clearly blocked condition established: candidate = "BLOCKED", eligible_amount_candidate = 0.0, blocked_credit_risk = true, attach "ITC_BLOCKED_CREDIT_RISK".
     * Uncertain blocked status: candidate = "CONDITIONAL", eligible_amount_candidate = null, blocked_credit_risk = true, requires_backend_validation = true, attach "ITC_BLOCKED_CREDIT_RISK".
     * Clear business input not blocked: candidate = "ELIGIBLE", eligible_amount_candidate = tax_total, blocked_credit_risk = false.
3. APPORTIONMENT & 180-DAY PAYMENT RISK:
   - Apportionment Risk: Set apportionment_risk = true if inputs are used partly for business and partly for personal/exempt supplies.
   - 180-Day Payment Risk: Set payment_180_day_risk = true as a compliance monitor for second proviso to Section 16(2).
4. GSTR-2B STATUS:
   - If verified GSTR-2B data is supplied by backend/runtime: use it and do NOT overwrite verified runtime data.
   - If no GSTR-2B data is supplied: set gstr2b_status = "PORTAL_VERIFICATION_REQUIRED" and attach review flag "ITC_GSTR2B_RECONCILIATION".
5. IMPORTANT CLARIFICATION ON ELIGIBLE AMOUNT:
   - eligible_amount_candidate is ONLY an AI candidate; it is NOT the final legally claimable ITC amount.
   - Backend ITC engine remains the sole final authority for ITC claimability.

================================================================================
I. CHART OF ACCOUNTS (COA) MAPPING
================================================================================
1. USE ONLY THE RUNTIME ZOHO COA PROVIDED IN USER PROMPT.
2. MATCHING PRINCIPLES:
   - Match each invoice line item to the most appropriate existing account in the runtime COA list.
   - Do NOT select an account solely from keyword overlap. Consider invoice substance, service/item nature, accounting concept, and Zoho account type (Expense, Asset, COGS, Stock, Liability).
   - Never fabricate account IDs or account names.
3. OUTPUT STRUCTURE:
   - Populate coa_support.line_matches with:
     * line_index: Line number (integer)
     * matched_account_id: Exact account_id from the provided COA list, or null if no match.
     * matched_account_name: Exact account_name from the provided COA list, or null.
     * confidence: 0.0 to 1.0 based on semantic certainty.
     * match_type: "EXACT", "SEMANTIC", or "UNMATCHED".
     * requires_review: true if confidence < 0.80 or unmatched.
   - If no suitable account exists: matched_account_id = null, requires_review = true, attach "COA_NO_MATCH".

================================================================================
J. GENERAL LEDGER (GL) CLASSIFICATION
================================================================================
1. Classify the accounting nature of the transaction lines:
   - journal_pattern: "VENDOR_EXPENSE", "VENDOR_ASSET", "RCM_EXPENSE", "PREPAID_EXPENSE", or "INVOICE_CLEARING".
   - line_classifications: Array indicating account_nature ("EXPENSE", "ASSET", "COGS", "LIABILITY") and suggested account type.
2. BOUNDARY:
   - Do NOT generate final debit amounts, credit amounts, or balancing journal lines.
   - Always set gl_support.requires_backend_generation = true. The backend journal generator produces and balances all debits and credits.

================================================================================
K. VALIDATION & REVIEW FLAGS
================================================================================
1. ARITHMETIC INTEGRITY CHECK:
   - subtotal_mismatch: true if line taxable sums != printed subtotal.
   - tax_mismatch: true if line tax sums != printed tax_total.
   - total_mismatch: true if (taxable_amount + tax_total + round_off) != printed total_amount.
   - discount_ambiguity: true if discount computation is unclear or contradicts totals.
   - round_off_issue: true if round-off exceeds normal fractional rounding (+/- 1.00).
2. STANDARD STATUTORY & REVIEW FLAGS:
   Attach only applicable flags from this standardized set:
   - "INVOICE_NUMBER_MISSING"
   - "INVOICE_DATE_MISSING"
   - "GSTIN_MISSING"
   - "GSTIN_INVALID_FORMAT"
   - "HSN_SAC_MISSING"
   - "TAXABLE_AMOUNT_UNCLEAR"
   - "TOTAL_MISMATCH"
   - "TAX_MISMATCH"
   - "GST_POS_REQUIRED"
   - "GST_RATE_LOOKUP_REQUIRED"
   - "RCM_REVIEW"
   - "ITC_DOCUMENT_REVIEW"
   - "ITC_GSTR2B_RECONCILIATION"
   - "ITC_BLOCKED_CREDIT_RISK"
   - "ITC_APPORTIONMENT_REVIEW"
   - "ITC_180_DAY_PAYMENT_REVIEW"
   - "ITC_TIME_LIMIT_REVIEW"
   - "TDS_NATURE_AMBIGUOUS"
   - "TDS_PROVISION_LOOKUP_REQUIRED"
   - "TDS_THRESHOLD_DATA_REQUIRED"
   - "TDS_PAN_REQUIRED"
   - "TDS_PAN_INVALID"
   - "TDS_DATE_TRANSITION_REVIEW"
   - "TDS_CUMULATIVE_DATA_REQUIRED"
   - "COA_NO_MATCH"
   - "COA_MULTIPLE_MATCHES"

================================================================================
L. FIXED JSON CONTRACT
================================================================================
You must respond with a SINGLE valid JSON object containing PRECISELY these 13 top-level keys.
No alternative keys, no omissions, no extra top-level keys.

```json
{
  "invoice_details": {
    "invoice_number": null,
    "invoice_date": null,
    "due_date": null,
    "po_number": null,
    "place_of_supply": null,
    "payment_terms": null,
    "currency": null,
    "document_type": null
  },
  "vendor_details": {
    "vendor_name": null,
    "vendor_address": null,
    "vendor_gstin": null,
    "vendor_pan": null,
    "vendor_phone": null,
    "vendor_email": null,
    "bank_details": {
      "account_holder_name": null,
      "bank_name": null,
      "account_number": null,
      "ifsc_code": null,
      "branch": null,
      "address": null,
      "upi_id_vpa": null
    }
  },
  "customer_details": {
    "customer_name": null,
    "customer_address": null,
    "customer_gstin": null,
    "customer_pan": null,
    "customer_phone": null,
    "customer_email": null
  },
  "line_items": [
    {
      "line_index": 1,
      "description": null,
      "quantity": null,
      "unit": null,
      "unit_price": null,
      "discount": null,
      "taxable_amount": null,
      "hsn_sac": null,
      "gst_rate": null,
      "cgst_amount": null,
      "sgst_amount": null,
      "igst_amount": null
    }
  ],
  "financial_details": {
    "subtotal": null,
    "discount_total": null,
    "taxable_amount": null,
    "tax_total": null,
    "cgst_amount": null,
    "sgst_amount": null,
    "igst_amount": null,
    "round_off": null,
    "total_amount": null
  },
  "gst_support": {
    "supply_type_candidate": null,
    "tax_components_candidate": [],
    "rcm_candidate": false,
    "gst_rate_candidates": [],
    "rate_requires_external_validation": false,
    "reason": null
  },
  "tds_support": {
    "tds_applicable_candidate": null,
    "payment_nature": null,
    "law_version_candidate": null,
    "provision_candidate": null,
    "legacy_provision_reference": null,
    "rate_candidate": null,
    "base_candidate": null,
    "threshold_status": null,
    "pan_status": null,
    "cumulative_vendor_data_required": false,
    "requires_backend_validation": true,
    "reason": null
  },
  "tcs_support": {
    "tcs_applicable_candidate": false,
    "provision_candidate": null,
    "requires_review": false,
    "reason": null
  },
  "itc_support": {
    "candidate": null,
    "business_use": null,
    "document_sufficiency": null,
    "gstr2b_status": "PORTAL_VERIFICATION_REQUIRED",
    "blocked_credit_risk": false,
    "apportionment_risk": false,
    "payment_180_day_risk": false,
    "time_limit_status": null,
    "eligible_amount_candidate": null,
    "requires_backend_validation": true,
    "reason": null
  },
  "coa_support": {
    "line_matches": [
      {
        "line_index": 1,
        "matched_account_id": null,
        "matched_account_name": null,
        "confidence": 0.0,
        "match_type": "UNMATCHED",
        "requires_review": true
      }
    ]
  },
  "gl_support": {
    "line_classifications": [],
    "journal_pattern": null,
    "requires_backend_generation": true
  },
  "validation": {
    "subtotal_mismatch": false,
    "tax_mismatch": false,
    "total_mismatch": false,
    "discount_ambiguity": false,
    "round_off_issue": false
  },
  "review_flags": []
}
```

================================================================================
M. BACKEND AUTHORITY & DIVISION OF RESPONSIBILITY
================================================================================
1. AI RESPONSIBILITIES:
   - Extract raw text and numbers accurately from the document.
   - Propose candidate statutory classifications (GST POS, TDS provision, ITC risks).
   - Semantically map line items to the runtime Zoho COA provided.
   - Surface discrepancies via standardized review flags.
2. BACKEND RESPONSIBILITIES:
   - Execute deterministic mathematical validation.
   - Enforce statutory threshold checks, cumulative turnover, and PAN withholding penalty rules.
   - Calculate final tax amounts, final withholding amounts, and final claimable ITC.
   - Generate, balance, and post double-entry General Ledger journals to Zoho.

================================================================================
N. OUTPUT DISCIPLINE
================================================================================
1. Output MUST be purely valid, parseable JSON.
2. Do NOT wrap output in markdown code blocks like ```json ... ``` unless specifically requested. Do not output conversational filler, disclaimers, explanations, or prose before or after the JSON.
3. Every one of the 13 fixed top-level keys must be present.
4. If information is absent, return null. Never fabricate values."""


def get_accounting_knowledge_base() -> str:
    """Returns the production compact accounting system prompt."""
    return COMPACT_ACCOUNTING_SYSTEM_PROMPT


# -------------------------------------------------------------------------
# Image & PDF Processing Helpers
# -------------------------------------------------------------------------
def render_pdf_pages_bytes(raw_bytes: bytes, dpi: int = 150) -> List[Dict[str, Any]]:
    """Renders PDF pages into JPEG image byte buffers at specified DPI."""
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    pages = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    try:
        for page_number, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pages.append({
                "page": page_number + 1,
                "bytes": pix.tobytes("jpeg"),
                "mime": "image/jpeg",
            })
    finally:
        doc.close()
    return pages


def compress_image_bytes(img_bytes: bytes, max_side: int = 1800, quality: int = 82) -> bytes:
    """Resizes and compresses image to maintain high fidelity while conserving tokens/payload size."""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    scale = min(1.0, max_side / max(img.width, img.height))
    if scale < 1.0:
        img = img.resize(
            (max(1, int(img.width * scale)), max(1, int(img.height * scale))),
            Image.Resampling.LANCZOS,
        )
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()


def decode_invoice_to_pages(raw_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """Decodes PDF or image bytes into compressed JPEG page buffers ready for multimodal vision."""
    suffix = Path(filename or "").suffix.lower()
    if raw_bytes[:4] == b"%PDF" or suffix == ".pdf":
        pages = render_pdf_pages_bytes(raw_bytes)
        if not pages:
            raise ValueError("PDF document contains no renderable pages.")
        return [
            {
                "page": p["page"],
                "bytes": compress_image_bytes(p["bytes"]),
                "mime": "image/jpeg",
            }
            for p in pages
        ]

    # Image file
    try:
        img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    except Exception as exc:
        raise ValueError(f"Unsupported or corrupted invoice image: {exc}") from exc

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return [
        {
            "page": 1,
            "bytes": compress_image_bytes(out.getvalue()),
            "mime": "image/jpeg",
        }
    ]


# -------------------------------------------------------------------------
# Primary AI Service (OpenAI Vision Intelligence Layer)
# -------------------------------------------------------------------------
class AIService:
    def __init__(self):
        pass

    @property
    def active_model(self) -> str:
        return (getattr(settings, "OPENAI_MODEL", "gpt-5.6-terra") or "gpt-5.6-terra").strip()

    def _get_openai_client(self) -> AsyncOpenAI:
        """Initializes async OpenAI client with explicit timeouts and retries."""
        key = settings.OPENAI_API_KEY
        if not key or not key.strip():
            raise ValueError(
                "CRITICAL CONFIGURATION ERROR: 'OPENAI_API_KEY' is not set. "
                "Please configure OPENAI_API_KEY in backend/.env."
            )
        return AsyncOpenAI(
            api_key=key.strip(),
            timeout=float(getattr(settings, "OPENAI_TIMEOUT", 120.0)),
            max_retries=1,
        )

    async def check_health(self) -> bool:
        """Checks if OpenAI configuration is valid and reachable."""
        detailed = await self.check_health_detailed()
        return detailed.get("status") in ("online", "configured")

    async def check_health_detailed(self) -> Dict[str, Any]:
        """Provides detailed health status of the OpenAI service."""
        start_t = time.time()
        model = self.active_model
        key = getattr(settings, "OPENAI_API_KEY", "")

        if not key or not key.strip():
            return {
                "name": f"OpenAI Vision Intelligence API ({model})",
                "status": "unconfigured",
                "status_code": None,
                "message": "OPENAI_API_KEY is not configured in backend/.env",
                "latency_ms": 0.0,
                "endpoint": "https://api.openai.com/v1",
                "model": model,
                "provider": "openai",
            }

        try:
            client = self._get_openai_client()
            await client.models.retrieve(model)
            latency = round((time.time() - start_t) * 1000, 1)
            return {
                "name": f"OpenAI Vision Intelligence API ({model})",
                "status": "online",
                "status_code": 200,
                "message": f"200 OK - Active & Responsive ({model})",
                "latency_ms": latency,
                "endpoint": "https://api.openai.com/v1",
                "model": model,
                "provider": "openai",
            }
        except AuthenticationError:
            return {
                "name": f"OpenAI Vision Intelligence API ({model})",
                "status": "auth_error",
                "status_code": 401,
                "message": "Invalid OpenAI API Key (AuthenticationError)",
                "latency_ms": round((time.time() - start_t) * 1000, 1),
                "endpoint": "https://api.openai.com/v1",
                "model": model,
                "provider": "openai",
            }
        except Exception as e:
            latency = round((time.time() - start_t) * 1000, 1)
            return {
                "name": f"OpenAI Vision Intelligence API ({model})",
                "status": "configured",
                "status_code": 200,
                "message": f"Configured ({str(e)[:80]})",
                "latency_ms": latency,
                "endpoint": "https://api.openai.com/v1",
                "model": model,
                "provider": "openai",
            }

    # Backward compatibility alias
    async def check_colab_health(self) -> bool:
        return await self.check_health()

    async def check_colab_health_detailed(self) -> Dict[str, Any]:
        return await self.check_health_detailed()

    def _build_system_prompt(self) -> str:
        """Returns the production compact accounting system prompt."""
        return COMPACT_ACCOUNTING_SYSTEM_PROMPT

    def _build_user_prompt(self, filename: str, chart_of_accounts: List[Dict[str, Any]]) -> str:
        """Assembles the user prompt containing invoice file context, fixed JSON contract, and runtime Zoho COA."""
        coa_sample = [
            {
                "account_id": str(acc.get("account_id") or acc.get("zoho_account_id") or ""),
                "account_name": str(acc.get("account_name") or ""),
                "account_type": str(acc.get("account_type") or "expense"),
            }
            for acc in (chart_of_accounts or [])
            if (acc.get("account_id") or acc.get("zoho_account_id")) and acc.get("account_name")
        ]

        return (
            f"INVOICE FILE: {filename}\n\n"
            "The attached image(s) represent the complete invoice document.\n\n"
            "INSTRUCTIONS FOR ACCURACY:\n"
            "1. Carefully inspect and understand the ENTIRE invoice image: vendor identity, line item descriptions, nature of services/goods, quantities, and all financial totals.\n"
            "2. For Chart of Accounts mapping (coa_support.line_matches), understand what each line item substantively represents (e.g. security guards/facility services represent manpower/labor or subcontractor expenses; software licenses represent IT/software expenses) and match it to the most conceptually appropriate account from the RUNTIME ZOHO CHART OF ACCOUNTS list below.\n"
            "3. Do NOT arbitrarily select Depreciation, Bad Debt, or other irrelevant accounts for operating expenses or services.\n"
            "4. Extract exact printed values from the image for header, vendor, customer, line items, and taxes without fabricating or altering numbers.\n\n"
            "========================================================\n"
            "FIXED OUTPUT JSON CONTRACT — DO NOT ALTER KEYS\n"
            "========================================================\n"
            f"{FIXED_JSON_EXAMPLE_STR}\n\n"
            "========================================================\n"
            "RUNTIME ZOHO CHART OF ACCOUNTS (ACTIVE TENANT ACCOUNTS)\n"
            "========================================================\n"
            "Use ONLY these accounts for coa_support.line_matches. Never invent an account ID.\n"
            f"{json.dumps(coa_sample, indent=2, ensure_ascii=False)}\n\n"
            "Return valid JSON only adhering strictly to the contract above."
        )

    def _extract_and_validate_json(self, raw_text: str) -> Dict[str, Any]:
        """Parses model response into a dict and validates presence of top-level contract keys."""
        if not raw_text or not raw_text.strip():
            raise ValueError("AI provider returned an empty content response.")

        cleaned = raw_text.strip()
        # Remove reasoning / think tags if present
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE).strip()

        # Try direct JSON parsing
        parsed = None
        try:
            candidate = json.loads(cleaned)
            if isinstance(candidate, dict):
                parsed = candidate
        except Exception:
            pass

        # Try regex fenced code block
        if parsed is None:
            fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
            if fenced:
                try:
                    candidate = json.loads(fenced.group(1))
                    if isinstance(candidate, dict):
                        parsed = candidate
                except Exception:
                    pass

        # Try finding outer braces
        if parsed is None:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                try:
                    candidate = json.loads(cleaned[start : end + 1])
                    if isinstance(candidate, dict):
                        parsed = candidate
                except Exception:
                    pass

        if not isinstance(parsed, dict):
            raise ValueError(f"Failed to parse valid JSON object from AI response: {cleaned[:200]}")

        # Lightweight sanity checks (No schema-lock, no Draft 2020-12 validator)
        expected_top_level = [
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
        ]
        missing_keys = [k for k in expected_top_level if k not in parsed]
        if missing_keys:
            logger.warning(f"[AI] Model output missing some top-level contract keys: {missing_keys}. Initializing defaults.")
            for k in missing_keys:
                parsed[k] = FIXED_JSON_STRUCTURE[k]

        if not isinstance(parsed.get("line_items"), list):
            parsed["line_items"] = []
        if not isinstance(parsed.get("review_flags"), list):
            parsed["review_flags"] = []

        return parsed

    async def _extract_openai(
        self,
        messages: List[Dict[str, Any]],
        start_time: float,
    ) -> Dict[str, Any]:
        """Dispatches request directly to OpenAI API (e.g. gpt-5.6-terra)."""
        model = self.active_model
        logger.info(f"[AI-OPENAI] Dispatching request to OpenAI model '{model}'...")

        client = self._get_openai_client()
        kwargs = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_completion_tokens": 4096,
        }
        # GPT-5.6 series models enforce default temperature (1.0). Only pass temperature=0.0 on models that support it.
        if not ("gpt-5" in model.lower() or "o1" in model.lower() or "o3" in model.lower()):
            kwargs["temperature"] = 0.0

        try:
            response = await client.chat.completions.create(**kwargs)
        except AuthenticationError as e:
            logger.error(f"[AI-OPENAI] OpenAI Authentication Error: {e}")
            raise RuntimeError("OpenAI authentication failed. Please verify OPENAI_API_KEY.") from e
        except RateLimitError as e:
            logger.error(f"[AI-OPENAI] OpenAI Rate Limit reached: {e}")
            raise RuntimeError("OpenAI rate limit or quota exceeded. Please retry shortly.") from e
        except APITimeoutError as e:
            logger.error(f"[AI-OPENAI] OpenAI request timed out: {e}")
            raise TimeoutError("OpenAI inference timed out.") from e
        except OpenAIError as e:
            logger.error(f"[AI-OPENAI] OpenAI API error: {e}")
            raise RuntimeError(f"OpenAI API error: {str(e)}") from e
        except Exception as e:
            logger.error(f"[AI-OPENAI] Unexpected error calling OpenAI: {e}")
            raise RuntimeError(f"Failed to communicate with OpenAI API: {str(e)}") from e

        elapsed = round(time.time() - start_time, 2)
        raw_content = response.choices[0].message.content or ""
        
        # Log token usage when available
        usage = getattr(response, "usage", None)
        if usage:
            prompt_t = getattr(usage, "prompt_tokens", 0)
            comp_t = getattr(usage, "completion_tokens", 0)
            total_t = getattr(usage, "total_tokens", 0)
            logger.info(f"[AI-OPENAI] OpenAI response received in {elapsed}s | Tokens: prompt={prompt_t}, completion={comp_t}, total={total_t}")
        else:
            logger.info(f"[AI-OPENAI] OpenAI response received in {elapsed}s")

        parsed = self._extract_and_validate_json(raw_content)
        if usage:
            parsed["_token_usage"] = {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
                "latency_s": elapsed,
            }
        return parsed

    async def extract_invoice_vlm(
        self,
        file_bytes: bytes,
        filename: str = "invoice.pdf",
        content_type: str = "application/pdf",
        chart_of_accounts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Direct multimodal invoice extraction via OpenAI API.
        """
        if not file_bytes or len(file_bytes) == 0:
            raise ValueError("Invoice file content is empty.")

        start_time = time.time()
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        logger.info(
            f"[AI] Invoice request received | provider=openai model={self.active_model} "
            f"filename={filename} size={len(file_bytes)} sha256={sha256_hash} "
            f"coa_count={len(chart_of_accounts or [])}"
        )

        # 1. Rasterize file bytes into compressed page images
        t0 = time.time()
        pages = decode_invoice_to_pages(file_bytes, filename)
        raster_time = round(time.time() - t0, 2)
        logger.info(f"[AI] Rasterized {len(pages)} page(s) in {raster_time}s")

        # 2. Build standard multimodal messages payload
        system_prompt = self._build_system_prompt()
        user_text = self._build_user_prompt(filename, chart_of_accounts or [])

        user_content: List[Dict[str, Any]] = [{"type": "text", "text": user_text}]
        for page_data in pages:
            b64_img = base64.b64encode(page_data["bytes"]).decode("utf-8")
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64_img}",
                    "detail": "auto",
                },
            })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # 3. Direct OpenAI extraction
        return await self._extract_openai(messages, start_time)


ai_service = AIService()
