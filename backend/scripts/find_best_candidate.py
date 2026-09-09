import json

with open('backend/scratch/db_audit_dump.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for inv in data['invoices']:
    raw = inv.get('raw_vlm_output') or {}
    root = raw.get('prediction') if isinstance(raw.get('prediction'), dict) else raw
    if 'invoice_details' in root and 'vendor_details' in root:
        fn = inv.get('file_name')
        v_d = root.get('vendor_details') or {}
        bd = v_d.get('bank_details') or {}
        created = inv.get('created_at')
        id_ = inv.get('id')
        print(f"ID: {id_} | Created: {created[:19]} | File: {fn}")
        print(f"   Vendor: {v_d.get('vendor_name')} | Phone: {v_d.get('vendor_phone')} | Email: {v_d.get('vendor_email')}")
        print(f"   Bank: {bd}")
