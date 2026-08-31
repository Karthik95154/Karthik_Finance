# TDS UI Data Path Fix Report

## 1. Actual API TDS Path & Previous Incorrect Path
The frontend API response returned the populated TDS assessment under the `tds_assessment` key. However, it also included an empty or fallback `tds` object. 

Previously, `src/app/finance/invoices/[id]/page.tsx` was hardcoded to read only from `accountingData.tds`. Since this object was empty, all fields incorrectly displayed as "Not specified" or "-".

## 2. Corrected Path
The frontend has been updated to explicitly prefer the `tds_assessment` object if it is populated. It falls back to `tds` only if `tds_assessment` is absent or completely empty.

```typescript
const tdsResultRaw = accountingData.tds_assessment || accountingData.tds || undefined;
const tdsResult: TdsResult | undefined = (tdsResultRaw && Object.keys(tdsResultRaw).length > 0) 
  ? tdsResultRaw 
  : (accountingData.tds || undefined);
```
Additionally, `TdsResult` was added to `tds_assessment` in the `AccountingOutput` interface in `src/lib/api.ts`.

## 3. Field Mappings
All mappings were preserved correctly from the previous fix:
- `tds_applicable` → TDS Applicable (or Pending Validation)
- `nature_of_payment` → Nature of Payment
- `tds_provision` / `tds_section` → TDS Section / Provision
- `tds_rate` → TDS Rate
- `tds_base_amount` → TDS Base Amount
- `proposed_tds_amount` → AI Proposed TDS
- `calculated_tds_amount` → Final TDS (only if present)
- `tds_needs_review` → Review Required
- `tds_reasoning` → Model Reasoning

## 4. Null Handling for Applicability
When `tds_applicable` is `null`, the UI no longer hides the entire TDS block. It now safely renders all available extracted fields (e.g. Rate, Provision, Proposed Amount, Reasoning) and displays a gray neutral badge stating:
**"Not determined by AI / Pending backend validation"**

## 5. Real Invoice Verification
Using invoice `7a5dc8fd-b199-4729-a700-3a9bd4fafa8a` and the cloud infrastructure invoice, the UI perfectly reads `tds_assessment` and displays the exact provision, rate, proposed amount, and reasoning, bypassing the empty `tds` object.

## 6. Build Result
`npm run build` executed and passed the TypeScript compiler and Next.js static generation checks flawlessly.

---

## FINAL VERDICT

- **TDS DATA EXISTS IN API:** PASS
- **CORRECT TDS OBJECT USED:** PASS
- **SECTION DISPLAY:** PASS
- **PROVISION DISPLAY:** PASS
- **RATE DISPLAY:** PASS
- **BASE DISPLAY:** PASS
- **AI PROPOSED TDS DISPLAY:** PASS
- **NATURE DISPLAY:** PASS
- **REASONING DISPLAY:** PASS
- **NULL APPLICABILITY HANDLING:** PASS
- **FINAL VS AI PROPOSAL SEPARATED:** PASS
- **FRONTEND BUILD:** PASS
