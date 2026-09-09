import asyncio, os, json, asyncpg, uuid
from dotenv import load_dotenv

load_dotenv(".env")

async def inspect():
    db_url = os.getenv("DATABASE_URL", "").replace("postgresql+psycopg2://", "postgresql://").replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)
    inv_id = uuid.UUID("19f69e82-e16b-401c-b466-f2161f8ec215")
    q = "SELECT id, file_name, export_status, error_message, raw_vlm_output, current_accounting_output FROM invoices WHERE id = $1"
    row = await conn.fetchrow(q, inv_id)
    if row:
        print("=== ID ===", row["id"])
        print("=== FILE ===", row["file_name"])
        print("=== EXPORT STATUS ===", row["export_status"])
        print("=== ERROR ===", row["error_message"])
        
        raw = row["raw_vlm_output"]
        if isinstance(raw, str):
            raw = json.loads(raw)
        print("=== VENDOR ===", json.dumps(raw.get("vendor_details"), indent=2))
        print("=== CUSTOMER ===", json.dumps(raw.get("customer_details"), indent=2))
        print("=== INVOICE DETAILS ===", json.dumps(raw.get("invoice_details"), indent=2))
        print("=== GST SUPPORT ===", json.dumps(raw.get("gst_support"), indent=2))
        print("=== ITC SUPPORT ===", json.dumps(raw.get("itc_support"), indent=2))
        print("=== FINANCIALS ===", json.dumps(raw.get("financial_details"), indent=2))
        print("=== LINE ITEMS ===", json.dumps(raw.get("line_items"), indent=2))

        cur = row["current_accounting_output"]
        if isinstance(cur, str):
            cur = json.loads(cur)
        print("=== CURRENT ACCOUNTING OUTPUT ===", json.dumps(cur, indent=2))

    await conn.close()

if __name__ == "__main__":
    asyncio.run(inspect())
