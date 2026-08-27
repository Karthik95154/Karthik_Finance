# Final Invoice Workspace & Processing Workflow Status

## 1. Summary of Changes
The single-page Invoice Workspace has been refined to serve as the unified Finance workspace:
- **Top Area (Two-Column Workspace)**:
  - **Left Panel (48% width)**: `INVOICE PREVIEW` with uploaded file name and "Open in new tab" link. Has its **own independent vertical scroll** displaying original PDFs / images from private Supabase Storage.
  - **Right Panel (52% width)**: `AI EXTRACTION REVIEW` with dummy action buttons (`[ Reject ]`, `[ Approve ]`, `[ Export ]`). Has its **own independent vertical scroll** containing the complete long-form workspace:
    1. `INVOICE INFORMATION` (Editable Invoice Number, Invoice Date, Due Date, PO Number, Place of Supply, Currency)
    2. `VENDOR / BILL FROM` (Editable Name, GSTIN, PAN, CIN, Phone, Email, Address)
    3. `CUSTOMER / BILL TO` (Editable Name, GSTIN, PAN, Address)
    4. `LINE ITEMS` (Horizontally scrollable editable table with Description, HSN/SAC, Qty, Unit Price, Discount, Taxable, CGST Rate/Amt, SGST Rate/Amt, IGST Rate/Amt, Total, `+ Add Item Row`, and delete item buttons)
    5. `PAYMENT & BANK DETAILS` (Editable Payment Terms, Account Holder, Bank Name, Account Number, IFSC, Branch, UPI ID)
    6. `TAX DETAILS` (Tax amounts extracted by VLM)
    7. `FINANCIAL TOTALS` (Subtotal, Discount Total, Tax Total, Shipping, Other Charges, Round Off, Grand Total in a clean 2-column grid)
    8. `ADDITIONAL EXTRACTED INFORMATION` (Preserves unmapped fields from `additional_fields` with zero data loss)
    9. `SAVE CHANGES` (Working button that saves customer edits into PostgreSQL `current_vlm_output` while leaving `raw_vlm_output` untouched)
- **Bottom Area (Processing Workflow)**:
  - Three equal columns:
    - **INCOMING INVOICES**: Real database invoices with status `PENDING` / `PROCESSING_VLM`.
    - **EXTRACTED INVOICES**: Real database invoices with status `COMPLETED`. Clicking navigates directly to `/finance/invoices/[id]`.
    - **EXPORTED TO ZOHO**: Count = 0, clean empty state: "No invoices exported yet." (Zero fake data).

---

## 2. Persistence & Dual-State Verification
- **`raw_vlm_output`**: Stores original untouched extraction from Qwen3-VL.
- **`current_vlm_output`**: Stores user-edited working invoice state.
- **`PUT /api/v1/invoices/{id}`**: Successfully persists customer edits without overwriting `raw_vlm_output`.
- **Page Refresh**: Loads `current_vlm_output` with all user modifications intact.

---

## 3. Automated Test & Build Status
- **Backend Tests**: `pytest backend/tests -v` $\rightarrow$ **10 / 10 tests passed**.
- **Frontend Build**: `npm run build` $\rightarrow$ **Compiled successfully with zero errors**.
- **Alembic Migration**: `003_add_current_vlm_output` applied to live PostgreSQL.
