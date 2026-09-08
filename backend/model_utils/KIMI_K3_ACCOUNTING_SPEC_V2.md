# KIMI K3 — A-to-Z Indian Invoice Accounting & Tax Knowledge Base
## Production Knowledge, Decision Rules, Negative Examples, Positive Examples, Edge Cases & Strict Output Contract

**Version:** 2.0  
**Research/verification date:** 07 September 2026  
**Primary use:** Kimi K3 decision-support layer for an Indian invoice/accounting backend  
**Scope:** Invoice extraction interpretation, GST, CGST/SGST/UTGST/IGST, HSN/SAC, RCM, ITC, GSTR-2B, TDS, TCS, accounting classification, COA matching and GL/journal support.

> This is a knowledge/integration specification, not a substitute for professional tax advice. It is intentionally designed for an automation system: K3 interprets evidence, classifies, recommends and flags risks; the backend calculates, validates, enforces statutory rules, persists data and posts/export journals.
>
> Indian tax law, notifications, circulars, forms, thresholds, rates and portal validations can change. Production must use effective-date-aware rule masters and current official sources.

---

# 1. SYSTEM PHILOSOPHY

## 1.1 K3 is the intelligence layer

K3 should answer:

- What is this invoice?
- What are the goods/services?
- What is the accounting nature?
- Which existing Zoho COA account is the best match?
- Is GST apparently intra-State, inter-State, import/export, SEZ or special-rule?
- Is RCM a possibility?
- Is TDS potentially applicable?
- Which TDS provision/category is a candidate?
- Is ITC apparently eligible, blocked, partial or requiring review?
- What evidence supports the classification?
- What information is missing?
- Which cases require backend/statutory validation?

## 1.2 Backend is the authority layer

Backend should answer:

- What is the final GST calculation?
- What is the final ITC amount?
- What reversal applies?
- What is the final TDS base/rate/amount?
- Which COA ID is actually posted?
- What are the final debit/credit amounts?
- Is the journal balanced?
- Is the transaction legally/operationally acceptable?
- What gets persisted and exported to Zoho?

The current project already follows this split: GST, ITC, financial validation, statutory TDS and GL generation are deterministic backend components, while COA/TDS classifications are model-supported proposals. fileciteturn3file5L255-L263

---

# 2. SOURCE PRIORITY

For any rule, use:

1. Current statute / Finance Act / amendment.
2. Current official government notification/circular.
3. Current official GST/Income-Tax portal guidance.
4. Tenant/company accounting policy.
5. Current Zoho master data.
6. Versioned project knowledge base.
7. K3 general knowledge.
8. Safe fallback.

Never use an old memorized rate/threshold when a current rule master is available.

---

# 3. NON-NEGOTIABLE ANTI-HALLUCINATION RULES

K3 MUST NEVER invent:

- invoice number;
- invoice date;
- vendor/customer identity;
- GSTIN;
- PAN;
- HSN/SAC;
- quantity;
- price;
- discount;
- taxable amount;
- tax amount;
- TDS section;
- TDS rate;
- TDS amount;
- ITC amount;
- GSTR-2B status;
- Zoho account ID;
- Zoho tax ID;
- legal certificate;
- exemption;
- payment history;
- threshold status.

When evidence is unavailable:

```json
{
  "value": null,
  "requires_review": true
}
```

Do not use a plausible value simply because it "normally" occurs.

---

# 4. FACT / INTERPRETATION / DECISION SUPPORT SEPARATION

For every domain:

```text
EXTRACTED FACT
    ↓
MODEL INTERPRETATION
    ↓
MODEL RECOMMENDATION
    ↓
BACKEND VALIDATION/CALCULATION
    ↓
FINAL RESULT
```

Example:

```text
Invoice says:
"Annual legal consultancy — ₹100,000"

K3:
Payment nature = likely professional service
TDS = potential
ITC = potential subject to normal conditions
COA = likely professional fees

Backend:
checks current law, threshold, PAN, payment/credit event,
ITC statutory conditions, actual Zoho COA,
then calculates final result.
```

---

# 5. CANONICAL INVOICE SCHEMA

The existing backend accepts canonical header and line-item fields. Relevant fields include:

- `invoice_number`
- `invoice_date`
- `due_date`
- `po_number`
- `vendor_name`
- `vendor_address`
- `vendor_gstin`
- `vendor_pan`
- `customer_name`
- `customer_gstin`
- `customer_pan`
- `place_of_supply`
- `payment_terms`
- `bank_details`
- `line_items`
- `subtotal`
- `discount_total`
- `tax_total`
- `cgst_amount`
- `sgst_amount`
- `igst_amount`
- `cess_amount`
- `shipping_charges`
- `other_charges`
- `adjustment`
- `round_off`
- `total_amount`
- `currency`
- `raw_fields`
- `additional_fields`

The project schema shows `line_items[].taxable_amount` flowing to financial validation, GST, ITC, TDS-base determination and GL; GST component amounts flow into GST, ITC, financial validation and journal generation. fileciteturn2file0L22-L45

---

# 6. FIELD DEFINITIONS

## 6.1 Header

### `invoice_number`
Supplier's invoice/bill identifier.

Rules:
- preserve meaningful prefixes/suffixes;
- do not create one;
- blank/missing → `null` + review.

### `invoice_date`
Date printed/issued on the document.

Rules:
- extract exactly;
- backend normalizes;
- do not replace a missing date with today's date for a finalized invoice.

### `due_date`
Contractual/payment due date.

### `po_number`
Purchase order reference.

### `vendor_name`
Supplier/seller name shown on document.

### `vendor_gstin`
Supplier GST registration number.

Rules:
- validate syntax;
- do not infer from company name;
- missing/uncertain → review.

### `vendor_pan`
Supplier PAN if shown/available from trusted master data.

### `customer_name`
Buyer/recipient name.

### `customer_gstin`
Buyer GSTIN.

### `customer_pan`
Buyer PAN where available.

### `place_of_supply`
Legally relevant place-of-supply result or clearly evidenced invoice field.

Do not automatically equate:
- billing address;
- delivery address;
- customer registered office;
- vendor address

with legal POS.

### `line_items`
Every material invoice line.

### `subtotal`
Pre-tax subtotal.

### `discount_total`
Total discount shown at header level.

### `tax_total`
Total GST/cess/tax shown.

### `cgst_amount`
Central GST amount.

### `sgst_amount`
State GST amount.

### `igst_amount`
Integrated GST amount.

### `cess_amount`
Applicable GST compensation/other statutory cess shown.

### `shipping_charges`
Freight/shipping charge.

### `other_charges`
Other charges.

### `adjustment`
Invoice adjustment.

### `round_off`
Signed rounding adjustment.

### `total_amount`
Final invoice payable amount.

### `currency`
ISO-style currency identifier where known.

---

# 7. LINE-ITEM FIELD DEFINITIONS

### `description`
Supplier's goods/services description.

### `hsn_code`
HSN/SAC identifier in canonical backend naming.

The backend currently accepts aliases such as `hsn_sac_code` and maps them to `hsn_code`. K3 should emit the canonical field. fileciteturn2file3L121-L130

### `quantity`
Quantity displayed.

### `unit`
Unit of measurement.

### `unit_price`
Pre-discount, pre-tax unit price.

### `discount`
Line discount.

### `discount_type`

Allowed:

```text
percentage
amount
null
```

Never guess whether an ambiguous "10" means ₹10 or 10%.

### `taxable_amount`
Pre-tax taxable amount.

Where appropriate:

```text
gross = quantity × unit_price
taxable = gross − applicable discount
```

The backend already uses line quantity/price/discount for reconciliation and derivation. fileciteturn2file3L125-L130

---

# 8. GST MASTER KNOWLEDGE

## 8.1 GST components

Know the difference between:

- CGST;
- SGST;
- UTGST;
- IGST;
- cess.

Normal simplified pattern:

```text
Intra-State taxable supply
    → CGST + SGST/UTGST

Inter-State taxable supply
    → IGST
```

Special rules can alter this, so K3 must not use a simplistic state comparison alone.

## 8.2 Inter-State / Intra-State

Reason with:

```text
Supplier location
+
Recipient location
+
Place of supply
+
Nature of supply
+
Special statutory rule
```

The IGST Act provides separate place-of-supply rules for goods, domestic services and cross-border services. The official CBIC material describes, for example, movement-based goods supplies, installation/assembly, on-board supplies and import/export POS rules. citeturn521935search53turn521935search0

## 8.3 Goods place-of-supply signals

K3 should recognize:

- goods with movement;
- bill-to/ship-to structures;
- no movement;
- installation/assembly at site;
- goods supplied on a conveyance;
- import;
- export.

Never assume "ship-to state = POS" for every possible transaction without checking the statutory category.

## 8.4 Service POS signals

K3 must recognize that some services have special place-of-supply rules.

Do not apply:

```text
service vendor state ≠ customer state → automatically IGST
```

without evaluating POS.

## 8.5 GST rate

GST rates are notification-driven.

Runtime:

```text
description + HSN/SAC + transaction date + supply type
            ↓
current official rate master
            ↓
K3 rate candidate
            ↓
backend rate validation
```

Never treat model memory as the authoritative rate table.

---

# 9. GST TAX INVOICE KNOWLEDGE

Official CBIC invoice rules include taxable value, tax rate, tax amount, POS for inter-State supplies, separate delivery address where different, reverse-charge indication and HSN/service accounting code requirements as applicable. citeturn521935search3

K3 should check for:

- supplier identity;
- invoice number;
- invoice date;
- recipient details;
- GSTIN where applicable;
- description;
- HSN/SAC;
- taxable value;
- tax rate;
- tax amount;
- POS where applicable;
- RCM flag;
- total.

Missing information should become a review signal, not an invented value.

---

# 10. GST VALUATION KNOWLEDGE

K3 should distinguish:

- taxable transaction value;
- discount;
- freight;
- incidental expenses;
- other charges;
- reimbursement;
- taxes/cess governed by statutory valuation rules.

Never use blanket rules:

```text
all freight = taxable
all discounts = non-taxable
all reimbursements = non-taxable
```

Valuation depends on statutory conditions.

---

# 11. REVERSE CHARGE MECHANISM (RCM)

RCM means the recipient may be liable for tax in specified notified circumstances.

K3 should recognize:

- invoice explicitly saying "Reverse Charge";
- notified goods/services where RCM may apply;
- RCM vs supplier-charged GST distinction;
- RCM tax and ITC are separate decisions.

Official CBIC guidance explains RCM under the GST framework and identifies notified supplies. citeturn521935search6

Model output:

```json
{
  "rcm_candidate": true,
  "reason": "Invoice explicitly states reverse charge.",
  "backend_validation_required": true
}
```

Never use "RCM = true" solely because the supplier is unregistered.

---

# 12. ITC MASTER KNOWLEDGE

## 12.1 Core principle

ITC is not automatically available merely because GST is printed.

The model should evaluate:

```text
document
↓
recipient status
↓
receipt of supply
↓
business use
↓
statutory tax/document conditions
↓
time limit
↓
blocked credit restrictions
↓
apportionment
↓
payment-related reversal conditions
↓
GSTR-2B/reconciliation
```

Section 16 of the CGST Act contains the primary eligibility and conditions framework. citeturn521935search7

## 12.2 Document requirement

Know common qualifying evidence:

- tax invoice;
- debit note;
- bill of entry;
- prescribed ISD documentation;
- other prescribed documents.

Do not infer legal entitlement from a mere PDF/scan if material information is missing.

## 12.3 GSTR-2B

Official GST Portal guidance states that GSTR-2B is a static, auto-drafted ITC statement generated from supplier/ECO and other relevant filings, and includes import-related information from ICEGATE. It is used as an input to take the appropriate ITC, but taxpayers must still self-assess other legal restrictions. citeturn704350search0turn521935search54

Important:

```text
2B says available
≠ automatically legally claimable in every case
```

K3 should flag 2B status separately from legal eligibility.

## 12.4 Section 16(2) gate

K3 should recognize the broad conditions involving:

- possession of prescribed documentation;
- receipt of goods/services;
- supplier tax reporting/payment conditions as applicable;
- return filing requirements;
- other statutory conditions.

Do not hard-code a simplistic single yes/no rule.

## 12.5 Section 16(3)

Capital goods can have an ITC restriction when depreciation has been claimed on the tax component under the applicable Income-tax law. citeturn521935search7

Model:

```text
capital asset
+
depreciation on GST component?
    yes → potential restriction
    no/unknown → continue evaluation
```

## 12.6 Section 16(4)

ITC time-limit rules are date-sensitive and can be amended.

Production must use an effective-date rule master.

K3 should return:

```text
time_limit_status:
  VALID
  EXPIRED
  UNKNOWN
  BACKEND_CHECK_REQUIRED
```

rather than memorizing one permanent cutoff.

## 12.7 Section 17(1)

Business/non-business use can require restriction.

Signals:

```text
clearly business
clearly personal
mixed
unknown
```

## 12.8 Section 17(2)

Exempt/taxable-use apportionment must be recognized.

K3 should identify:

```text
full taxable business use
mixed taxable/exempt use
unknown use
```

The backend should compute the statutory apportionment/reversal.

## 12.9 Section 17(5) blocked credit

K3 must know the major blocked-credit categories and their statutory exceptions.

Recognize risk categories including:

- specified motor vehicles/conveyances;
- food/beverages and specified related supplies;
- club memberships;
- specified travel benefits;
- works contract/construction-related categories;
- personal consumption;
- goods lost/stolen/destroyed/written off/given as gifts/free samples in specified circumstances;
- certain taxes/penalties and other specifically restricted items.

**Never use a pure keyword blacklist.**

Example:

```text
"car"
→ BLOCKED_RISK

not:

"car"
→ ALWAYS_BLOCKED
```

Exceptions and purpose matter.

CBIC circulars demonstrate that even motor-vehicle/demo-vehicle cases can require interpretation of statutory exceptions rather than a simple keyword decision. citeturn704350search24

## 12.10 Rule 36

K3 should recognize prescribed documentary/document-condition logic.

## 12.11 Rule 37

K3 should recognize payment-linked reversal/re-availment concepts.

For ordinary supplier-payment cases, the 180-day condition is a critical review signal.

## 12.12 Rule 42 and Rule 43

K3 should identify potential common-use/apportionment situations:

```text
exclusive business taxable
exclusive exempt
mixed
non-business
capital goods
```

Backend computes the statutory amount.

---

# 13. TDS MASTER KNOWLEDGE

## 13.1 2026 Act transition

This is mandatory knowledge.

The Income-tax Department states that TDS obligations are governed by the Act applicable based on when the earlier of credit or payment occurs:

```text
earlier of credit/payment
        ↓
on or before 31-Mar-2026
        → Income-tax Act, 1961

on or after 01-Apr-2026
        → Income-tax Act, 2025
```

For salary, payment timing controls under the applicable salary provision. citeturn521935search1turn521935search4

## 13.2 Old vs new provision references

For post-1-Apr-2026 transactions, the Income-tax Department says the relevant provision/table item under section 393 (or section 394 for TCS) must be used rather than blindly quoting old sections such as 194C/194J/194H. Incorrect old references may cause filing validation errors. citeturn704350search1

Therefore K3 should be able to store:

```text
current_law_provision
legacy_reference
effective_date
```

but should never output the old provision as the production statutory provision for a post-1-Apr-2026 event.

## 13.3 TDS categories K3 must recognize

At minimum:

- salary;
- contractor/work contract;
- professional services;
- technical services;
- commission/brokerage;
- rent;
- interest;
- purchase-of-goods situations;
- immovable property;
- virtual digital asset;
- specified payments;
- non-resident payments;
- cases requiring special certificate/order treatment;
- no TDS/insufficient evidence.

The new Act consolidates TDS under sections 392 and 393; section 393 uses tables by payee/nature/category. Official Income-tax Department guidance confirms this structure. citeturn704350search1

## 13.4 TDS decision tree

```text
payment/credit event
↓
nature of payment
↓
payer type
↓
payee type/residency
↓
law version
↓
relevant table/provision
↓
threshold
↓
PAN status
↓
certificate/lower/nil rate
↓
special exception
↓
withholding base
↓
candidate rate
↓
backend calculation
```

## 13.5 Thresholds

Thresholds are transaction/category dependent and can change.

Never invent a threshold.

K3 should request/backend-check:

```text
current threshold
annual cumulative amount
single transaction amount
payer category
payee category
```

The current project documentation identifies annual/cumulative TDS threshold tracking as a backend gap; current processing can calculate a single transaction without historical cumulative vendor payments. fileciteturn2file9L380-L383

Therefore:

```json
{
  "threshold_status": "CUMULATIVE_DATA_REQUIRED",
  "requires_backend_validation": true
}
```

when previous payments are unavailable.

## 13.6 PAN

Recognize:

- valid;
- invalid;
- missing;
- unknown;
- special/exempt case where relevant.

Never create PAN from imagination.

The project backend already has a PAN validation/invalid-PAN handling path, but K3 must remain an evidence detector rather than the final calculator. fileciteturn3file2L127-L132

## 13.7 Lower/nil deduction

K3 should detect evidence of:

- lower deduction certificate/order;
- nil deduction certificate/order;
- declaration;
- exemption.

If present, flag it and pass the evidence to backend.

## 13.8 TDS and GST

K3 must keep:

```text
invoice taxable/service/goods value
GST
TDS base candidate
```

as separate concepts.

The current project TDS engine calculates from a pre-tax base and derives the final amount deterministically. fileciteturn3file2L114-L125

## 13.9 TDS final amount

K3 may suggest:

```text
base_candidate
rate_candidate
```

Backend calculates:

```text
final_tds_amount
```

Do not make the model's arithmetic authoritative.

---

# 14. TCS MASTER KNOWLEDGE

TCS is not TDS.

```text
TDS
→ tax deducted by the payer/person making the specified payment.

TCS
→ tax collected by the specified collector on specified transactions.
```

The Income-tax Department states that TCS is consolidated under section 394 of the Income-tax Act, 2025 and follows the same transition principle around 31-Mar/1-Apr-2026. citeturn521935search1

K3 must separately classify TDS and TCS.

---

# 15. HSN / SAC KNOWLEDGE

## HSN
Goods classification.

## SAC
Services classification.

Model should use:

```text
description
+
HSN/SAC provided
+
item characteristics
+
transaction context
```

Do not invent HSN/SAC.

If a tax rate is needed:

```text
classification
→ current official rate master
→ backend validation
```

---

# 16. COMPOSITE / MIXED SUPPLY

K3 should detect possible:

- naturally bundled supply;
- principal + ancillary supply;
- unrelated goods/services sold together for one price.

Do not decide solely from the number of invoice lines.

```json
{
  "composite_or_mixed_supply_risk": "POSSIBLE",
  "requires_review": true
}
```

---

# 17. IMPORT / EXPORT / SEZ

Recognize:

- import of goods;
- import of services;
- export of goods;
- export of services;
- supply to SEZ;
- Bill of Entry;
- ICEGATE import IGST;
- zero-rated supply.

The IGST Act identifies exports and supplies to SEZ as zero-rated supplies subject to applicable conditions. citeturn521935search0

Do not assume:

```text
foreign vendor = no GST
foreign currency = export
```

without checking transaction nature.

---

# 18. ZERO-RATED VS EXEMPT

K3 must know the distinction:

```text
ZERO-RATED
- export
- qualifying SEZ supply
- ITC/refund framework differs

EXEMPT
- statutory exemption
- ITC treatment differs from zero-rated supply
```

Never call an export "exempt" merely because GST is 0.

---

# 19. FINANCIAL VALIDATION KNOWLEDGE

K3 should flag:

```text
line subtotal mismatch
header subtotal mismatch
tax arithmetic mismatch
total mismatch
discount ambiguity
round-off issue
missing components
```

It should not modify arithmetic just to make totals match.

The project's financial validator performs deterministic reconciliation and its schema feeds line taxable values and tax components into the validation path. fileciteturn2file2L96-L98

---

# 20. ACCOUNTING / GL KNOWLEDGE

## 20.1 Fundamental equation

```text
Assets = Liabilities + Equity
```

For each journal:

```text
Total Debit = Total Credit
```

## 20.2 Normal business purchase

Conceptual pattern:

```text
Dr Expense / Inventory / Asset
Dr Eligible Input GST
    Cr Vendor Payable
```

## 20.3 TDS deducted

Conceptual pattern:

```text
Dr Expense / Inventory / Asset
Dr Eligible Input GST
    Cr Vendor Payable (net of TDS)
    Cr TDS Payable
```

The exact posting pattern depends on the backend result and organization policy.

## 20.4 Blocked ITC

If GST is not eligible, the blocked tax component may form part of the expense/asset cost rather than an eligible input-tax asset.

Backend decides the final treatment.

## 20.5 Expense vs asset

Potential asset indicators:

- machinery;
- computer equipment;
- servers;
- furniture;
- vehicles;
- long-lived infrastructure.

Potential expense indicators:

- routine maintenance;
- utilities;
- subscriptions;
- consumables;
- professional fees;
- ordinary office costs.

Entity policy can override generic intuition.

Never invent a universal capitalization threshold.

---

# 21. COA MATCHING

## Production mode

Backend supplies the actual Zoho COA.

K3 must choose from it.

```text
Zoho COA
  ↓
candidate matching
  ↓
semantic/economic match
  ↓
best existing account
```

Output:

```json
{
  "matched_account_id": "actual-zoho-id",
  "matched_account_name": "Professional Fees",
  "match_type": "SEMANTIC",
  "confidence": 0.96,
  "requires_review": false
}
```

## No match

```json
{
  "matched_account_id": null,
  "matched_account_name": null,
  "suggested_new_account_name": "Specialized Consultancy",
  "requires_review": true
}
```

Never fabricate a Zoho ID.

The project currently treats manual approved COA above the AI proposal. fileciteturn3file6L282-L286

---

# 22. STRICT K3 RESPONSE

Recommended top-level object:

```json
{
  "schema_version": "2.0.0",
  "knowledge_version": "2026-09-07",
  "invoice_interpretation": {},
  "coa_support": {},
  "gst_support": {},
  "tds_support": {},
  "tcs_support": {},
  "itc_support": {},
  "gl_support": {},
  "review_flags": []
}
```

Closed objects should use:

```json
"additionalProperties": false
```

where supported by the selected structured-output API.

---

# 23. RECOMMENDED OUTPUT ENUMS

## Goods/services

```text
GOODS
SERVICES
MIXED
UNKNOWN
```

## Supply type

```text
INTRA_STATE
INTER_STATE
IMPORT
EXPORT
SEZ
RCM_SPECIAL_CASE
UNKNOWN
```

## ITC

```text
ELIGIBLE_CANDIDATE
PARTIALLY_ELIGIBLE_CANDIDATE
BLOCKED_CANDIDATE
REVIEW_REQUIRED
UNKNOWN
```

## Business use

```text
YES
NO
MIXED
UNKNOWN
```

## Confidence

```text
0.0 to 1.0
```

Confidence is not legal certainty.

---

# 24. STANDARD REVIEW FLAGS

## Invoice

```text
INVOICE_NUMBER_MISSING
INVOICE_DATE_MISSING
VENDOR_IDENTITY_UNCERTAIN
GSTIN_MISSING
GSTIN_INVALID_FORMAT
PAN_MISSING
LINE_DESCRIPTION_MISSING
HSN_SAC_MISSING
TAXABLE_AMOUNT_UNCLEAR
TOTAL_MISMATCH
TAX_MISMATCH
DISCOUNT_AMBIGUOUS
```

## GST

```text
GST_POS_REQUIRED
GST_RATE_LOOKUP_REQUIRED
GST_COMPONENT_MISMATCH
GST_HEADER_LINE_MISMATCH
RCM_REVIEW
COMPOSITE_SUPPLY_REVIEW
ZERO_RATED_REVIEW
IMPORT_EXPORT_REVIEW
```

## ITC

```text
ITC_DOCUMENT_REVIEW
ITC_RECEIPT_REVIEW
ITC_BUSINESS_USE_REVIEW
ITC_BLOCKED_CREDIT_RISK
ITC_APPORTIONMENT_REVIEW
ITC_180_DAY_PAYMENT_REVIEW
ITC_TIME_LIMIT_REVIEW
ITC_GSTR2B_RECONCILIATION
ITC_IMPORT_REVIEW
```

## TDS

```text
TDS_NATURE_AMBIGUOUS
TDS_PROVISION_LOOKUP_REQUIRED
TDS_THRESHOLD_DATA_REQUIRED
TDS_PAN_REQUIRED
TDS_PAN_INVALID
TDS_CERTIFICATE_REVIEW
TDS_NON_RESIDENT_REVIEW
TDS_DATE_TRANSITION_REVIEW
TDS_CUMULATIVE_DATA_REQUIRED
```

## COA

```text
COA_NO_MATCH
COA_MULTIPLE_MATCHES
COA_NEW_ACCOUNT_SUGGESTION
COA_ASSET_EXPENSE_AMBIGUITY
```

---

# 25. POSITIVE EXAMPLES

## P01 — Clear professional service

Input:

```text
Description: Legal Consultancy Services
Taxable: ₹100,000
GST: ₹18,000
Vendor: ABC Legal Advisors
```

Expected K3:

```json
{
  "goods_or_services": "SERVICES",
  "payment_nature": "PROFESSIONAL_SERVICES",
  "coa_category_candidate": "PROFESSIONAL_FEES",
  "tds_applicable_candidate": true,
  "tds_threshold_check_required": true,
  "itc_candidate": "ELIGIBLE_CANDIDATE"
}
```

Backend validates current TDS provision/rate/threshold/PAN and final ITC.

---

## P02 — Office stationery

```text
Description: A4 Paper 80 GSM
HSN: provided
Quantity: 20 boxes
```

Expected:

```text
GOODS
→ Office Supplies / Stationery candidate
→ normal GST analysis
→ ITC candidate if business-use/statutory conditions satisfied
→ no invented TDS conclusion
```

---

## P03 — Laptop / computer equipment

```text
Description: Business Laptop — 5 units
```

Expected:

```text
GOODS
POTENTIAL_CAPITAL_ASSET
COA → Computer Equipment / Fixed Asset candidate
ITC → candidate, subject to statutory conditions
```

Do not invent capitalization threshold.

---

## P04 — Interstate goods

```text
Supplier State: Telangana
Customer State: Karnataka
Goods move to Karnataka
```

Expected:

```text
INTER_STATE
IGST candidate
```

Backend validates POS and tax.

---

## P05 — Intrastate goods

```text
Supplier State: Telangana
Customer POS: Telangana
```

Expected:

```text
INTRA_STATE
CGST + SGST candidate
```

---

## P06 — Cloud hosting

```text
Description: Cloud Computing Infrastructure Services
GST: 18% IGST
```

Expected:

```text
SERVICES
ITC → eligible candidate subject to statutory conditions
COA → Cloud Hosting / IT Infrastructure candidate
```

The project itself has a representative ITC test where cloud infrastructure was treated as eligible while another line in the same invoice was blocked. fileciteturn2file6L243-L265

---

## P07 — Client-project hotel stay

```text
Description: Hotel Accommodation — Client Project
```

Expected:

```text
Travel/Accommodation
Business-purpose = YES if supported by evidence
ITC candidate = potentially eligible, subject to current law/conditions
```

Do not use "hotel" as an automatic blocker.

---

## P08 — Invoice with valid Zoho COA match

Zoho:

```json
[
  {"account_id":"A1","account_name":"Professional Fees"},
  {"account_id":"A2","account_name":"Office Expenses"}
]
```

Invoice:

```text
Legal consultancy
```

Expected:

```json
{
  "matched_account_id": "A1",
  "matched_account_name": "Professional Fees",
  "requires_review": false
}
```

---

## P09 — Existing capital account match

Zoho:

```text
Computer Equipment → ID A8
```

Invoice:

```text
Dell laptop
```

Expected:

```text
A8
```

provided the accounting context supports capitalization.

---

## P10 — Clear RCM indicator

Invoice visibly says:

```text
Tax payable under reverse charge: Yes
```

Expected:

```json
{
  "rcm_candidate": true,
  "reason": "Explicit invoice evidence"
}
```

Backend determines actual RCM liability and ITC.

---

# 26. NEGATIVE EXAMPLES

Negative means **the model must not make the tempting but unsupported conclusion**.

## N01 — "Service Charges"

Input:

```text
Description: Service Charges
```

Wrong:

```text
TDS = professional services
```

Correct:

```text
Nature ambiguous
TDS review required
COA review required
```

---

## N02 — Vendor name says "Consultancy"

Wrong:

```text
Vendor = XYZ Consultancy
→ automatically TDS professional fee
```

Correct:

```text
Need actual nature of payment/service.
Vendor name alone is insufficient.
```

---

## N03 — Word "Car"

Wrong:

```text
description = "Car"
→ ITC always blocked
```

Correct:

```text
Section 17(5) motor-vehicle risk detected.
Check purpose and statutory exceptions.
```

---

## N04 — Word "Hotel"

Wrong:

```text
Hotel → always blocked ITC
```

Correct:

```text
Business purpose + applicable statutory treatment required.
```

---

## N05 — GSTR-2B present

Wrong:

```text
GSTR-2B = YES
→ ITC = automatically eligible
```

Correct:

```text
GSTR-2B supports reconciliation.
Other statutory restrictions still require evaluation.
```

Official GST Portal guidance explicitly says other legal restrictions can still make credit unavailable and taxpayers must self-assess. citeturn704350search0

---

## N06 — Foreign currency

Wrong:

```text
USD invoice → export
```

Correct:

```text
Currency is not sufficient to classify import/export.
```

---

## N07 — Interstate shipping address

Wrong:

```text
Delivery address Karnataka
→ always IGST
```

Correct:

```text
Determine legal POS under applicable goods/service rules.
```

---

## N08 — Missing TDS history

Wrong:

```text
Invoice ₹40,000
→ below/above threshold based only on this invoice
```

Correct:

```text
Cumulative threshold data required where applicable.
```

---

## N09 — Missing PAN

Wrong:

```text
guess PAN from GSTIN/company name
```

Correct:

```text
PAN = UNKNOWN/MISSING
backend validation required
```

---

## N10 — No COA match

Wrong:

```text
Generate random Zoho account ID
```

Correct:

```json
{
  "matched_account_id": null,
  "requires_review": true
}
```

---

# 27. EDGE CASE EXAMPLES

## E01 — 31-Mar-2026 vs 01-Apr-2026 TDS transition

### Case A

```text
Professional fee credited: 31-Mar-2026
Paid: Apr-2026
```

Expected:

```text
Earlier event = credit
Old Income-tax Act, 1961 applies.
```

The official Income-tax Department gives this transition example. citeturn521935search1

### Case B

```text
Professional fee credited: 01-Apr-2026
```

Expected:

```text
Income-tax Act, 2025
Relevant section 393 table item
```

Do not quote old 194J as the production provision for a post-transition event. citeturn704350search1

---

## E02 — Monthly contractor contract crosses transition

```text
March payment/credit: 31-Mar-2026
April payment/credit: 30-Apr-2026
```

Expected:

```text
March → old Act reference
April → new Act section 393 table reference
```

Official Income-tax Department guidance uses this exact type of transition example. citeturn704350search4

---

## E03 — Header GST only, three lines

```text
3 line invoice
Only header IGST = ₹27,000
No line tax breakdown
```

K3:

```text
Header tax exists.
Line allocation unknown.
Do not invent 9,000/9,000/9,000.
```

The project backend explicitly avoids arbitrary allocation and can flag `REVIEW_REQUIRED`. fileciteturn2file9L410-L413

---

## E04 — Discount ambiguity

```text
Discount = "10"
```

K3:

```text
discount_type = null
review_required = true
```

Never decide percentage vs amount.

---

## E05 — Mixed goods/services

```text
Line 1: Laptop
Line 2: Annual software support
```

Expected:

```text
Potentially different accounting nature
Potentially different tax classification
Evaluate line by line
```

---

## E06 — Expense vs asset uncertain

```text
Description: "Server setup and installation"
```

Could contain:

- hardware;
- installation service;
- configuration;
- maintenance.

Expected:

```text
Do not classify entire amount as asset or expense without line/context.
```

---

## E07 — Multiple possible COA matches

Zoho:

```text
IT Services
Software Subscriptions
Consulting Expense
```

Invoice:

```text
Technology Services
```

Expected:

```text
Multiple plausible matches
→ return ranked candidates
→ requires_review = true
```

---

## E08 — TDS threshold requires prior payments

```text
Current invoice: ₹50,000
Previous vendor payments: unavailable
```

Expected:

```text
threshold_status = UNKNOWN
cumulative_vendor_data_required = true
```

---

## E09 — RCM explicitly marked

```text
Tax payable under reverse charge: YES
```

Expected:

```text
RCM candidate = true
```

but final RCM liability remains backend/statutory.

---

## E10 — RCM not printed but special supply may be notified

Expected:

```text
Do not conclude RCM = false solely because invoice does not say RCM.
```

Use current notified-category rules.

---

## E11 — GSTR-2B mismatch

```text
Invoice exists in books.
Invoice not found in GSTR-2B.
```

Expected:

```text
GSTR2B reconciliation review
Do not automatically mark ITC permanently blocked.
```

---

## E12 — Credit note reduces GST

Expected:

```text
Understand original invoice + credit note relationship.
ITC must not remain overstated after applicable adjustment.
Backend reconciles.
```

GSTR-2B guidance covers negative/amended credit effects and net presentation. citeturn704350search0

---

## E13 — Import of goods

```text
Foreign supplier
Bill of Entry
Import IGST
```

Expected:

```text
IMPORT
Import IGST evidence
GSTR-2B/ICEGATE reconciliation candidate
ITC analysis based on applicable conditions
```

Official GSTR-2B guidance includes import data from ICEGATE. citeturn704350search0

---

## E14 — SEZ supply

Expected:

```text
SEZ candidate
zero-rated framework candidate
LUT/payment-of-IGST context required
```

The IGST Act defines exports and qualifying SEZ supplies as zero-rated. citeturn521935search0

---

## E15 — Construction-related service

Expected:

```text
ITC Section 17(5) risk
Need exact nature/purpose and applicable exception
```

Never use "construction" as an automatic final answer without context.

---

## E16 — Employee food

Expected:

```text
Section 17(5) food/beverage risk
Check statutory exceptions/conditions
```

---

## E17 — Club membership

Expected:

```text
blocked-credit risk
backend/statutory review
```

---

## E18 — Personal consumption

```text
Invoice: household appliance
Company employee says personal use
```

Expected:

```text
ITC personal-use risk
Not ordinary eligible business ITC
```

---

## E19 — 180-day payment issue

```text
Invoice received
Supplier unpaid >180 days
```

Expected:

```text
ITC reversal/review risk
Payment-data check required
```

---

## E20 — Capital asset + depreciation on GST component

Expected:

```text
Capital asset
Potential Section 16(3) restriction
Need depreciation evidence
```

---

# 28. GST POSITIVE / NEGATIVE / EDGE MATRIX

| Scenario | K3 should say | K3 should NOT say |
|---|---|---|
| Same-State ordinary goods | Intra-State candidate | Guaranteed without POS check |
| Different-State ordinary movement | Inter-State candidate | Guaranteed for every service |
| Export | Zero-rated candidate | Exempt |
| SEZ supply | Zero-rated candidate | Automatically tax-free without conditions |
| RCM printed | RCM candidate | Final RCM liability |
| Foreign currency | Currency fact | Export |
| Hotel | Service category | Always blocked ITC |
| Car | Motor vehicle blocker risk | Always blocked |
| Multiple tax rates | Multiple rates | One average rate |
| Header-only GST | Allocation unavailable | Artificial line allocation |

---

# 29. TDS POSITIVE / NEGATIVE / EDGE MATRIX

| Scenario | K3 should say | K3 should NOT say |
|---|---|---|
| Legal consultancy | Professional-services candidate | Final TDS amount without backend |
| Housekeeping contract | Contractor/work candidate | Section solely from vendor name |
| Generic service charges | Ambiguous | Professional fee automatically |
| Missing PAN | PAN unknown | Invent PAN |
| Prior vendor payments unavailable | Cumulative check needed | Threshold definitely met/not met |
| Lower deduction certificate present | Certificate review | Standard rate automatically |
| Non-resident payment | Non-resident review | Resident provision automatically |
| 31-Mar-2026 credit | Old Act transition | New Act automatically |
| 01-Apr-2026 credit | New Act transition | Old section automatically |
| TCS transaction | TCS candidate | TDS |

---

# 30. ITC POSITIVE / NEGATIVE / EDGE MATRIX

| Scenario | K3 should say | K3 should NOT say |
|---|---|---|
| Business office supplies | Eligible candidate | Guaranteed final ITC |
| GSTR-2B match | Reconciliation support | Legal eligibility guaranteed |
| GSTR-2B missing | Reconciliation review | Automatically blocked |
| Gym membership | Blocked-credit risk | Ignore statutory category |
| Car | 17(5) risk | Always blocked |
| Client project travel | Business-use candidate | Personal-use automatically |
| Personal consumption | Blocked/restricted risk | Eligible |
| Mixed taxable/exempt use | Rule 42 risk | Full ITC |
| Capital asset | Capital-goods review | Expense automatically |
| Paid after long delay | 180-day review | Ignore payment history |
| Old invoice | Time-limit check | Automatically eligible/blocked without date analysis |

---

# 31. COA POSITIVE / NEGATIVE / EDGE MATRIX

| Scenario | K3 should do |
|---|---|
| Exact Zoho match | Select existing ID |
| Strong semantic match | Select existing ID with confidence |
| Two plausible accounts | Return candidates + review |
| No account match | Null ID + suggested name + review |
| Asset vs expense unclear | Review |
| Tax account | Keep separate from operating COA |
| Fake/unknown account ID | Never output it |
| Tenant COA differs | Use runtime tenant COA, not global memory |

---

# 32. GL POSITIVE / NEGATIVE / EDGE MATRIX

## Positive

```text
Professional Fees
+
eligible GST
+
TDS
→ normal double-entry purchase structure
```

## Negative

Never:

```text
Dr Expense ₹100,000
Cr Vendor ₹100,000
Dr GST ₹18,000
```

without a balancing credit.

## Edge

```text
TDS + eligible GST + blocked GST + discount + round-off
```

Backend must compile the final balanced journal.

The project's `JournalGenerator` is the deterministic double-entry compiler and integrates effective invoice data, approved COA, GST, ITC, TDS and financial validation. fileciteturn2file2L97-L100

---

# 33. END-TO-END EXAMPLE

Input:

```json
{
  "invoice_number": "INV-2026-001",
  "invoice_date": "2026-08-15",
  "vendor_name": "ABC Consulting Pvt Ltd",
  "vendor_gstin": "29XXXXXXXXXXXXX",
  "vendor_pan": "ABCDE1234F",
  "customer_gstin": "36XXXXXXXXXXXXX",
  "line_items": [
    {
      "description": "Business management consultancy",
      "taxable_amount": 100000,
      "gst_rate": 18,
      "igst_amount": 18000
    }
  ],
  "total_amount": 118000
}
```

K3 interpretation:

```text
Services
Professional/consultancy nature
Inter-State candidate if POS supports it
IGST candidate
TDS candidate
ITC candidate
Professional Fees COA candidate
```

Backend:

```text
GST engine → validates supply and tax
TDS engine → current-law provision/rate/threshold/PAN/base
ITC engine → statutory eligibility
COA → approved Zoho account
JournalGenerator → final journal
```

---

# 34. STRICT NULL POLICY

Use `null` for:

- absent data;
- unreadable data;
- uncertain classification where evidence is insufficient;
- values requiring a missing external master.

Do NOT use:

```text
0
false
"unknown"
"not applicable"
```

interchangeably.

For example:

```json
{
  "tds_rate_candidate": null,
  "threshold_status": "UNKNOWN",
  "requires_review": true
}
```

is better than inventing `0`.

---

# 35. CONFIDENCE POLICY

Confidence measures model confidence in interpretation.

It does NOT mean:

```text
0.99 confidence = 99% legal correctness
```

Use confidence with:

- evidence;
- reason code;
- review status.

---

# 36. KNOWLEDGE VERSIONING

Every rule should carry:

```json
{
  "rule_id": "ITC-17-5-MOTOR-VEHICLE",
  "effective_from": "YYYY-MM-DD",
  "effective_to": null,
  "authority": "CBIC",
  "source_url": "...",
  "last_verified": "2026-09-07"
}
```

TDS must additionally carry:

```text
law_version
effective_from
legacy_reference
current_reference
```

The 2026 transition makes this mandatory.

---

# 37. RUNTIME DATA K3 SHOULD RECEIVE

```text
SYSTEM KNOWLEDGE
    ↓
Invoice schema definitions
Tax/accounting rules
Decision trees
Examples
Anti-hallucination rules

RUNTIME CONTEXT
    ↓
Invoice JSON
Tenant/company information
Zoho COA
Zoho tax master
Vendor master
GSTIN/PAN status
GSTR-2B match
Payment history
TDS certificates
Company accounting policy
Effective tax date
```

This is better than putting the entire tenant COA or all dynamic tax data permanently inside the system prompt.

---

# 38. OFFICIAL SOURCE REGISTRY

## Income Tax Department

**TDS Compliance / Income-tax Act 2025 transition**

https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/tds-compliance

Supports the 31-Mar/1-Apr-2026 transition, new section 393 table structure, retained rates/threshold policy and examples. citeturn521935search1turn704350search4

**Tax Payments**

https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/tax-payments

Supports section 392/393/394 transition and post-1-Apr-2026 provision-reference guidance. citeturn704350search1

**Form 141**

https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/form-141-challan-cum-statement-deduction-tax-us-3931

Supports new Act consolidated TDS reporting information. citeturn704350search2

---

## CBIC / GST

**CGST Act**

https://cbic-gst.gov.in/hindi/CGST-bill-e.html

Primary GST statutory source for CGST framework, including ITC section 16 and related provisions. citeturn521935search7

**IGST Act**

https://cbic-gst.gov.in/hindi/IGST-bill-e.html

Primary source for IGST and place-of-supply/zero-rated concepts. citeturn521935search0turn521935search53

**Tax Invoice Rules**

https://cbic-gst.gov.in/gst-invoice-rules.html

Invoice particulars and tax-invoice requirements. citeturn521935search3

**GST sectoral FAQs**

https://cbic-gst.gov.in/hindi/sectoral-faq.html

GST/RCM and other practical guidance. citeturn521935search6

**GST Rate Materials**

https://cbic-gst.gov.in/hindi/gst-goods-services-rates.html

Use for current rate-master verification rather than hard-coding remembered rates.

---

## GST Portal

**GSTR-2B FAQ**

https://tutorial.gst.gov.in/userguide/returns/FAQ_gstr2b.htm

Official GSTR-2B behavior, availability and self-assessment guidance. citeturn704350search0

**GSTR-2B Advisory**

https://tutorial.gst.gov.in/offlineutilities/returns/GSTR2B/GSTR-2B_Advisory.pdf

Static statement, reconciliation, ITC-not-available cases and reversal cautions. citeturn704350search19

---

# 39. OFFICIAL-SOURCE USAGE RULE

For production knowledge ingestion:

```text
Official source
    ↓
extract rule
    ↓
assign effective date
    ↓
assign authority
    ↓
store source URL
    ↓
build test examples
    ↓
run regression tests
    ↓
deploy rule version
```

Do not directly copy a web page into a giant model prompt.

---

# 40. MINIMUM TEST SUITE

Before production, test at least:

### Invoice data
1. Clean single-line invoice.
2. Multi-line invoice.
3. Missing invoice number.
4. Missing invoice date.
5. Invalid GSTIN.
6. Missing GSTIN.
7. Missing HSN/SAC.
8. Missing line taxes.
9. Header-only GST.
10. Discount ambiguity.

### GST
11. Intra-State.
12. Inter-State.
13. Multiple GST rates.
14. POS conflict.
15. RCM.
16. Export.
17. SEZ.
18. Import.
19. GST arithmetic mismatch.
20. Mixed/composite supply.

### TDS
21. Professional fee.
22. Contractor.
23. Goods purchase.
24. Commission.
25. Rent.
26. Interest.
27. Missing PAN.
28. Invalid PAN.
29. Lower/nil certificate.
30. Threshold requires history.
31. Non-resident.
32. 31-Mar-2026 transition.
33. 01-Apr-2026 transition.
34. TCS rather than TDS.

### ITC
35. Normal business purchase.
36. GSTR-2B match.
37. GSTR-2B mismatch.
38. Missing GSTR-2B.
39. Motor vehicle.
40. Food/beverage.
41. Club membership.
42. Personal consumption.
43. Works contract/construction.
44. Mixed taxable/exempt use.
45. Business/non-business mixed use.
46. 180-day payment issue.
47. ITC time-limit issue.
48. Capital asset/depreciation.
49. Import IGST.
50. Credit note.

### Accounting
51. Expense.
52. Inventory.
53. Capital asset.
54. Professional fee + TDS.
55. Eligible GST.
56. Blocked GST.
57. Multiple COA matches.
58. No COA match.
59. Round-off.
60. Fully balanced journal.

---

# 41. FINAL ARCHITECTURE

```text
                         INVOICE
                            │
                            ▼
                    K3 VISION / VLM
                            │
                            ▼
                  NORMALIZED INVOICE
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
       K3 ACCOUNTING KB               ZOHO COA
              │                           │
              └─────────────┬─────────────┘
                            ▼
                   K3 DECISION SUPPORT
              ┌────────┬────┼────┬────────┐
              ▼        ▼    ▼    ▼        ▼
             GST      TDS   ITC  COA      GL
              │        │    │    │        │
              └────────┴────┴────┴────────┘
                            │
                            ▼
                 DETERMINISTIC BACKEND
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
          GST ENGINE     TDS ENGINE    ITC ENGINE
              │             │             │
              └─────────────┼─────────────┘
                            ▼
                 APPROVED ACCOUNT + TAX DATA
                            │
                            ▼
                    JOURNAL GENERATOR
                            │
                       ┌────┴────┐
                       ▼         ▼
                    DATABASE   ZOHO
```

---

# 42. PROJECT-SPECIFIC SOURCE-OF-TRUTH

The current project documents this precedence:

```text
1. Manual HITL approved value
2. Deterministic statutory engine result
3. Canonical extracted invoice data
4. AI/LLM recommendation
5. Safe fallback
```

The current project specifically treats AI COA/TDS proposals as non-authoritative and deterministic ITC/TDS/GL calculations as authoritative. fileciteturn2file8L337-L348

This hierarchy should remain after K3 integration.

---

# 43. GOLDEN RULE FOR K3

The ideal K3 behavior is NOT:

> "I know the answer."

It is:

> "From the invoice evidence, this is the most likely accounting/tax interpretation. Here is the exact evidence, here are the applicable risk signals, here is what I cannot establish, and here is what the backend should validate."

That is the behavior this knowledge base, examples, edge cases and strict schema are intended to teach.

---

# 44. IMPLEMENTATION CHECKLIST

Before connecting K3 to production:

- [ ] Strict JSON schema created.
- [ ] `additionalProperties=false` applied where possible.
- [ ] Canonical field names fixed.
- [ ] Every field has a definition.
- [ ] Null policy fixed.
- [ ] Review flags fixed.
- [ ] Evidence/reason fields fixed.
- [ ] Zoho COA passed at runtime.
- [ ] K3 cannot invent Zoho IDs.
- [ ] Current GST rate master connected.
- [ ] Effective-date TDS master connected.
- [ ] TDS 2026 law transition covered.
- [ ] Cumulative vendor payment data available for thresholds.
- [ ] GSTR-2B data available when ITC is being evaluated.
- [ ] Company accounting policy available for capitalization/COA decisions.
- [ ] Backend remains final calculator.
- [ ] 60+ regression examples implemented.
- [ ] Positive/negative/edge cases included.
- [ ] Every rule has official source + effective date.
- [ ] Failed/ambiguous model outputs become review cases.
