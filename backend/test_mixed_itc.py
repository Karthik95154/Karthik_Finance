import sys
import os

sys.path.insert(0, os.path.abspath("backend"))
from app.services.itc_engine import itc_engine
from app.services.journal_generator import journal_generator

inv_mixed = {
    "vendor_name": "Sri Ram Traders & Services",
    "vendor_gstin": "36AAOFS4521R1ZQ",
    "customer_gstin": "36AACCM9087L1Z2",
    "invoice_number": "SR/2026-27/0876",
    "invoice_date": "2026-09-03",
    "subtotal": 92100.0,
    "cgst_amount": 8289.0,
    "sgst_amount": 8289.0,
    "total_amount": 108678.0,
    "line_items": [
        {
            "line_index": 1,
            "description": "Supply of industrial cable & fittings (material)",
            "hsn_code": "8544",
            "quantity": 120,
            "unit_price": 380.0,
            "taxable_amount": 45600.0,
            "cgst_amount": 4104.0,
            "sgst_amount": 4104.0,
        },
        {
            "line_index": 2,
            "description": "Installation, wiring & commissioning charges",
            "hsn_code": "9954",
            "quantity": 1,
            "unit_price": 28500.0,
            "taxable_amount": 28500.0,
            "cgst_amount": 2565.0,
            "sgst_amount": 2565.0,
        },
        {
            "line_index": 3,
            "description": "Annual maintenance contract (Apr 26-Mar 27), billed quarterly",
            "hsn_code": "9987",
            "quantity": 1,
            "unit_price": 18000.0,
            "taxable_amount": 18000.0,
            "cgst_amount": 1620.0,
            "sgst_amount": 1620.0,
        }
    ]
}

# Provide accounting classification like user had in UI (Line 1: Materials, Line 2: Labor/COGS, Line 3: Repairs & Maintenance)
accounting_ctx = {
    "accounting": [
        {"line_index": 1, "account_name": "Cost of Goods Sold / Materials", "account_id": "407641"},
        {"line_index": 2, "account_name": "Labor (cost_of_goods_sold)", "account_id": "407641"},
        {"line_index": 3, "account_name": "Repairs and Maintenance", "account_id": "407641"}
    ]
}

res = itc_engine.evaluate_itc(invoice_data=inv_mixed, accounting_output=accounting_ctx)
print("ITC Status:", res.get("status"))
print("Eligible Tax:", res.get("eligible_amount"))
print("Blocked Tax:", res.get("ineligible_amount"))
print("Review Tax:", res.get("review_amount"))
print("Reversal Tax:", res.get("reversal_itc"))
for lb in res.get("line_item_breakdown", []):
    print(f"  Line {lb['line_index']}: {lb['description']} -> {lb['itc_status']} | Tax: {lb['tax_amount']} | Reason: {lb['reason']}")

journal = journal_generator.generate_journal(
    invoice_data=inv_mixed,
    accounting_classification=accounting_ctx,
    itc_result=res
)
print("\nJournal Lines:")
for l in journal.get("lines", []):
    print(f"  {l['line_type']}: {l['account_name']} | Dr: {l['debit']} | Cr: {l['credit']}")
