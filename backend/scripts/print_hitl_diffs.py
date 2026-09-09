import json

with open('backend/scratch/db_audit_dump.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

for hr in d['hitl_reviews']:
    inp = hr['input_snapshot'].get('data') if isinstance(hr['input_snapshot'], dict) else {}
    corr = hr['corrected_output'].get('data') if isinstance(hr['corrected_output'], dict) else {}
    print("=== HITL INVOICE:", hr['invoice_id'], "===")
    diffs = {}
    if isinstance(inp, dict) and isinstance(corr, dict):
        for k in set(inp.keys()).union(corr.keys()):
            if inp.get(k) != corr.get(k):
                diffs[k] = {'before': inp.get(k), 'after': corr.get(k)}
    print("Differences count:", len(diffs))
    for k, v in diffs.items():
        print(f"  Field '{k}': before={v['before']} -> after={v['after']}")
