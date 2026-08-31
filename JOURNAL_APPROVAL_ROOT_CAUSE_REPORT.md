# Root Cause Investigation Report: Unbalanced Journal on Invoice Approval

## 1. Invoice Identification
- **Invoice ID**: `067a0243-0c5d-4a93-bd90-7bbdb7082a6c`
- **Invoice Number**: `INV-2026-71162`
- **File Name**: `invoice_1_pharma_INV-2026-71162.png`
- **Invoice Status**: `COMPLETED`
- **Approval Status**: `PENDING_REVIEW`

---

## 2. Original Invoice Data (VLM Extraction)
From database record `invoices.current_vlm_output` (and `raw_vlm_output`):
- **raw_vlm_output exists**: `True`
- **current_vlm_output exists**: `True`
- **Vendor Name**: VitaLabs Corporation
- **Customer Name**: LogiPort Group
- **Subtotal**: ₹9,367,123.00
- **Tax Total**: ₹496,835.76
  - CGST: ₹248,417.88
  - SGST: ₹248,417.88
  - IGST: `null` / ₹0.00
- **Total Amount**: ₹10,433,551.00
- **Discount Total**: `null` (₹0.00)
- **Shipping Charges**: `null` (₹0.00)
- **Other Charges**: `null` (₹0.00)
- **Round Off**: `null` (₹0.00)
- **Line Items Total (Sum of extracted `taxable_amount`)**:
  - Line 1: ₹37,398.51
  - Line 2: ₹6,463.18
  - Line 3: ₹21,261.42
  - Line 4: ₹27,289.18
  - Line 5: ₹22,788.53
  - **Sum of Line Items Taxable Debits**: **₹115,200.82**

*(Note: Extracted line item `quantity` and `unit_price` in VLM output contain large unscaled OCR artifacts, e.g. 43 × ₹6,182,549, while the extracted `taxable_amount` is ₹37,398.51).*

---

## 3. Financial Validation (`financial_validation_result`)
- **Overall Status**: `MISMATCH`
- **Source Totals**:
  - Subtotal: ₹9,367,123.00
  - Tax Total: ₹496,835.76
  - Total Amount: ₹10,433,551.00
- **Calculated Totals**:
  - Subtotal (sum of line taxable amounts): ₹115,200.82
  - GST Total: ₹496,835.76
  - Grand Total (Calculated Subtotal + Tax): **₹612,036.58**
- **Differences**:
  - Subtotal Difference: ₹9,251,922.18
  - Tax Total Difference: ₹0.00
  - Total Amount Difference: ₹9,821,514.42
- **Failed Checks**:
  1. `line_item_math`: MISMATCH on all 5 lines between `quantity * unit_price` vs `taxable_amount`.
  2. `line_item_sum_vs_subtotal`: MISMATCH (Sum of line items = ₹115,200.82 vs Extracted Subtotal = ₹9,367,123.00; difference = ₹9,251,922.18).
  3. `extracted_total_vs_calculated_total`: MISMATCH (Calculated Total = ₹612,036.58 vs Extracted Total = ₹10,433,551.00; difference = ₹9,821,514.42).
- **Passed Checks**:
  - `gst_components_vs_gst_total`: PASSED (CGST ₹248,417.88 + SGST ₹248,417.88 = ₹496,835.76).
- **Pre-existing Reconciliation Mismatch**: **YES**. The invoice had severe internal reconciliation mismatches directly from Stage 2/Stage 5 before journal generation was run.

---

## 4. GST + ITC Results
- **Supply Type**: `INTER_STATE` (Supplier in Gujarat `24`, POS / Buyer in Rajasthan `08`)
- **Extracted GST**:
  - CGST: ₹248,417.88
  - SGST: ₹248,417.88
  - IGST: ₹0.00
  - GST Total: ₹496,835.76
- **GST Validation Status**: `GST_MISMATCH` (Unexpected CGST/SGST on Inter-State supply).
- **ITC Result Status**: `REVIEW_REQUIRED`
  - Eligible ITC: ₹0.00
  - Ineligible ITC: ₹0.00
  - Total Tax Amount: ₹496,835.76

---

## 5. Journal JSON (`invoice.journal_entry`)
Current preview journal entry stored in JSONB column:

| Account ID | Account Name | Line Type | Debit (₹) | Credit (₹) | Source Line | Provenance |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `4076465000000033052` | Materials | EXPENSE | 37,398.51 | 0.00 | 0 | AI_PREDICTED |
| `4076465000000033052` | Materials | EXPENSE | 6,463.18 | 0.00 | 1 | AI_PREDICTED |
| `4076465000000033052` | Materials | EXPENSE | 21,261.42 | 0.00 | 2 | AI_PREDICTED |
| `4076465000000033052` | Materials | EXPENSE | 27,289.18 | 0.00 | 3 | AI_PREDICTED |
| `4076465000000033052` | Materials | EXPENSE | 22,788.53 | 0.00 | 4 | AI_PREDICTED |
| `LIAB_AP` | Accounts Payable (Vendor) | ACCOUNTS_PAYABLE | 0.00 | 10,433,551.00 | None | DETERMINISTIC |

- **Total Debits**: ₹115,200.82
- **Total Credits**: ₹10,433,551.00
- **Difference**: -₹10,318,350.18
- **Status**: `UNBALANCED`

*(Note: In the preview generation `generate_journal()`, tax lines were omitted from debits because ITC status was `REVIEW_REQUIRED` with eligible tax = 0. However, during approval `generate_journal_entry()` is invoked, which includes the tax lines as debits: ₹115,200.82 + ₹248,417.88 + ₹248,417.88 = **₹612,036.58**).*

---

## 6. Relational Journal Inspection
Database tables `journal_entries` and `journal_lines`:
- **JournalEntry ID**: `1cd51f95-4a71-47b5-b5d6-bf21118998a4`
- **Total Debit**: ₹115,200.82
- **Total Credit**: ₹10,433,551.00
- **Difference**: -₹10,318,350.18
- **Status**: `UNBALANCED`
- **Relational Lines Count**: 6 lines matching `invoice.journal_entry` JSON lines exactly.

---

## 7. Trace of Journal Generation Logic (`backend/app/services/journal_generator.py`)
In `journal_generator.generate_journal_entry()`:
- **A. Expense/Asset Debit Amounts**:
  - Extracted per line item from `item.get("taxable_amount")`:
    - Line 1: ₹37,398.51
    - Line 2: ₹6,463.18
    - Line 3: ₹21,261.42
    - Line 4: ₹27,289.18
    - Line 5: ₹22,788.53
    - **Total Expense Debits = ₹115,200.82**
- **B. Input GST Debit Amounts**:
  - Extracted from `cgst_total` and `sgst_total` header/line fields:
    - Input CGST Receivable: ₹248,417.88 (DR)
    - Input SGST Receivable: ₹248,417.88 (DR)
    - **Total Tax Debits = ₹496,835.76**
  - **Total Debits (Expense + Tax)** = `₹115,200.82 + ₹496,835.76` = **₹612,036.58**
- **C. TDS Payable (Credit)**:
  - `tds_applicable` = `False` / `0.00` → Credit = ₹0.00
- **D. Accounts Payable (Credit)**:
  - Computed at line 844:
    ```python
    net_payable = round(total_amount - tds_amount, 2)
    ```
    Where `total_amount = float(invoice_data.get("total_amount") or 0.0)`.
    From the extracted VLM header `total_amount`: **₹10,433,551.00**
    - Accounts Payable Credit = **₹10,433,551.00**

**Confirmation**:
The Debit side aggregates line-item taxable amounts + GST (`₹115,200.82 + ₹496,835.76 = ₹612,036.58`), whereas Accounts Payable credit directly uses the header `total_amount` (`₹10,433,551.00`).

---

## 8. Trace of Approval Logic (`backend/app/api/v1/review.py`)
In `approve_invoice()` ([review.py:199-214](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/api/v1/review.py#L199-L214)):

```python
# 3. Generate Authoritative Journal (require_approved=True)
journal = journal_generator.generate_journal_entry(
    invoice_data=vlm_data,
    accounting_data=accounting_data,
    require_approved=True,
)

if not journal.get("is_balanced"):
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Cannot approve invoice: Journal is unbalanced (Debits ₹{journal.get('total_debit')} != Credits ₹{journal.get('total_credit')}).",
    )
```

Because `total_debit` (₹612,036.58) does not equal `total_credit` (₹10,433,551.00), `journal["is_balanced"]` evaluates to `False`, throwing the HTTP 400 Bad Request exception.

---

## 9. Data Flow Across Stages
1. **Stage 2 (VLM Extraction)**:
   - Extracted header `total_amount`: ₹10,433,551.00
   - Extracted header `subtotal`: ₹9,367,123.00
   - Extracted header `tax_total`: ₹496,835.76 (CGST ₹248,417.88 + SGST ₹248,417.88)
   - Extracted line item taxable amounts: ₹37,398.51 + ₹6,463.18 + ₹21,261.42 + ₹27,289.18 + ₹22,788.53 = **₹115,200.82**.
   - Note: The extracted line items sum to ₹115,200.82, which does not equal either the extracted subtotal (₹9,367,123.00) or total (₹10,433,551.00).
2. **Stage 3 (Accounting Classification)**:
   - Line items mapped to Chart of Accounts (`Materials` / `General Expenses`).
3. **Stage 4 (GST/ITC Engine)**:
   - Evaluated Inter-State supply vs Intra-State taxes (`GST_MISMATCH`). Tax amount = ₹496,835.76.
4. **Stage 5 (Financial Validation)**:
   - Flags `overall_status = MISMATCH`.
   - Explicitly records `calculated.grand_total = ₹612,036.58` vs `source.total_amount = ₹10,433,551.00` (difference: ₹9,821,514.42).
5. **Stage 6 (Journal Generation)**:
   - Preview generated Debits: ₹115,200.82 (lines only) vs Credit: ₹10,433,551.00 (Vendor AP).
6. **Approval Endpoint**:
   - Recomputes authoritative journal with tax debits:
     - Total Debits: `₹115,200.82 (Expense) + ₹496,835.76 (GST) = ₹612,036.58`
     - Total Credits: `₹10,433,551.00 (AP Vendor)`
     - Difference: ₹9,821,514.42 → Blocks approval with HTTP 400.

---

## 10. Root Cause
The root cause is a **fundamental mathematical data mismatch in the extracted invoice data**:
1. The extracted line items have `taxable_amount`s summing to **₹115,200.82**.
2. Together with GST of **₹496,835.76**, the total debits equal **₹612,036.58**.
3. However, the extracted invoice header `total_amount` is **₹10,433,551.00** (and `subtotal` is **₹9,367,123.00**).
4. When `journal_generator.generate_journal_entry()` constructs double entries:
   - It computes the **Debits** from the individual line items and tax components (`₹115,200.82 + ₹496,835.76 = ₹612,036.58`).
   - It computes the **Accounts Payable Credit** from the header `total_amount` (`₹10,433,551.00`).
5. Because the extracted line items do not sum to the extracted header total, the debits and credits diverge by **₹9,821,514.42**, resulting in an unbalanced journal.

---

## 11. Is the Approval HTTP 400 Correct?
**YES**.
The backend is behaving exactly as designed according to standard double-entry accounting and ERP posting safeguards:
- In double-entry accounting, `Total Debits must strictly equal Total Credits` before an invoice can be approved and exported to the general ledger (Zoho Books).
- Approving an unbalanced journal entry (DR ₹612,036.58 vs CR ₹10,433,551.00) would corrupt the accounting books and fail Zoho Books bill creation.
- The system correctly detects `is_balanced == False` and rejects the approval request with HTTP 400.

---

## 12. What Would Need to Be Addressed Later
When fixes/updates are permitted:
1. **Invoice Data Correction**: Edit the invoice's line item taxable amounts or header amounts so the mathematical equation `Line Items + Tax == Total Amount` holds true.
2. **Reconciliation / Validation Handling in UI**: Provide a clear UI banner/reconciliation resolution workflow so users can see line item vs header discrepancies and resolve them before attempting approval.
3. **Journal Regeneration**: Ensure journal preview and authoritative generation follow identical rules for tax debit inclusion.

---

## Conclusion Summary

```text
ROOT CAUSE:
The extracted line item taxable amounts sum to ₹115,200.82 (+ ₹496,835.76 GST = ₹612,036.58 Debits), whereas the extracted invoice header total is ₹10,433,551.00 (Credits). The journal generator constructs Debits from line items/taxes and Credit from the header total, resulting in an unbalanced entry.

APPROVAL 400:
EXPECTED

CODE CHANGE REQUIRED:
NO (The 400 error is the expected safety mechanism for an unbalanced financial document; the root issue is erroneous/mismatched invoice extraction data).
```
