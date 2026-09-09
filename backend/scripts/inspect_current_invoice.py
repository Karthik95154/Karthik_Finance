import psycopg2, os, json
from dotenv import load_dotenv

load_dotenv('backend/.env')
url = os.getenv('DATABASE_URL').replace('postgresql+psycopg2://', 'postgresql://')
conn = psycopg2.connect(url)
cur = conn.cursor()

cur.execute("""
    SELECT 
        id, file_name, raw_vlm_output, current_vlm_output, accounting_output, current_accounting_output
    FROM invoices 
    WHERE id = 'b5d21262-a40f-492d-84d9-5c017e0b1601';
""")
row = cur.fetchone()

print("File:", row[1])
print("\n--- 1. RAW VLM OUTPUT (Model Response) ---")
raw = row[2]
print("TDS Support:", json.dumps(raw.get('tds_support'), indent=2))
print("Line items:", json.dumps(raw.get('line_items'), indent=2))

print("\n--- 2. CURRENT VLM OUTPUT ---")
curr_vlm = row[3]
print("curr_vlm keys:", list(curr_vlm.keys()) if isinstance(curr_vlm, dict) else type(curr_vlm))

print("\n--- 3. ACCOUNTING OUTPUT ---")
acc = row[4]
print(json.dumps(acc, indent=2))

cur.close()
conn.close()
