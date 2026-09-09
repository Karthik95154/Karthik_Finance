"""
Analyze the formats of the 33 invoices in the DB:
Which ones have the 13 fixed-contract sections vs {"data": ...} or older format?
"""
import json
from collections import Counter

with open('backend/scratch/db_audit_dump.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

invoices = data['invoices']

format_types = Counter()
format_details = []

for idx, inv in enumerate(invoices):
    raw = inv.get('raw_vlm_output')
    fn = inv.get('file_name')
    created = inv.get('created_at')
    status = inv.get('status')
    
    if not isinstance(raw, dict):
        format_types[f'non_dict_{type(raw).__name__}'] += 1
        continue
    
    keys = list(raw.keys())
    if 'invoice_details' in raw and 'vendor_details' in raw:
        fmt = "LOCKED_CONTRACT_13_KEYS (New)"
    elif 'data' in raw:
        data_keys = list(raw['data'].keys()) if isinstance(raw['data'], dict) else []
        if 'invoice_details' in data_keys:
            fmt = "LOCKED_CONTRACT_WRAPPED_IN_DATA"
        else:
            fmt = f"DATA_WRAPPED_LEGACY ({len(data_keys)} keys: {data_keys[:4]})"
    elif 'prediction' in raw:
        fmt = "PREDICTION_WRAPPED"
    elif 'gl_support' in raw:
        fmt = "LOCKED_CONTRACT_PARTIAL"
    else:
        fmt = f"LEGACY_FORMAT ({keys[:4]})"
    
    format_types[fmt] += 1
    format_details.append({
        "idx": idx,
        "id": str(inv['id']),
        "file_name": fn,
        "created_at": created,
        "status": status,
        "format": fmt,
        "top_keys": keys[:6]
    })

print("=== INVOICE RAW OUTPUT FORMAT BREAKDOWN (Total 33) ===")
for fmt, cnt in format_types.items():
    print(f"  {fmt:40}: {cnt:2d} invoices ({cnt/33*100:.1f}%)")

print("\nChronological breakdown (first 10 and last 10):")
print("First 5 (newest):")
for item in format_details[:5]:
    print(f"  [{item['created_at'][:19]}] {item['file_name']:25} -> {item['format']}")

print("\nLast 5 (oldest):")
for item in format_details[-5:]:
    print(f"  [{item['created_at'][:19]}] {item['file_name']:25} -> {item['format']}")
