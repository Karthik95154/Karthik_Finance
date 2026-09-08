import sys
import os
sys.path.append(os.getcwd())
import asyncio
from sqlalchemy import text
from app.db.database import AsyncSessionLocal

async def clean_zoho():
    async with AsyncSessionLocal() as session:
        # Delete disconnected orphan rows when a CONNECTED row exists for the tenant
        res = await session.execute(
            text("""
            DELETE FROM zoho_connections 
            WHERE status = 'DISCONNECTED' 
            AND tenant_id IN (
                SELECT tenant_id FROM zoho_connections WHERE status = 'CONNECTED' AND organization_id IS NOT NULL
            )
            """)
        )
        await session.commit()
        print(f"Cleaned up {res.rowcount} orphan disconnected Zoho connection rows.")

if __name__ == "__main__":
    asyncio.run(clean_zoho())
