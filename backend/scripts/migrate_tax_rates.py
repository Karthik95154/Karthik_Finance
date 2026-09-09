import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv(".env")

async def check_columns():
    url = os.getenv("DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        cols = await conn.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'tax_rates'")
        print("Existing columns in tax_rates:")
        for c in cols:
            print(dict(c))
        
        # Add tax_section and tax_description if not present
        existing = [c["column_name"] for c in cols]
        if "tax_section" not in existing:
            print("Adding tax_section column...")
            await conn.execute("ALTER TABLE tax_rates ADD COLUMN IF NOT EXISTS tax_section VARCHAR(100)")
        if "tax_description" not in existing:
            print("Adding tax_description column...")
            await conn.execute("ALTER TABLE tax_rates ADD COLUMN IF NOT EXISTS tax_description VARCHAR(255)")
        print("Database schema verified/updated successfully.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_columns())
