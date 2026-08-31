# Zoho Export HTTP 400 After Successful Approval — Root Cause Report

**Investigation Date:** August 31, 2026  
**Target Invoice ID:** `7b314d41-b251-4bfd-97c9-dbbf15d0bb02`  
**Investigation Mode:** Strictly Read-Only (No code changes, no database updates, no migrations).

---

## 1. Invoice State After Approval

Inspection of the database record for invoice `7b314d41-b251-4bfd-97c9-dbbf15d0bb02` yielded:

- **Invoice ID:** `7b314d41-b251-4bfd-97c9-dbbf15d0bb02`
- **Tenant ID:** `default-tenant-001`
- **Invoice Status (`status`):** `COMPLETED`
- **Approval Status (`approval_status`):** `APPROVED`
- **Export Status (`export_status`):** `NOT_EXPORTED`
- **Locked At Timestamp (`locked_at`):** `2026-08-31 07:07:22.035800+00:00`
- **JSONB `invoice.journal_entry` Status:** `BALANCED`
- **JSONB `is_balanced`:** `True`
- **JSONB Total Debit:** ₹59,000.00
- **JSONB Total Credit:** ₹59,000.00

---

## 2. Relational Journal State

Inspection of `journal_entries` and `journal_lines` for this invoice yielded:

- **Journal Entry ID:** `656a8b5b-553b-4cca-95c0-d7ef37015c24`
- **Invoice ID:** `7b314d41-b251-4bfd-97c9-dbbf15d0bb02`
- **Tenant ID:** `default-tenant-001`
- **Relational Status (`JournalEntry.status`):** **`BALANCED`**
- **Relational `JournalEntry.balanced`:** `True`
- **Relational `JournalEntry.is_balanced`:** `True`
- **Relational Total Debit:** ₹59,000.00
- **Relational Total Credit:** ₹59,000.00
- **Line Count:** 4
  - Line 1: `ACC_1` (*Operating expenses*) | `EXPENSE` | Dr: ₹50,000.00 | Cr: ₹0.00
  - Line 2: `TAX_INP_CGST` (*Input CGST*) | `INPUT_TAX` | Dr: ₹4,500.00 | Cr: ₹0.00
  - Line 3: `TAX_INP_SGST` (*Input SGST / UTGST*) | `INPUT_TAX` | Dr: ₹4,500.00 | Cr: ₹0.00
  - Line 4: `LIAB_AP` (*Accounts Payable - NimbusStack Cloud Solutions Pvt. Ltd.*) | `ACCOUNTS_PAYABLE` | Dr: ₹0.00 | Cr: ₹59,000.00

---

## 3. Comparison: JSONB vs Relational Journal

| Property | JSONB `invoice.journal_entry` | Relational `JournalEntry` | Match Status |
|---|---|---|---|
| **Total Debit** | ₹59,000.00 | ₹59,000.00 | **IDENTICAL** |
| **Total Credit** | ₹59,000.00 | ₹59,000.00 | **IDENTICAL** |
| **Is Balanced** | `True` | `True` | **IDENTICAL** |
| **Lines Breakdown** | 4 lines (Expense, CGST, SGST, AP) | 4 lines (Expense, CGST, SGST, AP) | **IDENTICAL** |
| **Status String** | `"BALANCED"` | `"BALANCED"` | **IDENTICAL** |

**Determination:** **IDENTICAL**. The invoice and relational database are 100% synchronized and balanced.

---

## 4. Approval Flow Analysis

In [backend/app/api/v1/review.py](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/api/v1/review.py) (`approve_invoice`):

1. `approve_invoice` generates the authoritative journal via `journal_generator.generate_journal(...)`.
2. Sets `invoice.journal_entry = authoritative_journal_dict` (which has `status: "BALANCED"`, `is_balanced: True`).
3. Calls `sync_relational_journal(session=db, invoice_id=invoice_id, journal_dict=authoritative_journal_dict, tenant_id=tenant_id)`.
4. In [backend/app/services/journal_generator.py](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/journal_generator.py) (lines 886–905):
   ```python
   status_val = journal_dict.get("status", "BALANCED" if is_bal else "UNBALANCED")
   # Sets JournalEntry.status = "BALANCED"
   ```
5. Sets `invoice.approval_status = "APPROVED"` on the `Invoice` model and commits the transaction.

---

## 5. Export Flow & Failing Condition Analysis

In [backend/app/services/export_service.py](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/export_service.py) (lines 62–71):

```python
# 3. Check Balanced Journal Entry Existence
journal_query = select(JournalEntry).where(
    JournalEntry.invoice_id == invoice_id,
    JournalEntry.tenant_id == tenant_id,
    JournalEntry.status == "APPROVED",  # <--- CRITICAL FAILING CONDITION
)
j_res = await db.execute(journal_query)
journal_entry = j_res.scalar_one_or_none()
if not journal_entry or not journal_entry.is_balanced:
    raise ValueError("Invoice cannot be exported without an approved, balanced General Ledger journal entry.")
```

### Actual Evaluated Values:
- `invoice.approval_status`: `"APPROVED"` (Passes step 2)
- `JournalEntry.invoice_id`: `7b314d41-b251-4bfd-97c9-dbbf15d0bb02` (Matches)
- `JournalEntry.tenant_id`: `default-tenant-001` (Matches)
- `JournalEntry.status` in Database: **`"BALANCED"`**
- **Query Filter `JournalEntry.status == "APPROVED"`:** **`"BALANCED" == "APPROVED"` $\implies$ `FALSE`**
- `journal_entry`: **`None`**
- Result: **HTTP 400 Bad Request** with message:
  `"Invoice cannot be exported without an approved, balanced General Ledger journal entry."`

---

## 6. Root Cause

### Category: **Status Field Domain Mismatch Between Model & Export Query**

1. **State Machine Definitions:**
   - **`Invoice.approval_status`** tracks the governance approval state: `['PENDING_REVIEW', 'APPROVED', 'REJECTED']`.
   - **`JournalEntry.status`** (and `journal_dict["status"]`) tracks double-entry mathematical validity / state: `['BALANCED', 'UNBALANCED', 'REVIEW_REQUIRED', 'DRAFT', 'POSTED']` as defined on line 285 of [backend/app/db/models.py](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/db/models.py).
2. **The Defect:**
   - `export_service.py` attempted to filter `JournalEntry.status == "APPROVED"`.
   - Because `sync_relational_journal()` saves the mathematical status `status="BALANCED"`, the query `select(JournalEntry).where(JournalEntry.status == "APPROVED")` returned `None`.
   - When `invoice.approval_status == "APPROVED"` and `journal_entry.is_balanced == True` (or `status == "BALANCED"`), the export query erroneously assumed no valid journal existed.

---

## 7. Downstream Path & Zoho Payload Trace

Because step 3 threw a `ValueError` (HTTP 400), **the Zoho API was NEVER reached**.

### What Happens Downstream Once the Precondition Passes:
In `export_service.py` (lines 83–201):
1. Reads `invoice.current_vlm_output` / `raw_vlm_output` for invoice headers and line descriptions/quantities/tax rates.
2. Reads `invoice.current_accounting_output` for finance-approved Chart of Accounts (`approved_account_id` / `final_account_id`).
3. Searches/creates vendor contact in Zoho via `search_vendor` / `create_vendor`.
4. Assembles `bill_payload` with strict `approved_account_id` mappings and matching tax rates.
5. Issues idempotent `create_bill` call to Zoho Books.

---

## 8. Correct Architectural Fix

1. In [backend/app/services/export_service.py](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/export_service.py):
   Query `JournalEntry` for the invoice and check:
   ```python
   journal_query = select(JournalEntry).where(
       JournalEntry.invoice_id == invoice_id,
       JournalEntry.tenant_id == tenant_id,
   )
   j_res = await db.execute(journal_query)
   journal_entry = j_res.scalar_one_or_none()
   if not journal_entry or not journal_entry.is_balanced or journal_entry.status not in ("BALANCED", "APPROVED", "POSTED"):
       raise ValueError("Invoice cannot be exported without an approved, balanced General Ledger journal entry.")
   ```
2. Alternatively/Additionally in `approve_invoice`:
   When an invoice is approved, if `JournalEntry.status` should also reflect `"APPROVED"` / `"POSTED"` or `"BALANCED"`, keep them aligned. Supporting `JournalEntry.is_balanced == True` and `invoice.approval_status == "APPROVED"` ensures complete architectural consistency.

---

## 9. Final Summary

```
APPROVAL STATE:
Invoice ID: 7b314d41-b251-4bfd-97c9-dbbf15d0bb02
Invoice.status: COMPLETED
Invoice.approval_status: APPROVED
Invoice.locked_at: 2026-08-31 07:07:22.035800+00:00

JOURNAL JSONB:
Status: BALANCED
is_balanced: True
total_debit: 59000.0
total_credit: 59000.0
Lines: 4

RELATIONAL JOURNAL:
Entry ID: 656a8b5b-553b-4cca-95c0-d7ef37015c24
JournalEntry.status: BALANCED
JournalEntry.is_balanced: True
JournalEntry.balanced: True
total_debit: 59000.0
total_credit: 59000.0
Lines: 4 (Dr ₹50k, Dr ₹4.5k CGST, Dr ₹4.5k SGST, Cr ₹59k AP)

EXPORT CHECK:
Checked: Invoice.approval_status == "APPROVED" -> PASS
Checked: JournalEntry(status="APPROVED") -> FAIL (Returned None because status="BALANCED")

FAILING CONDITION:
select(JournalEntry).where(JournalEntry.status == "APPROVED") evaluated to None because the General Ledger engine correctly recorded status="BALANCED".

ROOT CAUSE:
export_service.py filtered JournalEntry.status == "APPROVED" instead of checking JournalEntry.is_balanced == True (or status in ("BALANCED", "APPROVED", "POSTED")) alongside invoice.approval_status == "APPROVED".

ZOHO API REACHED:
NO (Blocked at precondition step 3 before any Zoho network call).

CODE CHANGE REQUIRED:
YES (Align export_service.py query with the actual JournalEntry status domain).
```
