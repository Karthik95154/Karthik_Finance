"""
Generate comprehensive statistics and detailed tables for OPENAI_MODEL_PERFORMANCE_AUDIT.md
"""
import json

with open('backend/scratch/db_audit_dump.json', 'r', encoding='utf-8') as f:
    db_data = json.load(f)

invoices = db_data['invoices']
hitl_reviews = db_data['hitl_reviews']
audit_logs = db_data['audit_logs']
journal_entries = db_data['journal_entries']
coa_master = db_data['coa_master']
vendors_master = db_data['vendors_master']

# 1. Pipeline trace for all 33 invoices
traces = []
for inv in invoices:
    raw = inv.get('raw_vlm_output') or {}
    curr_vlm = inv.get('current_vlm_output') or {}
    acc = inv.get('accounting_output') or {}
    curr_acc = inv.get('current_accounting_output') or {}
    je = inv.get('journal_entry') or {}
    inv_id = str(inv['id'])

    root = raw.get('prediction') if isinstance(raw.get('prediction'), dict) else raw
    if isinstance(root.get('data'), dict) and any(k in root['data'] for k in ('invoice_details', 'vendor_details')):
        root = root['data']

    # Is 13-key contract?
    is_contract = 'invoice_details' in root and 'vendor_details' in root
    
    inv_d = root.get('invoice_details') or (root.get('data') if isinstance(root.get('data'), dict) else root)
    v_d = root.get('vendor_details') or (root.get('data') if isinstance(root.get('data'), dict) else root)
    f_d = root.get('financial_details') or (root.get('data') if isinstance(root.get('data'), dict) else root)
    tds = root.get('tds_support') or {}
    coa = root.get('coa_support') or {}

    inv_num = inv_d.get('invoice_number') if isinstance(inv_d, dict) else None
    vend_name = v_d.get('vendor_name') if isinstance(v_d, dict) else None
    tot_amt = f_d.get('total_amount') if isinstance(f_d, dict) else None

    # Backend TDS
    b_tds = acc.get('tds') if isinstance(acc, dict) else None
    b_tds_app = b_tds.get('applicable') if isinstance(b_tds, dict) else None
    b_tds_sec = b_tds.get('section') if isinstance(b_tds, dict) else None
    b_tds_rate = b_tds.get('rate') if isinstance(b_tds, dict) else None
    b_tds_amt = b_tds.get('tds_amount') if isinstance(b_tds, dict) else None

    # Journal balanced?
    je_balanced = je.get('balanced') if isinstance(je, dict) else None
    je_lines_count = len(je.get('lines', [])) if isinstance(je, dict) else 0

    inv_reviews = [h for h in hitl_reviews if str(h.get('invoice_id')) == inv_id]
    inv_audits = [a for a in audit_logs if str(a.get('invoice_id')) == inv_id]

    traces.append({
        "id": inv_id,
        "file_name": inv.get('file_name'),
        "created_at": inv.get('created_at'),
        "is_contract": is_contract,
        "status": inv.get('status'),
        "accounting_status": inv.get('accounting_status'),
        "approval_status": inv.get('approval_status'),
        "export_status": inv.get('export_status'),
        "confidence_score": inv.get('confidence_score'),
        "accounting_confidence": inv.get('accounting_confidence'),
        "invoice_number": inv_num,
        "vendor_name": vend_name,
        "total_amount": tot_amt,
        "model_tds": {
            "applicable": tds.get('tds_applicable_candidate'),
            "provision": tds.get('provision_candidate'),
            "legacy": tds.get('legacy_provision_reference'),
            "rate": tds.get('rate_candidate'),
            "base": tds.get('base_candidate'),
            "threshold": tds.get('threshold_status')
        },
        "backend_tds": {
            "applicable": b_tds_app,
            "section": b_tds_sec,
            "rate": b_tds_rate,
            "amount": b_tds_amt
        },
        "je_balanced": je_balanced,
        "je_lines_count": je_lines_count,
        "hitl_count": len(inv_reviews),
        "audit_actions": [a.get('action') for a in inv_audits]
    })

print(f"Generated traces for {len(traces)} invoices.")
with open('backend/scratch/audit_traces.json', 'w', encoding='utf-8') as f:
    json.dump(traces, f, indent=2, default=str)
print("Saved traces to backend/scratch/audit_traces.json")
