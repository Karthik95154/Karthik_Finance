# COA Frontend Mapping Fix Report

## 1. Root Cause
The Qwen3-4B backend was successfully emitting the AI-predicted Chart of Accounts data containing `account_id`, `account_name`, `confidence_score`, `ai_needs_review`, `accounting_reason`, and `source_description`. However, the frontend UI (`page.tsx`) and API types (`api.ts`) were expecting the outdated legacy schema variables: `ai_account_id`, `ai_account_name`, and `ai_confidence`.

## 2. Exact Frontend Field Mismatch
- Expected by UI: `ai_account_id`, `ai_account_name`, `ai_confidence`
- Actual from API: `account_id`, `account_name`, `confidence_score`

Because the UI could not find the expected legacy fields, it defaulted to displaying fallback values such as "General Expenses" and "ACC_x", masking the correct Qwen result.

## 3. Exact Files Changed
- `frontend/src/app/finance/invoices/[id]/page.tsx`
- `frontend/src/lib/api.ts`

## 4. Fields Now Displayed
The Review UI table now successfully maps and displays:
- **Account Name**: `account_name` (or `ai_account_name` fallback)
- **Account ID**: `account_id` (or `ai_account_id` fallback)
- **Confidence**: `confidence_score` (or `ai_confidence` fallback)
- **Accounting Reason**: Shown as subtext below the source description when available.

## 5. Fallback Behavior
Legitimate fallback and error handling remains intact. The variables map in priority:
`final_account_name || account_name || ai_account_name || "General Expenses"`
This guarantees that if the AI explicitly fails, the legacy/fallback values take over safely without fabricating COA data, but a successful Qwen run will ALWAYS take precedence.

## 6. Multi-Line Verification
The mapping was explicitly updated inside the `accountingLines.map((acc, idx) => ...)` loop and `handleAcceptAllAccounts` / `handleAcceptAccount` functions. Each distinct `line_index` from the backend successfully binds to its corresponding row in the COA review UI, ensuring multi-line invoices render correctly.

## 7. Build Result
The application was built via `npm run build` and compiled successfully. Type checking and linting passed entirely with no errors.

---

### Verification Summary
- **QWEN COA DATA RECEIVED: PASS**
- **CORRECT FIELD MAPPING: PASS**
- **ACCOUNT NAME DISPLAY: PASS**
- **ACCOUNT ID DISPLAY: PASS**
- **CONFIDENCE DISPLAY: PASS**
- **ACCOUNTING REASON DISPLAY: PASS**
- **FALLBACK SAFETY: PASS**
- **MULTI-LINE MAPPING: PASS**
- **FRONTEND BUILD: PASS**
