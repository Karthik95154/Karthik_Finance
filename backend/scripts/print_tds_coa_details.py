import json

with open('backend/scratch/audit_traces.json', 'r', encoding='utf-8') as f:
    traces = json.load(f)

print("=== 11 FIXED CONTRACT INVOICES: MODEL TDS vs BACKEND TDS ===")
for t in traces:
    if t['is_contract']:
        m_tds = t['model_tds']
        b_tds = t['backend_tds']
        fn = t['file_name'][:28]
        m_app = str(m_tds.get('applicable'))
        m_sec = str(m_tds.get('legacy') or m_tds.get('provision') or 'None')[:15]
        b_app = str(b_tds.get('applicable'))
        b_sec = str(b_tds.get('section'))
        b_rate = str(b_tds.get('rate'))
        b_amt = str(b_tds.get('amount'))
        print(f"{fn:28} | M_app: {m_app:5} | M_sec: {m_sec:15} | B_app: {b_app:5} | B_sec: {b_sec:12} | B_rate: {b_rate:5} | B_amt: {b_amt:8}")

print("\n=== COA PER-INVOICE MAPPING IN 11 CONTRACT INVOICES ===")
with open('backend/scratch/db_audit_dump.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
coa_master = {c['id']: c['account_name'] for c in d['coa_master']}

for inv in d['invoices']:
    raw = inv.get('raw_vlm_output') or {}
    root = raw.get('prediction') if isinstance(raw.get('prediction'), dict) else raw
    if 'invoice_details' in root and 'vendor_details' in root:
        fn = inv.get('file_name')
        coa = root.get('coa_support') or {}
        l_matches = coa.get('line_matches') or []
        print(f"\n{fn}:")
        for lm in l_matches:
            aid = lm.get('matched_account_id')
            aname = lm.get('matched_account_name')
            in_master = aid in coa_master
            master_name = coa_master.get(aid, "NOT_IN_MASTER")
            print(f"  Line {lm.get('line_index')}: proposed_id={aid} ({aname}) -> in_master={in_master} (actual: {master_name}), conf={lm.get('confidence')}, type={lm.get('match_type')}")
