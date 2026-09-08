import sys
import os
sys.path.append(os.getcwd())
import asyncio
import json
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice

async def check_invoices():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Invoice).order_by(Invoice.created_at.desc()).limit(10))
        invoices = result.scalars().all()
        print(f"Found {len(invoices)} recent invoices:\n")
        for inv in invoices:
            print("=" * 80)
            print(f"ID: {inv.id}")
            print(f"File Name: {inv.file_name}")
            print(f"Status: {inv.status}")
            print(f"Error Message: {inv.error_message}")
            print(f"Raw VLM Output Present: {bool(inv.raw_vlm_output)}")
            print(f"Current VLM Output Present: {bool(inv.current_vlm_output)}")
            print(f"Accounting Output Present: {bool(inv.accounting_output)}")
            if inv.current_vlm_output:
                print("Current VLM Sample:", json.dumps(inv.current_vlm_output, indent=2)[:300])
            if inv.accounting_output:
                print("Accounting Output Sample:", json.dumps(inv.accounting_output, indent=2)[:300])
            print("=" * 80)

if __name__ == "__main__":
    asyncio.run(check_invoices())
