# Complete SAKSHI Finance Fix & Hardening Roadmap

**Status**: Planning & Architecture Phase  
**Branch**: `Abhishek_Changes_from_local`  
**Execution Rule**: ANALYSIS ONLY COMPLETED — NO CODE MODIFIED DURING AUDIT  

This roadmap details the prioritized, phased execution plan to resolve all P0, P1, P2, and P3 findings identified in the comprehensive system audit.

---

## Phase 1: Compliance & Accounting Critical Fixes (P0)

### Step 1.1: Fix Journal Generator RCM Liability & Reverse Charge Accounting
* **Files**: [`journal_generator.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/journal_generator.py), [`export_service.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/export_service.py)
* **Goal**:
  - When `is_reverse_charge == True`:
    1. Do NOT book RCM tax to `ACCOUNTS_PAYABLE` (Vendor is NOT paid GST under RCM).
    2. Credit `RCM_GST_PAYABLE` (Recipient liability to discharge in cash to Government).
    3. Debit `INPUT_GST` (Eligible ITC available upon cash payment under Section 16(2)).
    4. Vendor Payable must equal strictly Pre-tax Base Amount less TDS.
* **Test to Prove**: Create `backend/tests/test_rcm_journal_accounting.py` asserting that an RCM invoice of ₹10,000 + ₹1,800 tax credits Vendor AP for ₹10,000 (or ₹9,800 net of TDS) and credits RCM GST Payable for ₹1,800.

### Step 1.2: Remove Unsafe TDS Rate Fallbacks in Engine & Adapter
* **Files**: [`tds_engine.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/tds_engine.py#L557), [`model_response_adapter.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/model_response_adapter.py#L966)
* **Goal**:
  - Eliminate all instances where an unknown or unclassified service defaults to `rate = 2.0%` or `rate = 10.0%`.
  - When provision/nature is unresolved, set `rate = None`, `tds_amount = None`, `tds_needs_review = True`, and attach `TDS_AMBIGUOUS_CLASSIFICATION`.
  - Prohibit journal generation/approval when TDS is in `REVIEW_REQUIRED` state.
* **Test to Prove**: Run `backend/tests/test_tds_p0_fixtures.py` verifying that ambiguous services require review and never receive an arbitrary 2% rate.

### Step 1.3: Enforce Review Required Blocking Gate on Journal Approval & Export
* **Files**: [`review.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/api/v1/review.py#L353-L355), [`export_service.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/export_service.py#L243-L250)
* **Goal**:
  - Reinstate strict blocking: If `financial_validation_result.overall_status == "MISMATCH"` or `itc_status == "REVIEW_REQUIRED"` or `tds_status == "REVIEW_REQUIRED"`, the `/approve` endpoint must return `400 Bad Request` unless explicitly overridden via HITL review snapshot.
* **Test to Prove**: Create `backend/tests/test_review_blocking_invariants.py`.

---

## Phase 2: Statutory Determination & Engine Hardening (P1)

### Step 2.1: Implement Deterministic Statutory RCM Category Classifier
* **Files**: [`gst_engine.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/gst_engine.py), [`itc_engine.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/itc_engine.py)
* **Goal**:
  - Implement rule engine detecting Notification 13/2017 & 29/2018 statutory RCM categories:
    * **Legal Services**: SAC 9982 or keywords ("Advocate", "Legal Counsel", "Law Firm").
    * **GTA Services**: SAC 9965 where tax rate is 5% or uncharged.
    * **Director Services**: Line description contains director fees/sitting fees.
    * **Security Services**: SAC 9985 where supplier entity is Individual/Firm/LLP (PAN 4th letter 'P'/'F') and recipient is registered entity.
* **Test to Prove**: Create `backend/tests/test_rcm_statutory_auto_detection.py`.

### Step 2.2: Implement Multi-Invoice Cumulative FY Threshold Tracking for TDS
* **Files**: [`tds_engine.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/tds_engine.py), [`master_data_service.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/master_data_service.py), new model `VendorTaxHistory`
* **Goal**:
  - Support cumulative financial year turnover aggregation per `(tenant_id, organization_id, vendor_pan, financial_year)`.
  - Track:
    * Contractor payments towards ₹1,00,000 FY limit (Section 393 Sl. 6(i)).
    * Goods procurement towards ₹50,00,000 FY limit (Section 393 Sl. 8(ii)).
    * Professional fees towards ₹30,000 FY limit.
  - Correctly calculate tax only on the *excess* amount when crossing the ₹50L threshold under 194Q / Sl. 8(ii).
* **Test to Prove**: Create `backend/tests/test_tds_cumulative_fy_aggregation.py`.

---

## Phase 3: AI Service & OpenAI GPT-5.6 Terra Optimization (P2)

### Step 3.1: Migrate to OpenAI Structured Outputs (JSON Schema)
* **Files**: [`ai_service.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/ai_service.py)
* **Goal**:
  - Define formal Pydantic schema `InvoiceExtractionVLMContract` and pass as `response_format={"type": "json_schema", "json_schema": {"name": "invoice_extraction", "strict": True, "schema": ...}}`.
  - Remove fallback key injection loops in `_extract_and_validate_json`.

### Step 3.2: Refactor & Condense System Prompt
* **Files**: [`ai_service.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/ai_service.py)
* **Goal**:
  - Delete lines 463–593 (embedded JSON string example).
  - Delete lines 290–311 (redundant TDS comparison chart).
  - Strip arithmetic instructions; task LLM with verbatim extraction only.
  - Set `reasoning_effort="low"` for extraction workload.
  - Reduce prompt token size by 59%.

---

## Phase 4: System Hardening & Test Suite Remediation (P3)

### Step 4.1: Fix Failing Legacy Tests & Broken Async Fixtures
* **Files**: [`test_stage2.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/tests/test_stage2.py), [`test_ai_service_async_polling.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/tests/test_ai_service_async_polling.py), [`test_e2e_live.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/tests/test_e2e_live.py)
* **Goal**:
  - Update `test_stage2.py` mocks to reflect PyMuPDF stream decoding and direct OpenAI client calls instead of dead Colab `httpx` posts.
  - Fix unawaited `AsyncMock` calls causing RuntimeWarnings across audit logs and journal lines.
  - Remove or gate `test_e2e_live.py` behind a live server flag.

### Step 4.2: Unify Tolerances into Central Configuration
* **Files**: [`config.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/core/config.py), [`financial_validator.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/financial_validator.py), [`journal_generator.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/journal_generator.py), [`export_service.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/export_service.py)
* **Goal**:
  - Replace hardcoded `1.0`, `2.0`, and `0.05` with `settings.MONETARY_TOLERANCE_INR` and `settings.PERCENTAGE_TOLERANCE_EPSILON`.
