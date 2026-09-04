# Forensic Investigation Report: Origin of Incorrect Invoice Data in Review UI

**Target Invoice**: `invoice_2page_2.pdf`  
**Database Invoice ID**: `e30280f7-fe16-4798-a1f0-e5eca175ac68`  
**VLM Request ID**: `VLM-20260902-105101-0002`  
**Investigation Mode**: **READ-ONLY Forensic Analysis (Zero Code Modifications)**  
**Final Verdict**: **`BACKEND PERSISTENCE BUG`**

---

## 1. Executive Summary & Root Cause

The discrepancy between the visible invoice document and the Frontend Review UI is caused by a **silent exception fallback in the backend processing pipeline**:

1. **The PDF Document & VLM Model Extracted Correct Data**:
   - `VLM-20260902-105101-0002` on Colab successfully extracted:
     - Invoice Number: **`INV-2026-1722`**
     - Vendor: **`Satpura Industrial Fabrications Pvt. Ltd.`**
     - Vendor GSTIN: **`36AABCS7845R1Z4`**
     - Place of Supply: **`Maharashtra (27)`**
     - Subtotal: **`₹973,600.00`**

2. **The Backend Hit an HTTP Exception and Generated Synthetic Draft Data**:
   - During the 334.07-second GPU inference run, the HTTP connection between the FastAPI backend and the Colab ngrok endpoint was interrupted (client-side timeout, connection drop, or network error).
   - In [`backend/app/services/invoice_processing.py`](file:///c:/Users/User/Desktop/sakshi_raju/backend/app/services/invoice_processing.py#L260-L305), the `try...except Exception as vlm_err` block caught the error and initialized a synthetic "structured draft workspace":
     - `clean_inv_num = f"INV-{str(invoice.id)[:8].upper()}"` $\rightarrow$ **`"INV-E30280F7"`**
     - `vendor_candidate = base_fname.split(".")[0].strip()` $\rightarrow$ **`"invoice 2page 2"`**
     - Hardcoded `vendor_gstin` $\rightarrow$ **`"36AABCU9603R1ZM"`**
     - Hardcoded `place_of_supply` $\rightarrow$ **`"36-Telangana"`**
     - Hardcoded `subtotal` $\rightarrow$ **`1000.0`**

3. **Backend Persisted the Draft into PostgreSQL**:
   - Lines 317–322 committed this synthetic draft object into `invoice.raw_vlm_output` and `invoice.current_vlm_output`.

4. **Frontend Accurately Displays What is in the Database**:
   - `GET /api/v1/invoices/e30280f7-fe16-4798-a1f0-e5eca175ac68` returns the synthetic draft payload stored in PostgreSQL.
   - The Frontend Review UI faithfully renders the values returned by the backend API.

---

## 2. Field-by-Field Comparison Table

| Field Name | Expected Document Value (Visible in PDF) | VLM Model Output (`VLM-20260902-105101-0002`) | PostgreSQL DB Value (`raw_vlm_output.data`) | Frontend Review UI Displayed Value | Origin of Displayed Value |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Invoice Number** | `INV-2026-1722` | `INV-2026-1722` | `INV-E30280F7` | **`INV-E30280F7`** | `f"INV-{invoice.id[:8]}"` ([`invoice_processing.py:265`](file:///c:/Users/User/Desktop/sakshi_raju/backend/app/services/invoice_processing.py#L265)) |
| **Vendor Name** | `Satpura Industrial Fabrications Pvt. Ltd.` | `Satpura Industrial Fabrications Pvt. Ltd.` | `invoice 2page 2` | **`invoice 2page 2`** | `file_name.split('.')[0]` ([`invoice_processing.py:268`](file:///c:/Users/User/Desktop/sakshi_raju/backend/app/services/invoice_processing.py#L268)) |
| **Vendor GSTIN** | `36AABCS7845R1Z4` | `36AABCS7845R1Z4` | `36AABCU9603R1ZM` | **`36AABCU9603R1ZM`** | Fallback template ([`invoice_processing.py:279`](file:///c:/Users/User/Desktop/sakshi_raju/backend/app/services/invoice_processing.py#L279)) |
| **Vendor PAN** | `AABCS7845R` | `AABCS7845R` | `AABCU9603R` | **`AABCU9603R`** | Fallback template ([`invoice_processing.py:280`](file:///c:/Users/User/Desktop/sakshi_raju/backend/app/services/invoice_processing.py#L280)) |
| **Buyer Name** | `Konkan Retail Ventures Pvt. Ltd.` | `Konkan Retail Ventures Pvt. Ltd.` | `Sakshi Finance` | **`Sakshi Finance`** | Fallback template ([`invoice_processing.py:282`](file:///c:/Users/User/Desktop/sakshi_raju/backend/app/services/invoice_processing.py#L282)) |
| **Buyer GSTIN** | `27AAAAA0000A1Z5` | `27AAAAA0000A1Z5` | `36AAACH7409R1ZZ` | **`36AAACH7409R1ZZ`** | Fallback template ([`invoice_processing.py:283`](file:///c:/Users/User/Desktop/sakshi_raju/backend/app/services/invoice_processing.py#L283)) |
| **Place of Supply** | `Maharashtra (27)` | `Maharashtra (27)` | `36-Telangana` | **`36-Telangana`** | Fallback template ([`invoice_processing.py:281`](file:///c:/Users/User/Desktop/sakshi_raju/backend/app/services/invoice_processing.py#L281)) |
| **Subtotal** | `₹973,600.00` | `973600.0` | `1000.0` | **`₹1,000.00`** | Fallback template ([`invoice_processing.py:284`](file:///c:/Users/User/Desktop/sakshi_raju/backend/app/services/invoice_processing.py#L284)) |
| **Tax Total** | `₹175,248.00` | `175248.0` | `180.0` | **`₹180.00`** | Fallback template ([`invoice_processing.py:285`](file:///c:/Users/User/Desktop/sakshi_raju/backend/app/services/invoice_processing.py#L285)) |
| **Total Amount** | `₹1,148,848.00` | `1148848.0` | `1180.0` | **`₹1,180.00`** | Fallback template ([`invoice_processing.py:286`](file:///c:/Users/User/Desktop/sakshi_raju/backend/app/services/invoice_processing.py#L286)) |
| **Line Description** | Storage racks, pallet beams... | 7 detailed line items | `Invoice items (invoice_2page_2.pdf)` | **`Invoice items (invoice_2page_2.pdf)`** | `f"Invoice items ({file_name})"` ([`invoice_processing.py:293`](file:///c:/Users/User/Desktop/sakshi_raju/backend/app/services/invoice_processing.py#L293)) |

---

## 3. Frontend Data Flow & API Trace

### Step 1: Frontend Route Opened
- Route: `/finance/invoices/e30280f7-fe16-4798-a1f0-e5eca175ac68`
- Component: [`frontend/src/app/finance/invoices/[id]/page.tsx`](file:///c:/Users/User/Desktop/sakshi_raju/frontend/src/app/finance/invoices/[id]/page.tsx)

### Step 2: API Call
- Endpoint called: `GET /api/v1/invoices/e30280f7-fe16-4798-a1f0-e5eca175ac68`
- API Function: `getInvoice(invoiceId)` in [`frontend/src/lib/api.ts:457-468`](file:///c:/Users/User/Desktop/sakshi_raju/frontend/src/lib/api.ts#L457-L468)

### Step 3: Exact JSON Returned by Backend API
```json
{
  "id": "e30280f7-fe16-4798-a1f0-e5eca175ac68",
  "file_name": "invoice_2page_2.pdf",
  "status": "COMPLETED",
  "accounting_status": "COMPLETED",
  "confidence_score": 0.5,
  "raw_vlm_output": {
    "confidence_score": 0.5,
    "data": {
      "invoice_number": "INV-E30280F7",
      "invoice_date": "2026-09-02",
      "due_date": "2026-09-02",
      "vendor_name": "invoice 2page 2",
      "vendor_gstin": "36AABCU9603R1ZM",
      "vendor_pan": "AABCU9603R",
      "place_of_supply": "36-Telangana",
      "buyer_name": "Sakshi Finance",
      "buyer_gstin": "36AAACH7409R1ZZ",
      "subtotal": 1000.0,
      "tax_total": 180.0,
      "total_amount": 1180.0,
      "cgst_amount": 90.0,
      "sgst_amount": 90.0,
      "igst_amount": 0.0,
      "line_items": [
        {
          "line_index": 1,
          "description": "Invoice items (invoice_2page_2.pdf)",
          "quantity": 1.0,
          "unit_price": 1000.0,
          "taxable_amount": 1000.0,
          "cgst_rate": 9.0,
          "cgst_amount": 90.0,
          "sgst_rate": 9.0,
          "sgst_amount": 90.0,
          "total": 1180.0
        }
      ]
    }
  },
  "current_vlm_output": { ... identical to raw_vlm_output ... }
}
```

### Step 4: State Initialization in Frontend
- Lines 306–320 of `page.tsx`:
  ```typescript
  const currData = invData.current_vlm_output.data;
  const rawData = invData.raw_vlm_output.data;
  const extracted = { ...rawData, ...currData };
  setFormData(extracted);
  ```
- The frontend renders `formData.invoice_number`, `formData.vendor_name`, `formData.vendor_gstin`, etc., directly into the form inputs.

---

## 4. Exact Point of Corruption in Source Code

The single point where real invoice data is replaced with synthetic values is in:

**File**: [`backend/app/services/invoice_processing.py`](file:///c:/Users/User/Desktop/sakshi_raju/backend/app/services/invoice_processing.py#L258-L322)  
**Function**: `process_invoice_background(invoice_id: uuid.UUID)`

```python
257: extraction_result = None
258: try:
259:     extraction_result = await ai_service.extract_invoice_vlm(file_bytes)
260: except Exception as vlm_err:
261:     logger.warning(
262:         f"Colab Qwen3-VL extraction unavailable for invoice {invoice_id} ({vlm_err}). "
263:         f"Initializing structured draft workspace for manual review & editing."
264:     )
265:     clean_inv_num = f"INV-{str(invoice.id)[:8].upper()}"  # <-- PRODUCES "INV-E30280F7"
266:     today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
267:     base_fname = (invoice.file_name or "Vendor").replace("_", " ").replace("-", " ")
268:     vendor_candidate = base_fname.split(".")[0].strip()   # <-- PRODUCES "invoice 2page 2"
269:     if len(vendor_candidate) > 40:
270:         vendor_candidate = vendor_candidate[:40]
271: 
272:     extraction_result = {
273:         "confidence_score": 0.5,
274:         "data": {
275:             "invoice_number": clean_inv_num,
276:             "invoice_date": today_str,
277:             "due_date": today_str,
278:             "vendor_name": vendor_candidate or "Vendor Invoice",
279:             "vendor_gstin": "36AABCU9603R1ZM",            # <-- HARDCODED
280:             "vendor_pan": "AABCU9603R",
281:             "place_of_supply": "36-Telangana",            # <-- HARDCODED
282:             "buyer_name": "Sakshi Finance",               # <-- HARDCODED
283:             "buyer_gstin": "36AAACH7409R1ZZ",             # <-- HARDCODED
284:             "subtotal": 1000.0,                           # <-- HARDCODED
285:             "tax_total": 180.0,                           # <-- HARDCODED
286:             "total_amount": 1180.0,                       # <-- HARDCODED
287:             "cgst_amount": 90.0,
288:             "sgst_amount": 90.0,
289:             "igst_amount": 0.0,
290:             "line_items": [
291:                 {
292:                     "line_index": 1,
293:                     "description": f"Invoice items ({invoice.file_name})", # <-- "Invoice items (invoice_2page_2.pdf)"
294:                     "quantity": 1.0,
295:                     "unit_price": 1000.0,
296:                     "taxable_amount": 1000.0,
297:                     "cgst_rate": 9.0,
298:                     "cgst_amount": 90.0,
299:                     "sgst_rate": 9.0,
300:                     "sgst_amount": 90.0,
301:                     "total": 1180.0,
302:                 }
303:             ],
304:         },
305:     }
...
317: invoice.raw_vlm_output = extraction_result
318: invoice.current_vlm_output = extraction_result
322: await session.commit()
```

---

## 5. Summary of the 4 Target Values

1. **`"INV-E30280F7"`**:
   - Generated on Line 265: `f"INV-{str(invoice.id)[:8].upper()}"` using the first 8 hex characters of Invoice UUID `e30280f7-fe16-4798-a1f0-e5eca175ac68`.
2. **`"invoice 2page 2"`**:
   - Generated on Line 268: `invoice.file_name.split(".")[0].strip()` from `"invoice_2page_2.pdf"`.
3. **`"36AABCU9603R1ZM"`**:
   - Generated on Line 279: Hardcoded template placeholder in fallback draft.
4. **`"36-Telangana"`**:
   - Generated on Line 281: Hardcoded template placeholder in fallback draft.

---

## 6. Recommended Future Resolution (For Reference Only)

When authorization to apply fixes is given:
1. When `ai_service.extract_invoice_vlm` encounters an exception or timeout:
   - Mark `invoice.status = "FAILED"` and record `invoice.error_message = str(vlm_err)`.
   - Do **not** silently overwrite the extraction with synthetic dummy values (`INV-E30280F7`, `invoice 2page 2`, `36AABCU9603R1ZM`, `1000.0`).
2. If a draft workspace is desired for manual entry, leave fields empty (`null` or `""`) instead of populating fake GSTINs, state codes, and financial totals.
3. Ensure HTTP client timeouts and Colab keep-alive connections do not disconnect prematurely during long-running multi-page inferences.

---

## 7. Final Verdict

### Verdict: **`BACKEND PERSISTENCE BUG`**

- **VLM Extraction**: Extracted correct values on Colab (`INV-2026-1722`, `Satpura Industrial Fabrications`, `36AABCS7845R1Z4`, `973600.0`).
- **Frontend Layer**: 100% accurate display of the backend API payload.
- **Root Cause**: Backend `process_invoice_background` caught a network exception during VLM inference and committed synthetic template fallback data into PostgreSQL.
