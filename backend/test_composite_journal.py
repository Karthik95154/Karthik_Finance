import sys
import os

sys.path.insert(0, os.path.abspath("backend"))
from app.services.journal_generator import journal_generator
from app.services.tds_engine import get_effective_tds_data, resolve_tds_tax_details

inv_data = {
    "vendor_name": "Sentinel FacilityCare Services Pvt Ltd",
    "vendor_gstin": "36AADSC7712M1ZP",
    "customer_gstin": "36AABCS1429B1Z",
    "subtotal": 289000.0,
    "total_amount": 341020.0,
    "cgst_amount": 26010.0,
    "sgst_amount": 26010.0,
    "line_items": [
        {"line_index": 1, "description": "Security Guard deployment", "taxable_amount": 176000.0, "hsn_sac": "9985"},
        {"line_index": 2, "description": "CCTV Equipment rental", "taxable_amount": 45000.0, "hsn_sac": "9973"},
        {"line_index": 3, "description": "IT security audit and vulnerability assessment", "taxable_amount": 68000.0, "hsn_sac": "9983"},
    ]
}

tds_assessment = {
    "tds_applicable": True,
    "applicable": True,
    "tds_section": "194C, 194J",
    "section": "194C, 194J",
    "tds_provision": "Section 194C, Section 194J",
    "provision": "Section 194C, Section 194J",
    "nature_of_payment": "Composite Services (194C: Rs.3520.0, 194J: Rs.1360.0)",
    "tds_rate": 2.0,
    "rate": 2.0,
    "tds_base_amount": 244000.0,
    "base_amount": 244000.0,
    "proposed_tds_amount": 4880.0,
    "calculated_tds_amount": 4880.0,
    "final_tds_amount": 4880.0,
    "tds_amount": 4880.0,
    "is_approved": False
}

journal = journal_generator.generate_journal(
    invoice_data=inv_data,
    tds_result=tds_assessment
)

print("Status:", journal.get("status"))
print("Total Debit:", journal.get("total_debit"))
print("Total Credit:", journal.get("total_credit"))
print("Difference:", journal.get("difference"))
for line in journal.get("lines", []):
    print(f"  {line['line_type']}: {line['account_name']} | Dr: {line['debit']} | Cr: {line['credit']}")
