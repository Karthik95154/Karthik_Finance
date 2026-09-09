import psycopg2, os, json, sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath('backend'))
from dotenv import load_dotenv

load_dotenv('backend/.env')
url = os.getenv('DATABASE_URL').replace('postgresql+psycopg2://', 'postgresql://')
conn = psycopg2.connect(url)
cur = conn.cursor()

cur.execute("""
    SELECT id, file_name, raw_vlm_output, current_vlm_output, accounting_output
    FROM invoices 
    WHERE id = 'b5d21262-a40f-492d-84d9-5c017e0b1601';
""")
row = cur.fetchone()
raw = row[2]

from app.services.model_response_adapter import ModelResponseAdapter
from app.services.tds_engine import tds_engine, get_effective_tds_data

norm = ModelResponseAdapter.normalize_model_response(raw)
norm_tds = norm['normalized_accounting']['tds_assessment']
print("=== 1. ADAPTER NORMALIZATION ON THIS RAW OUTPUT ===")
print(json.dumps(norm_tds, indent=2))

print("\n=== 2. DOWNSTREAM TDS ENGINE SIMULATION ===")
invoice_payload = norm['normalized_data']
effective_tds = get_effective_tds_data({"tds_assessment": norm_tds})
print("effective_tds:", json.dumps(effective_tds, indent=2))

tds_applicable = bool(effective_tds.get("applicable"))
tds_base_amt = tds_engine.determine_tds_base_amount(invoice_payload, effective_tds)
tds_rate = effective_tds.get("rate")
tds_section = effective_tds.get("section")
tds_provision = effective_tds.get("provision")
tds_nature = effective_tds.get("nature_of_payment")
vendor_pan = invoice_payload.get("vendor_pan")

final_tds = tds_engine.calculate_tds(
    applicable=tds_applicable,
    section=tds_section,
    provision=tds_provision,
    nature_of_payment=tds_nature,
    base_amount=tds_base_amt,
    rate=float(tds_rate) if tds_rate is not None else None,
    vendor_pan=vendor_pan
)
print("\nFinal TDS calculated with CURRENT adapter code:")
print(json.dumps(final_tds, indent=2))

print("\n=== 3. OLD STORED ACCOUNTING OUTPUT IN DB (when invoice was uploaded) ===")
print(json.dumps(row[4].get('tds'), indent=2))

cur.close()
conn.close()
