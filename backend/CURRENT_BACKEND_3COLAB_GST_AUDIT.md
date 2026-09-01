# CURRENT_BACKEND_3COLAB_GST_AUDIT.md

## Executive Summary & Final Verdict

| Audit Domain | Status / Result | Findings |
| :--- | :--- | :--- |
| **CURRENT VLM → COA FLOW** | **PARTIAL** | Pipeline calls Colab Qwen3-4B endpoint with normalized invoice JSON, cached Chart of Accounts, and cached Taxes. Fallback implemented if offline. |
| **CURRENT VLM → TDS FLOW** | **PARTIAL** | TDS is bundled inside Qwen3-4B Accounting response rather than an independent 3rd dedicated Colab service; backend has `tds_engine.py` for deterministic calculation. |
| **COA/TDS SAME NORMALIZED INPUT** | **PASS** | `invoice_payload` produced by `get_effective_invoice_data()` is the single normalized dictionary sent to both COA/TDS reasoning and deterministic engines. |
| **CURRENT GST SUPPLY-TYPE LOGIC** | **PASS** | Deterministic state resolution via GSTIN (2-digit prefix) + Address fallback + Explicit Place of Supply priority. INTRA vs INTER properly evaluated. |
| **IGST / CGST-SGST SEPARATION** | **PARTIAL (ISSUE IDENTIFIED)** | `gst_engine.py` does NOT arbitrarily split taxes. However, in `journal_generator.py` (lines 374-379) and `invoice_processing.py` fallback (lines 222-224), when only header `tax_total` is extracted without split, `journal_generator` falls back to splitting `tax_total / 2` into CGST + SGST if supply_type is INTRA_STATE, or IGST if INTER_STATE. |
| **ACTUAL WRONG SPLIT FOUND** | **YES (Edge cases & Fallbacks)** | 1) `invoice_processing.py` default offline fallback mock hardcodes CGST=90, SGST=90, IGST=0 with POS="35-Andaman & Nicobar Islands" (mismatched states). 2) If VLM extracts only `tax_total`, journal generator synthesizes CGST/SGST or IGST based on supply_type. |
| **ROOT CAUSE IDENTIFIED** | **YES** | Proven from source code and documented below. |

---

## PART A — CURRENT 3-COLAB / BACKEND FLOW

### 1. Where Qwen3-VL is called
- **File**: [`backend/app/services/ai_service.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/ai_service.py#L87-L144) (`AIService.extract_invoice_vlm`)
- **Invoked in**: [`backend/app/services/invoice_processing.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/invoice_processing.py#L194) (`process_invoice_background`)
- **Transport**: `POST {settings.COLAB_API_URL}/api/infer/extract-invoice` with payload `{"image_base64": "<base64_string>"}`.

### 2. Exact JSON Qwen3-VL returns
```json
{
  "confidence_score": 0.95,
  "data": {
    "invoice_number": "INV-1024",
    "invoice_date": "2026-08-15",
    "due_date": "2026-08-30",
    "vendor_name": "Acme Cloud Services",
    "vendor_gstin": "36AABCU9603R1ZM",
    "vendor_pan": "AABCU9603R",
    "vendor_address": "Hyderabad, Telangana",
    "customer_name": "Sakshi Finance",
    "customer_gstin": "29AAACH7409R1ZZ",
    "customer_address": "Bengaluru, Karnataka",
    "place_of_supply": "29-Karnataka",
    "subtotal": 10000.0,
    "tax_total": 1800.0,
    "cgst_amount": null,
    "sgst_amount": null,
    "igst_amount": 1800.0,
    "total_amount": 11800.0,
    "line_items": [
      {
        "line_index": 1,
        "description": "Cloud Compute Engine",
        "hsn_code": "998313",
        "quantity": 1.0,
        "unit_price": 10000.0,
        "taxable_amount": 10000.0,
        "igst_rate": 18.0,
        "igst_amount": 1800.0,
        "total": 11800.0
      }
    ],
    "bank_details": {},
    "additional_fields": {}
  }
}
```

### 3. Where that JSON is normalized
- **File**: [`backend/app/services/invoice_processing.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/invoice_processing.py#L19-L51) (`get_effective_invoice_data`) and lines 244-252.
- **Normalization steps**:
  1. Unwraps nested `"data"` key if present.
  2. Merges base `raw_vlm_output` with user edits from `current_vlm_output`.
  3. Parses and normalizes dates (Indian DD/MM/YYYY vs ISO YYYY-MM-DD) via `parse_and_normalize_date()`.
  4. Preserves line items array even if partially modified.

### 4. Where it is stored
- Stored directly on `invoices` table in PostgreSQL:
  - `invoice.raw_vlm_output` (Immutable initial extraction)
  - `invoice.current_vlm_output` (Working/edited version)

### 5 & 6. Where COA and TDS AI are called
- **COA AI**: Called in [`backend/app/services/accounting_service.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/accounting_service.py#L113-L174) (`AccountingService.categorize_accounting`) via `POST {settings.COLAB_ACCOUNTING_API_URL}/api/infer/categorize-accounting`.
- **TDS AI**: Currently **bundled** in the same call as COA AI (Qwen3-4B accounting returns both `accounting` line items and `tds` object). There is also a standalone deterministic [`backend/app/services/tds_engine.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/tds_engine.py).

### 7. Do COA and TDS receive the SAME normalized invoice JSON?
- **YES**. `invoice_payload` produced by `get_effective_invoice_data(invoice)` is passed to `accounting_service.categorize_accounting()` and deterministic stages.

### 8. Does COA receive invoice_json, chart_of_accounts, available_taxes?
- **YES**. See [`backend/app/services/accounting_service.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/accounting_service.py#L130-L135):
  ```python
  payload = {
      "invoice_json": invoice_json,
      "chart_of_accounts": coa,
      "available_taxes": taxes,
  }
  ```

### 9. Does TDS receive invoice_json?
- **YES**, through the same payload in `categorize-accounting`.

### 10. Local, Remote, Mocked, or Hardcoded?
- **AI Endpoints**: Remote HTTP (ngrok tunnels pointing to Colab).
- **Fallbacks**: If HTTP request to Colab fails / times out, `invoice_processing.py` provides graceful fallback dictionaries so user can continue manual review.

### 11. Environment Variables and Service URLs
From [`backend/app/core/config.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/core/config.py#L87-L91):
- `COLAB_API_URL`: Qwen3-VL Vision Engine URL.
- `COLAB_ACCOUNTING_API_URL`: Qwen3-4B Accounting URL.
- `INFERENCE_TIMEOUT`: 900.0 seconds.

### 12. HTTP Client Implementation
- Built using `httpx.AsyncClient(timeout=self.timeout)`.
- Headers include `{"Content-Type": "application/json", "ngrok-skip-browser-warning": "1"}`.

### 13 & 14. Timeout and Fallback Behavior
- Timeout defaults to 900s (15 min) for large VLM/LLM workloads.
- Health checks use a quick 4.0s timeout (`httpx.AsyncClient(timeout=4.0)`).
- On failure/timeout, errors are caught in `try...except` and structured draft fallback objects are created with `confidence_score=0.5` or `0.85`.

### 15 & 16. DB & API Fields Exposing AI Outputs
- **Database Model ([`Invoice`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/db/models.py#L216-L226))**:
  - `raw_vlm_output` (JSONB)
  - `current_vlm_output` (JSONB)
  - `accounting_output` (JSONB)
  - `current_accounting_output` (JSONB)
  - `gst_result` (JSONB)
  - `itc_result` (JSONB)
  - `financial_validation_result` (JSONB)
  - `journal_entry` (JSONB)
- **API Schemas ([`InvoiceResponse`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/schemas/invoice.py#L33-L65))**:
  - Directly exposes all 8 JSONB properties in API responses.

---

## PART B — CURRENT GST FLOW

### 1 & 2. How Supplier & Recipient State are obtained
In [`backend/app/services/gst_engine.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/gst_engine.py#L360-L387):
1. **Supplier**:
   - Primary: Extracts 2-digit state code from `vendor_gstin` using `validate_gstin` and `extract_state_code_from_gstin` (e.g. `"36AABC..."` -> `"36"`, `"Telangana"`).
   - Fallback: Scans `vendor_address` using `resolve_state_from_text`.
2. **Buyer / Recipient**:
   - Primary: Extracts from `customer_gstin` / `buyer_gstin` / `recipient_gstin`.
   - Fallback: Scans `customer_address`.

### 3. How Place of Supply (POS) is obtained
In [`backend/app/services/gst_engine.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/gst_engine.py#L389-L403) and `extract_explicit_place_of_supply`:
- **Priority 1**: Explicit header fields (`place_of_supply`, `pos`, `place_of_delivery`, `state_of_supply`).
- **Priority 2**: `additional_fields` searching keys/values for POS indicators.
- **Priority 3**: Address regex scan for `Place of Supply: ...`.
- **Priority 4 (Fallback)**: Buyer GSTIN state code.

### 4. How INTRA_STATE vs INTER_STATE is determined
- If `supplier_state_code == pos_state_code` → **`INTRA_STATE`**
- If `supplier_state_code != pos_state_code` → **`INTER_STATE`**
- If either state is unresolved → **`REVIEW_REQUIRED`**

### 5 & 6. How extracted IGST vs CGST/SGST are handled
In `gst_engine.py` (lines 434-448):
- Extracted values (`ext_cgst`, `ext_sgst`, `ext_igst`, `ext_tax_total`) are parsed and preserved under `result["extracted"]`.
- `result["calculated"]` calculates:
  - If `INTRA_STATE`: `cgst_amount = calc_cgst`, `sgst_amount = calc_sgst`, `igst_amount = 0.0`
  - If `INTER_STATE`: `igst_amount = calc_igst`, `cgst_amount = 0.0`, `sgst_amount = 0.0`

### 7. Does the engine recalculate tax?
- Yes, at the line item level (`expected_line_cgst`, `expected_line_sgst`, `expected_line_igst`), but it **does not overwrite** the extracted values; it places them side-by-side in `extracted` and `calculated` dictionaries.

### 8. Can it accidentally convert IGST into CGST + SGST?
- In `gst_engine.py`: **NO**, `gst_engine` strictly separates them.
- In `journal_generator.py` (lines 372-379): **YES, on fallback**. If `cgst_amt`, `sgst_amt`, `igst_amt` are all 0, but `tax_total > 0`, lines 376-378 do:
  ```python
  if supply_type == "INTER_STATE":
      igst_amt = tax_total
  else:
      cgst_amt = round(tax_total / 2.0, 2)
      sgst_amt = round(tax_total - cgst_amt, 2)
  ```
  If `tax_total` was extracted from an invoice without itemized taxes, this synthesis occurs.

### 9. Can tax lookup return the wrong tax ID?
In [`backend/app/services/master_data_service.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/master_data_service.py#L206-L264) (`get_zoho_tax_for_line`):
- Checks `supply_type == "INTER_STATE"`. If true, filters for tax names starting with `IGST` or containing `IGST`.
- If `INTRA_STATE`, filters for tax names starting with `GST` and **excluding** `IGST`.
- This ensures correct Zoho Tax ID resolution based on supply type.

### 10 & 11. Do Zoho Export and Journal use the same tax type?
- **Zoho Export**: Uses `gst_engine.evaluate_gst(vlm_data)` to get `supply_type` and passes it to `get_zoho_tax_for_line`.
- **Journal**: Uses `gst_result.get("supply_type")`.

### 12. Does Frontend display engine result or raw extraction?
- **Frontend** displays **both** in a comparison table: `Extracted` vs `Calculated (Deterministic)` with matching status indicators.

---

## PART C — BUG & REAL EVIDENCE ANALYSIS

### Potential / Actual Bug Scenarios Identified in Current Code

#### Scenario 1: Fallback Mock in `invoice_processing.py`
- **Location**: [`backend/app/services/invoice_processing.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/invoice_processing.py#L216-L224)
- **Code**:
  ```python
  "place_of_supply": "35-Andaman & Nicobar Islands",
  "buyer_name": "Sakshi Finance",
  "subtotal": 1000.0,
  "tax_amount": 180.0,
  "total_amount": 1180.0,
  "cgst_amount": 90.0,
  "sgst_amount": 90.0,
  "igst_amount": 0.0,
  ```
- **Bug**: Default vendor candidate has no GSTIN (defaults to None), POS is `"35"` (Andaman & Nicobar), but fallback sets `cgst_amount: 90.0` and `sgst_amount: 90.0`. When `gst_engine` runs, if buyer is in another state, this creates an immediate `GST_MISMATCH` because CGST+SGST was invented on an interstate or undetermined supply.

#### Scenario 2: Implicit Splitting in `journal_generator.py`
- **Location**: [`backend/app/services/journal_generator.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/journal_generator.py#L372-L379)
- **Trace**:
  If VLM extracts:
  `tax_total = 1800`, but `cgst_amount = null`, `sgst_amount = null`, `igst_amount = null`.
  If POS resolution resolves to `INTRA_STATE`, `journal_generator` sets:
  `cgst_amt = 900`, `sgst_amt = 900`.
  If the vendor was actually unregistered or charged a flat non-GST cess, this creates synthetic CGST/SGST lines in the journal.

---

## PART D — GST INVARIANTS COMPLIANCE

| Invariant | Evaluated In Code | Status |
| :--- | :--- | :--- |
| `INTRA_STATE` → CGST + SGST/UTGST, IGST = 0 | `gst_engine.py` line 561-563 | **ENFORCED** |
| `INTER_STATE` → IGST, CGST = 0, SGST = 0 | `gst_engine.py` line 563 | **ENFORCED** |
| `tax_total == cgst + sgst + igst + cess` | `gst_engine.py` line 540-542, `financial_validator.py` line 120-128 | **ENFORCED** with tolerance |
| Never split IGST into CGST+SGST for Interstate | `gst_engine.py` | **ENFORCED** |

---

## PART E — DOWNSTREAM APPROVAL / JOURNAL IMPACT

If an incorrect GST split occurs:
1. **GST Validation**: Status becomes `GST_MISMATCH`, adding errors to `gst_result["errors"]`.
2. **Journal Status**: Automatically forced to `REVIEW_REQUIRED` (in [`journal_generator.py:175`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/journal_generator.py#L175)).
3. **ITC Engine**: Can create wrong ITC asset line (`Input CGST` instead of `Input IGST`).
4. **Approval Block**: If journal is not balanced or requires review, Finance user must manually review/override in HITL.
5. **Zoho Export**: Export will map line items to wrong Zoho Tax IDs (e.g. `GST18` instead of `IGST18`), causing Zoho API 400 Bad Request or misclassified GSTR-3B tax returns.

---

## PART F — TWO-CHANGE IMPLEMENTATION PLAN

### CHANGE 1: Wire 3 Independent Colab Services

```
                     ┌──────────────────┐
                     │ Incoming Invoice │
                     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │ 1. Qwen3-VL      │ (Colab Service 1: Vision Extraction)
                     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │ Normalized JSON  │
                     └────┬────────┬────┘
                          │        │
            ┌─────────────┘        └─────────────┐
            ▼                                    ▼
┌──────────────────────┐              ┌──────────────────────┐
│ 2. Qwen3-4B COA      │              │ 3. Qwen3-4B TDS      │ (Colab Service 3: TDS)
│ (Colab Service 2)    │              │                      │
│ - invoice_json       │              │ - invoice_json       │
│ - chart_of_accounts  │              │                      │
│ - available_taxes    │              │                      │
└───────────┬──────────┘              └──────────┬───────────┘
            │ COA Proposal                       │ TDS Proposal
            └─────────────┬        ┌─────────────┘
                          ▼        ▼
                     ┌──────────────────┐
                     │ Stage 4: GST     │ (Deterministic)
                     └────────┬─────────┘
                              ▼
                     ┌──────────────────┐
                     │ Stage 4: ITC     │ (Deterministic)
                     └────────┬─────────┘
                              ▼
                     ┌──────────────────┐
                     │ Stage 5: FinVal  │ (Deterministic Reconciliation)
                     └────────┬─────────┘
                              ▼
                     ┌──────────────────┐
                     │ Stage 6: Journal │ (Authoritative General Ledger)
                     └────────┬─────────┘
                              ▼
                     ┌──────────────────┐
                     │ Database / API   │
                     └──────────────────┘
```

#### Detailed Architecture Plan for Change 1:
1. **Configuration ([`config.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/core/config.py))**:
   - Add `COLAB_TDS_API_URL: str` to support the 3rd independent Colab instance.
   - Maintain `COLAB_API_URL` (Qwen3-VL) and `COLAB_ACCOUNTING_API_URL` (Qwen3-4B COA).
2. **New Service File ([`tds_service.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/tds_service.py))**:
   - Implement `TDSService` with `check_health_detailed()` and `assess_tds(invoice_json: Dict[str, Any])`.
   - Endpoint: `POST {COLAB_TDS_API_URL}/api/infer/assess-tds`.
3. **Pipeline Orchestrator ([`invoice_processing.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/invoice_processing.py))**:
   - In `process_invoice_background` and `process_accounting_only_background`:
     - Execute `coa_task = accounting_service.categorize_accounting(...)` and `tds_task = tds_service.assess_tds(...)` concurrently via `asyncio.gather()`.
     - Pass both results downstream into `itc_engine`, `financial_validator`, and `journal_generator`.
4. **Health Check ([`health.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/api/v1/health.py))**:
   - Add 3rd health monitor for `colab_tds`.

---

### CHANGE 2: Audit & Fix GST Tax-Type Handling

#### Detailed Architecture Plan for Change 2:
1. **Strict Invariant Enforcement in [`gst_engine.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/gst_engine.py)**:
   - Ensure `INTRA_STATE` sets `calculated.igst_amount = 0.0` strictly.
   - Ensure `INTER_STATE` sets `calculated.cgst_amount = 0.0` and `calculated.sgst_amount = 0.0` strictly.
   - If extracted taxes disagree with deterministic supply type, **do not alter extracted taxes**; flag `validation_status = "GST_MISMATCH"` with clear evidence.
2. **No Invented Split in [`journal_generator.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/journal_generator.py)**:
   - Remove automatic 50/50 splitting of unitemized `tax_total` into CGST/SGST if no explicit line or header breakdown exists.
   - Instead, if `supply_type == "INTRA_STATE"` and only `tax_total` exists without split, flag for review rather than synthesizing split amounts.
3. **Clean Up Fallbacks in [`invoice_processing.py`](file:///c:/Users/Admin/Desktop/Simple_Finance_module/backend/app/services/invoice_processing.py)**:
   - Update fallback mock draft values so state codes match supply type cleanly (e.g. Telangana supplier with Telangana buyer).

---

## Required Test Plan & Verification Strategy

1. **Unit Tests for 3-Colab Architecture**:
   - Test independent COA Colab call with mock HTTP server.
   - Test independent TDS Colab call with mock HTTP server.
   - Test parallel execution via `asyncio.gather`.
   - Test fallback resilience when 1, 2, or all 3 Colab services are offline.
2. **Deterministic GST Tests**:
   - Test Intra-state (36 -> 36) = CGST (9%) + SGST (9%), IGST = 0.
   - Test Inter-state (07 -> 27) = IGST (18%), CGST = 0, SGST = 0.
   - Test explicit POS override (Supplier 36, Buyer 36, POS 29) = Inter-State (IGST 18%).
   - Test mismatch detection when Inter-State invoice has CGST/SGST in extraction.
   - Test Zoho tax ID resolution for both supply types.
