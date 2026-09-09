import json

with open('backend/scratch/db_audit_dump.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for i, inv in enumerate(data['invoices'][:5]):
    print(f"\n==================== INVOICE {i+1} ====================")
    print("ID:", inv.get("id"))
    print("File:", inv.get("file_name"))
    print("Created at:", inv.get("created_at"))
    print("Status:", inv.get("status"))
    print("Accounting Status:", inv.get("accounting_status"))
    print("Approval Status:", inv.get("approval_status"))
    print("Confidence:", inv.get("confidence_score"))
    print("Accounting Confidence:", inv.get("accounting_confidence"))
    
    raw = inv.get("raw_vlm_output")
    curr = inv.get("current_vlm_output")
    acc = inv.get("accounting_output")
    curr_acc = inv.get("current_accounting_output")
    gst = inv.get("gst_result")
    je = inv.get("journal_entry")
    
    print("raw_vlm_output type:", type(raw).__name__)
    if isinstance(raw, dict):
        print("raw_vlm_output keys:", list(raw.keys()))
        print("raw sample invoice_number:", raw.get("invoice_number"))
        print("raw sample vendor_name:", raw.get("vendor_name"))
        print("raw sample total_amount:", raw.get("total_amount"))
        print("raw line_items count:", len(raw.get("line_items", [])) if isinstance(raw.get("line_items"), list) else type(raw.get("line_items")))
    
    print("accounting_output type:", type(acc).__name__)
    if isinstance(acc, dict):
        print("accounting_output keys:", list(acc.keys()))
        print("acc tds:", acc.get("tds") or acc.get("tds_result"))
        print("acc journal entry balanced?:", acc.get("journal_entry", {}).get("balanced") if isinstance(acc.get("journal_entry"), dict) else "N/A")
    
    print("journal_entry type:", type(je).__name__)
    if isinstance(je, dict):
        print("je lines count:", len(je.get("lines", [])))
        for line in je.get("lines", [])[:3]:
            print("  line:", line.get("account_name"), line.get("line_type"), line.get("debit"), line.get("credit"))
