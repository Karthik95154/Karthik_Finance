import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asyncio
from app.db.database import AsyncSessionLocal
from sqlalchemy import select
from app.db.models import ChartOfAccount

async def check():
    async with AsyncSessionLocal() as s:
        res = await s.execute(select(ChartOfAccount))
        accs = res.scalars().all()
        print(f"Total COAs in DB: {len(accs)}")
        for a in accs:
            print(f"ID: {a.zoho_account_id} | Name: '{a.account_name}' | Type: '{a.account_type}' | Code: '{a.account_code}'")

if __name__ == "__main__":
    asyncio.run(check())
