"""
Detailed statistical and pipeline tracer script.
Processes backend/scratch/db_audit_dump.json and extracts:
- Part 2: Invoice counts, status breakdown, model outputs presence
- Part 3: Model -> Adapter -> Backend -> HITL trace for all 33 invoices
- Part 4: TDS model performance (presence, rates, sections, backend overrides, HITL changes)
- Part 5: COA model performance (presence, accounts, backend validation, confidence, HITL changes)
- Part 6: Fixed JSON contract extraction field audit across all 33 records
- Part 7: Audit log inspection (user corrections, overrides)
"""
import json
import os
from collections import defaultdict, Counter

def analyze():
    with open('backend/scratch/db_audit_dump.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    invoices = data['invoices']
    hitl_reviews = data['hitl_reviews']
    audit_logs = data['audit_logs']
    journal_entries = data['journal_entries']
    coa_master = {c['id']: c for c in data['coa_master']}
    coa_by_code = {c['account_code']: c for c in data['coa_master']}

    print(f"Total Invoices with VLM output: {len(invoices)}")
    print(f"Total HITL reviews: {len(hitl_reviews)}")
    print(f"Total Audit logs: {len(audit_logs)}")

    # 1. Pipeline Status Breakdown
    status_counts = Counter(inv['status'] for inv in invoices)
    accounting_status_counts = Counter(inv['accounting_status'] for inv in invoices)
    approval_status_counts = Counter(inv['approval_status'] for inv in invoices)
    export_status_counts = Counter(inv['export_status'] for inv in invoices)

    print("\n--- Pipeline Statuses ---")
    print("Status:", dict(status_counts))
    print("Accounting Status:", dict(accounting_status_counts))
    print("Approval Status:", dict(approval_status_counts))
    print("Export Status:", dict(export_status_counts))

    # 2. Trace and Field Audit
    fixed_keys = [
        "invoice_number", "invoice_date", "due_date", "currency",
        "vendor_name", "vendor_gstin", "vendor_pan", "vendor_address",
        "customer_name", "customer_gstin", "customer_pan", "customer_address",
        "place_of_supply", "hsn_code",
        "subtotal", "tax_amount", "cgst_amount", "sgst_amount", "igst_amount",
        "discount_amount", "round_off_amount", "total_amount",
        "is_rcm", "line_items", "bank_details", "suggested_tds", "suggested_coa"
    ]

    field_presence = {k: 0 for k in fixed_keys}
    field_non_null = {k: 0 for k in fixed_keys}
    field_non_empty = {k: 0 for k in fixed_keys}

    # TDS details
    tds_in_raw = 0
    tds_sections = Counter()
    tds_rates = Counter()
    tds_backend_matches = 0
    tds_backend_differ = 0
    tds_details = []

    # COA details
    coa_in_raw = 0
    coa_codes = Counter()
    coa_backend_matches = 0
    coa_backend_differ = 0
    coa_details = []

    invoice_traces = []

    for inv in invoices:
        raw = inv.get('raw_vlm_output') or {}
        curr_vlm = inv.get('current_vlm_output') or {}
        acc = inv.get('accounting_output') or {}
        curr_acc = inv.get('current_accounting_output') or {}
        inv_id = str(inv['id'])

        # Field presence check in raw_vlm_output
        for k in fixed_keys:
            if k in raw:
                field_presence[k] += 1
                val = raw[k]
                if val is not None:
                    field_non_null[k] += 1
                    if isinstance(val, (str, list, dict)) and len(val) > 0:
                        field_non_empty[k] += 1
                    elif isinstance(val, (int, float)) and val != 0:
                        field_non_empty[k] += 1
                    elif val is True:
                        field_non_empty[k] += 1

        # Check TDS
        raw_tds = raw.get('suggested_tds')
        # Check if TDS exists in backend accounting_output / current_accounting_output / current_vlm_output
        backend_tds = None
        if acc and isinstance(acc, dict):
            backend_tds = acc.get('tds') or acc.get('tds_result')
        if not backend_tds and curr_acc and isinstance(curr_acc, dict):
            backend_tds = curr_acc.get('tds') or curr_acc.get('tds_result')
        if not backend_tds:
            # Check journal entry lines for TDS_PAYABLE
            je = inv.get('journal_entry')
            if je and isinstance(je, dict):
                lines = je.get('lines', [])
                tds_lines = [l for l in lines if l.get('line_type') == 'TDS_PAYABLE']
                if tds_lines:
                    backend_tds = {"lines": tds_lines}

        # Model TDS details
        if raw_tds:
            tds_in_raw += 1
            sec = raw_tds.get('section') if isinstance(raw_tds, dict) else None
            rate = raw_tds.get('rate') if isinstance(raw_tds, dict) else None
            tds_sections[str(sec)] += 1
            tds_rates[str(rate)] += 1

        # Check COA
        raw_coa = raw.get('suggested_coa')
        backend_coa = None
        if acc and isinstance(acc, dict):
            backend_coa = acc.get('line_items') or acc.get('debit_accounts')
        if raw_coa:
            coa_in_raw += 1
            code = raw_coa.get('account_code') if isinstance(raw_coa, dict) else None
            coa_codes[str(code)] += 1

        # Trace record
        invoice_traces.append({
            "id": inv_id,
            "file_name": inv.get('file_name'),
            "status": inv.get('status'),
            "accounting_status": inv.get('accounting_status'),
            "approval_status": inv.get('approval_status'),
            "export_status": inv.get('export_status'),
            "raw_invoice_number": raw.get('invoice_number'),
            "raw_vendor_name": raw.get('vendor_name'),
            "raw_total_amount": raw.get('total_amount'),
            "raw_tds": raw_tds,
            "backend_tds": backend_tds,
            "raw_coa": raw_coa,
            "has_hitl": any(str(h.get('invoice_id')) == inv_id for h in hitl_reviews),
            "audit_logs_count": sum(1 for a in audit_logs if str(a.get('invoice_id')) == inv_id),
            "confidence_score": inv.get('confidence_score'),
            "accounting_confidence": inv.get('accounting_confidence')
        })

    # Summary of HITL and Audit log actions
    audit_actions = Counter(a.get('action') for a in audit_logs)
    audit_fields_edited = Counter(a.get('field_name') for a in audit_logs if a.get('action') == 'EDIT_FIELD')

    results = {
        "total_analyzed": len(invoices),
        "status_counts": dict(status_counts),
        "accounting_status_counts": dict(accounting_status_counts),
        "approval_status_counts": dict(approval_status_counts),
        "export_status_counts": dict(export_status_counts),
        "fixed_keys_presence": {
            k: {
                "key_present_count": field_presence[k],
                "non_null_count": field_non_null[k],
                "non_empty_count": field_non_empty[k],
                "presence_pct": round(field_presence[k] / len(invoices) * 100, 1),
                "non_null_pct": round(field_non_null[k] / len(invoices) * 100, 1)
            } for k in fixed_keys
        },
        "tds_stats": {
            "total_with_raw_tds": tds_in_raw,
            "sections_distribution": dict(tds_sections),
            "rates_distribution": dict(tds_rates),
        },
        "coa_stats": {
            "total_with_raw_coa": coa_in_raw,
            "codes_distribution": dict(coa_codes)
        },
        "audit_logs_summary": {
            "total_logs": len(audit_logs),
            "actions": dict(audit_actions),
            "fields_edited": dict(audit_fields_edited)
        },
        "hitl_reviews_summary": {
            "total_reviews": len(hitl_reviews),
            "reviews": [
                {
                    "id": str(h['id']),
                    "invoice_id": str(h['invoice_id']),
                    "stage": h.get('stage'),
                    "status": h.get('status'),
                    "has_changes": bool(h.get('changes')),
                    "changes": h.get('changes')
                } for h in hitl_reviews
            ]
        },
        "traces": invoice_traces
    }

    with open('backend/scratch/analysis_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    
    print("\n--- Summary ---")
    print(f"Total VLM Invoices: {len(invoices)}")
    print(f"TDS in raw VLM: {tds_in_raw}/{len(invoices)}")
    print("TDS sections:", dict(tds_sections))
    print(f"COA in raw VLM: {coa_in_raw}/{len(invoices)}")
    print("COA codes:", dict(coa_codes))
    print("Audit Log Actions:", dict(audit_actions))
    print("Audit Log Edited Fields:", dict(audit_fields_edited))
    print("HITL reviews:", len(hitl_reviews))
    for hr in hitl_reviews:
        print("  Review:", hr.get('id'), hr.get('invoice_id'), hr.get('stage'), hr.get('status'), "Changes:", hr.get('changes'))

if __name__ == '__main__':
    analyze()
