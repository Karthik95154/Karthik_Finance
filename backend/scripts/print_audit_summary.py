import json

with open('backend/scratch/comprehensive_audit_results.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

print("=== CONTRACT SECTIONS (Total 33) ===")
for sec, stats in d['contract_sections_stats'].items():
    p = stats['present']
    ne = stats['non_empty']
    print(f"{sec:22}: present={p:2d}/33 ({p/33*100:5.1f}%), non_empty={ne:2d}/33")

print("\n=== EXTRA TOP-LEVEL KEYS ===")
for k, v in d['extra_top_level_keys'].items():
    print(f"  {k}: {v}")

print("\n=== KEY EXTRACTION FIELDS (non-null counts) ===")
for k, s in d['fields_stats'].items():
    nn = s['non_null']
    pct = s['non_null_pct']
    print(f"{k:30}: non_null={nn:2d}/33 ({pct:5.1f}%) | top: {list(s['top_values'].keys())[:2]}")

print("\n=== LINE ITEMS STATS ===")
print("Total line items across 33 invoices:", d['line_items_stats']['total_line_items'])
for k, v in d['line_items_stats']['field_population'].items():
    print(f"  {k:18}: {v['count']:3d} ({v['pct']}%)")
