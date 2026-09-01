# VLM IGST Amount Normalization Fix Report

## 1. Exact Root Cause
In `01_Qwen3VL_Invoice_Extraction (3).ipynb` (Cell 14), during post-processing and normalization of raw line items extracted by Qwen3-VL:
`_parse_line_items_freeform()` invokes `normalize_line_item(item)`.

Inside `normalize_line_item()`:
Every dictionary key `k` is mapped to its canonical field name using `canon = _ALIAS_LOOKUP.get(_norm_key(k))`.
For a raw output key `"igst_amount"`, `_norm_key("igst_amount")` produces `"igst amount"`.

However, in `LINE_ITEM_KEY_ALIASES`:
```python
# OLD DEFINITION:
"igst_amount": {"igst rs", "igst", "igst amt"}
```
`"igst amount"` was missing from the set of aliases. Consequently, `_ALIAS_LOOKUP.get("igst amount")` returned `None`, treating `"igst_amount"` as an unrecognized stray field and quarantining it into `stray` instead of mapping it to the canonical `igst_amount` field in `LineItem`. Because `LineItem` was initialized without `igst_amount`, it defaulted to `null` (`None`).

The same omission affected `cgst_amount` and `sgst_amount` when formatted as `"cgst amount"` or `"sgst amount"`.

---

## 2. Exact Function Causing Loss
- **File**: `colab_notebooks/01_Qwen3VL_Invoice_Extraction (3).ipynb`
- **Cell**: Code Cell 14 (`## 7. Normalization and repair helpers`)
- **Structure**: `LINE_ITEM_KEY_ALIASES` lookup dictionary consumed by `normalize_line_item()`.

---

## 3. Minimal Fix
Updated `LINE_ITEM_KEY_ALIASES` in Cell 14 to include the canonical amount phrases (`"igst amount"`, `"cgst amount"`, `"sgst amount"`):

```python
LINE_ITEM_KEY_ALIASES = {
    "description": {"description", "product name", "product name description", "item",
                     "item description", "particulars", "product"},
    "hsn_code": {"hsn code", "hsn", "hsn sac", "sac"},
    "quantity": {"qty", "qty nos", "quantity", "nos", "pcs"},
    "unit_price": {"unit price", "rate", "price", "unit rate"},
    "discount": {"disc amt", "discount amt", "discount amount", "disc value", "discount"},
    "taxable_amount": {"taxable amt rs", "taxable amount", "taxable amt", "taxable value", "assessable value"},
    "cgst_rate": {"cgst rate", "cgst %", "cgst pct", "cgst percent"},
    "cgst_amount": {"cgst amount", "cgst amt", "cgst rs", "cgst"},
    "sgst_rate": {"sgst rate", "sgst %", "sgst pct", "sgst percent"},
    "sgst_amount": {"sgst amount", "sgst amt", "sgst rs", "sgst"},
    "igst_rate": {"igst rate", "igst %", "igst pct", "igst percent"},
    "igst_amount": {"igst amount", "igst amt", "igst rs", "igst"},
    "total": {"total rs", "total", "amount total", "line total", "amount", "item total"},
}
```

---

## 4. Raw Before
```json
[
  {
    "description": "Goods Transportation Service - Full Truck Load (FTL)",
    "taxable_amount": 120000,
    "cgst_rate": null,
    "cgst_amount": null,
    "sgst_rate": null,
    "sgst_amount": null,
    "igst_rate": 12,
    "igst_amount": 14400,
    "total": 134400
  },
  {
    "description": "Loading & Unloading Charges",
    "taxable_amount": 5000,
    "cgst_rate": null,
    "cgst_amount": null,
    "sgst_rate": null,
    "sgst_amount": null,
    "igst_rate": 12,
    "igst_amount": 600,
    "total": 5600
  }
]
```

---

## 5. Normalized Before (Buggy)
```json
[
  {
    "description": "Goods Transportation Service - Full Truck Load (FTL)",
    "taxable_amount": 120000.0,
    "cgst_rate": null,
    "cgst_amount": null,
    "sgst_rate": null,
    "sgst_amount": null,
    "igst_rate": 12.0,
    "igst_amount": null,
    "total": 134400.0
  },
  {
    "description": "Loading & Unloading Charges",
    "taxable_amount": 5000.0,
    "cgst_rate": null,
    "cgst_amount": null,
    "sgst_rate": null,
    "sgst_amount": null,
    "igst_rate": 12.0,
    "igst_amount": null,
    "total": 5600.0
  }
]
```

---

## 6. Normalized After (Fixed)
```json
[
  {
    "description": "Goods Transportation Service - Full Truck Load (FTL)",
    "hsn_code": null,
    "quantity": 1.0,
    "unit_price": 120000.0,
    "discount": null,
    "taxable_amount": 120000.0,
    "cgst_rate": null,
    "cgst_amount": null,
    "sgst_rate": null,
    "sgst_amount": null,
    "igst_rate": 12.0,
    "igst_amount": 14400.0,
    "total": 134400.0
  },
  {
    "description": "Loading & Unloading Charges",
    "hsn_code": null,
    "quantity": 1.0,
    "unit_price": 5000.0,
    "discount": null,
    "taxable_amount": 5000.0,
    "cgst_rate": null,
    "cgst_amount": null,
    "sgst_rate": null,
    "sgst_amount": null,
    "igst_rate": 12.0,
    "igst_amount": 600.0,
    "total": 5600.0
  }
]
```

---

## 7. Confirmation of Zero Unrelated Changes
- VLM prompts and schemas were untouched.
- Tax amounts are extracted and preserved directly as parsed without any recalculation or derivation (`taxable_amount × rate`).
- Backend, frontend, GST/ITC/TDS engines, journals, and database models were untouched.

---

## 8. Regression Test Results
- **Coromandel Invoice Test (IGST)**:
  - Line 1: `igst_rate: 12.0`, `igst_amount: 14400.0`, `cgst_amount: None`, `sgst_amount: None` &rarr; **MATCH / PRESERVED**
  - Line 2: `igst_rate: 12.0`, `igst_amount: 600.0`, `cgst_amount: None`, `sgst_amount: None` &rarr; **MATCH / PRESERVED**
- **Intrastate Invoice Test (CGST + SGST)**:
  - Line: `cgst_rate: 9.0`, `cgst_amount: 4500.0`, `sgst_rate: 9.0`, `sgst_amount: 4500.0`, `igst_amount: None` &rarr; **MATCH / PRESERVED**

---

### Final Verdict

```text
RAW IGST AMOUNT: PASS
NORMALIZED IGST AMOUNT: PASS
CGST/SGST REMAIN NULL: PASS
NO RECALCULATION/FABRICATION: PASS
```
