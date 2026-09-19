# OpenAI GPT-5.6 Terra Prompt & Integration Audit

**Date of Audit**: September 19, 2026  
**Target Model**: `gpt-5.6-terra`  
**Provider**: Direct OpenAI API (`AsyncOpenAI`)  
**Backend File**: [`ai_service.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/ai_service.py)  

---

## 1. Executive Summary: Current Integration vs Official Guidance

SAKSHI Finance recently transitioned from legacy multi-stage Colab/vLLM endpoints (Qwen/Kimi) to direct OpenAI multimodal inference targeting `gpt-5.6-terra`. While the integration successfully removes flaky reverse SSH tunnels and unifies invoice extraction into a single async API call, this audit reveals critical architectural and prompt design misalignments with OpenAI's official guidance for `gpt-5.6-terra`.

Specifically:
1. **API Endpoint Choice**: The integration uses `client.chat.completions.create` with `response_format={"type": "json_object"}` rather than official **Structured Outputs** (`response_format={"type": "json_schema", ...}`) or the modern **Responses API**.
2. **Prompt Size & Redundancy**: The prompt is **31,408 characters (~7,852 tokens)** excluding image payloads, consisting of an embedded JSON example schema that duplicates Python contracts, extensive tax charts, and accounting rules.
3. **Statutory Logic Bleed**: The prompt forces the LLM to perform statutory tax and threshold calculations (e.g. comparing Section 393 entries, calculating 1% vs 2% contractor rates, evaluating RCM) that our deterministic backend engines (`tds_engine.py`, `gst_engine.py`, `itc_engine.py`) perform with 100% mathematical precision.

---

## 2. Prompt Metrics & Cost / Latency Profile

| Metric | Measured Current Value | OpenAI Best Practice | Assessment |
| :--- | :--- | :--- | :--- |
| **System Prompt Length** | 27,516 characters (~6,879 tokens) | < 2,500 tokens | **EXCESSIVE (2.75x target)** |
| **User Prompt Length** | 3,892 characters (~973 tokens) | Dynamic invoice metadata + active COA | **OPTIMAL** |
| **Total Prompt Tokens (Text)** | **~7,852 tokens** | < 3,500 tokens | **HIGH OVERHEAD** |
| **Image Payload (1 page @ 150 DPI)** | ~700 - 1,400 image tokens | detail="auto" | **EFFICIENT** |
| **Total Request Tokens** | **~8,800 - 10,500 tokens** | ~4,000 - 5,000 tokens | **2x COST & LATENCY** |
| **Max Completion Tokens** | 8,192 tokens | 4,096 tokens | Safe, but higher latency allocation |
| **API Format** | Chat Completions (`json_object`) | Structured Outputs (`json_schema`) | **SUB-OPTIMAL** |
| **Reasoning Effort Setting** | Unset (Default) | `reasoning_effort="low"` for extraction | **MISSING** |

---

## 3. Official OpenAI Guidance: Match vs Mismatch

### A. API Selection & Structured Outputs
* **Official Guidance**: For deterministic data extraction into typed enterprise schemas, OpenAI strongly recommends **Structured Outputs** with strict JSON Schema (`strict: true`). This guarantees that 100% of outputs conform to the contract keys and datatypes without missing keys or hallucinated formats.
* **Current Implementation**:
  ```python
  kwargs = {
      "model": model,
      "messages": messages,
      "response_format": {"type": "json_object"},
      "max_completion_tokens": max_tokens,
  }
  ```
* **Mismatch**: `response_format={"type": "json_object"}` only ensures valid JSON syntax; it **does NOT guarantee** key presence, types, or nested structure. As a result, [`ai_service.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/ai_service.py#L876-L885) must run a fallback loop to populate missing top-level keys with empty defaults.
* **Required Change**: Compile [`FIXED_JSON_STRUCTURE`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/ai_service.py#L25-L145) or Pydantic `InvoiceExtractionSchema` into an official JSON Schema and pass it via `response_format={"type": "json_schema", "json_schema": {"name": "invoice_extraction", "strict": True, "schema": ...}}`.

### B. Reasoning Effort Configuration
* **Official Guidance**: `gpt-5.6-terra` features dynamic reasoning. For multimodal document extraction tasks where visual grounding and OCR are paramount, OpenAI recommends specifying a reasoning level (e.g. `reasoning_effort="low"` or `"medium"`) to avoid runaway latency and token spend on internal chain-of-thought.
* **Current Implementation**: No `reasoning_effort` argument is passed.
* **Mismatch**: The model executes default unbounded reasoning, leading to 25s–60s extraction latency on complex multi-page invoices.
* **Required Change**: Configure `reasoning_effort="low"` for high-speed document extraction.

### C. System Prompt Bloat & Contract Duplication
* **Official Guidance**: Prompts should be outcome-first, concise, and avoid embedding 200-line JSON schemas in natural language text when structured outputs are available.
* **Current Implementation**:
  - [`COMPACT_ACCOUNTING_SYSTEM_PROMPT`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/ai_service.py#L152-L615) contains 463 lines of text.
  - Lines 463–593 contain an entire 130-line formatted JSON contract example string, which is already defined in Python as `FIXED_JSON_STRUCTURE`.
  - Lines 290–311 embed a 22-item TDS comparison chart with exact rates and section codes.
* **Mismatch**: High latency and token costs. Repeating the schema in prompt text causes prompt bloat and consumes ~1,200 tokens per request for zero informational gain.
* **Required Change**: Remove the embedded JSON example from the prompt once JSON Schema is passed via `response_format`.

### D. Division of Responsibilities: AI Proposal vs Deterministic Authority
* **Official Guidance & SAKSHI Architecture**: The AI model should observe visual evidence (OCR, line descriptions, numbers, vendor entity) and propose candidate classifications. The AI **must not** be tasked with performing arithmetic reconciliation, complex threshold evaluation, or multi-year tax determinations.
* **Current Implementation**:
  - The prompt instructs the model:
    > "Always calculate TDS on any eligible service line regardless of single-invoice amount. Set tds_applicable_candidate = true." (Line 327)
    > "Provide rate_candidate strictly based on the Section 393 Table entries above... 1% for Individual/HUF (PAN 4th letter 'P'/'H'), 2% for Corporate entities." (Line 331)
    > "subtotal_mismatch: true if line taxable sums != printed subtotal..." (Line 422)
* **Mismatch**: The LLM is forced to do manual arithmetic checks that [`financial_validator.py`](file:///home/gollapydisriabhishek/Documents/sakshi_AI_Finance/Sakshi_Finance/backend/app/services/financial_validator.py) already executes deterministically with sub-cent precision.
* **Required Change**: Strip arithmetic reconciliation requirements from the prompt. Instruct the LLM to extract verbatim numbers; let `FinancialValidator` perform all equality and discrepancy checks.

---

## 4. Line-by-Line Section Recommendation for System Prompt

| Prompt Section | Current Lines | Status | Action Required | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **A. Role & Core Behavior** | 152–163 | Keep | **Retain (Simplify)** | Sets first-pass extraction boundary |
| **B. Source Priority** | 164–173 | Keep | **Retain** | Enforces visual evidence > COA > statutory law |
| **C. Anti-Hallucination** | 174–194 | Keep | **Retain** | Critical for zero data fabrication and null vs 0.0 discipline |
| **D. Invoice Extraction Spec** | 195–238 | Keep | **Retain (Refactor)** | Core field extraction guidance (Header, Vendor, Customer, Bank, Lines) |
| **E. GST Statutory Interpretation** | 239–270 | Modify | **Condense by 50%** | Remove redundant POS explanations; keep basic POS and candidate RCM flags |
| **F. TDS Statutory Interpretation** | 271–351 | Modify | **Remove Chart (-1,500 tokens)** | Delete lines 290–311 (TDS Chart). Backend `tds_engine.py` has the master table. LLM only needs to provide payment nature. |
| **G. TCS Section** | 352–359 | Keep | **Retain** | Short and clean |
| **H. ITC Eligibility** | 360–390 | Keep | **Retain** | Excellent Section 17(5) blocked risk checklist |
| **I. Chart of Accounts (COA)** | 391–407 | Keep | **Retain** | Strict instruction to match against runtime COA only |
| **J. GL Classification** | 408–418 | Keep | **Retain** | Suggests pattern without generating journal debits/credits |
| **K. Validation & Review Flags** | 419–456 | Modify | **Condense** | Remove arithmetic checking; keep standardized review flag identifiers |
| **L. Fixed JSON Contract** | 457–594 | **DELETE** | **Remove completely (-1,200 tokens)** | Redundant once `json_schema` Structured Outputs is passed |
| **M. Division of Responsibility** | 595–609 | Keep | **Retain** | Reasserts AI proposal vs backend binding authority |
| **N. Output Discipline** | 610–616 | Keep | **Retain** | Valid JSON only |

---

## 5. Summary of Savings

* **Estimated System Prompt Tokens**: Reduced from **~6,879 tokens to ~2,800 tokens (59% reduction)**.
* **Request Latency**: Expected improvement of **35% to 50%** due to lower prompt cache processing and reduced reasoning steps.
* **Reliability**: 100% schema conformance via JSON Schema `strict: true`, eliminating runtime JSON repair or default injection.
