import asyncio
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice

async def check():
    async with AsyncSessionLocal() as session:
        for fname in ['sample_test_invoice.png', 'stage1_002_goods_layout2.png', 'Armstrong_INV-2025-26-0778_6490_23-05-2025 (1) (1) (1).pdf']:
            res = await session.execute(select(Invoice).where(Invoice.file_name == fname).limit(1))
            inv = res.scalars().first()
            if inv and inv.journal_entry:
                je = inv.journal_entry
                print(f"=== {fname} ===")
                print(f"Status: {je.get('status')}")
                print(f"Debit: Rs.{je.get('total_debit')}, Credit: Rs.{je.get('total_credit')}, Diff: Rs.{je.get('difference')}")
                print("Lines:")
                for l in je.get('lines', []):
                    print(f"  - {l.get('account_name')} ({l.get('account_id')}) [{l.get('line_type')}] Dr: Rs.{l.get('debit')}, Cr: Rs.{l.get('credit')}, Prov: {l.get('provenance')}")
                print()

if __name__ == '__main__':
    asyncio.run(check())
