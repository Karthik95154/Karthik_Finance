import json

with open('backend/scratch/db_audit_dump.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

invoices = data['invoices']

contract_invoices = []
for inv in invoices:
    raw = inv.get('raw_vlm_output') or {}
    root = raw.get('prediction') if isinstance(raw.get('prediction'), dict) else raw
    if 'invoice_details' in root and 'vendor_details' in root:
        contract_invoices.append(inv)

print(f"Found {len(contract_invoices)} invoices using the 13-key Fixed JSON contract:")
for inv in contract_invoices:
    fn = inv.get('file_name')
    raw = inv.get('raw_vlm_output') or {}
    root = raw.get('prediction') if isinstance(raw.get('prediction'), dict) else raw
    inv_d = root.get('invoice_details') or {}
    v_d = root.get('vendor_details') or {}
    f_d = root.get('financial_details') or {}
    tds = root.get('tds_support') or {}
    coa = root.get('coa_support') or {}
    itc = root.get('itc_support') or {}
    print(f"\n--- {fn} ({inv.get('id')}) ---")
    print(f"  Invoice: {inv_d.get('invoice_number')} | Date: {inv_d.get('invoice_date')} | Total: {f_d.get('total_amount')}")
    print(f"  Vendor: {v_d.get('vendor_name')} | GSTIN: {v_d.get('vendor_gstin')} | PAN: {v_d.get('vendor_pan')}")
    print(f"  TDS: applicable={tds.get('tds_applicable_candidate')}, nature={tds.get('payment_nature')}, prov={tds.get('provision_candidate')}, leg_sec={tds.get('legacy_provision_reference')}, rate={tds.get('rate_candidate')}, base={tds.get('base_candidate')}, threshold={tds.get('threshold_status')}")
    print(f"  ITC: candidate={itc.get('candidate')}, blocked_risk={itc.get('blocked_credit_risk')}, eligible_amt={itc.get('eligible_amount_candidate')}")
    l_matches = coa.get('line_matches') or []
    print(f"  COA line matches ({len(l_matches)}):")
    for lm in l_matches[:3]:
        print(f"    Line {lm.get('line_index')}: matched_id={lm.get('matched_account_id')}, name={lm.get('matched_account_name')}, conf={lm.get('confidence')}, type={lm.get('match_type')}")
