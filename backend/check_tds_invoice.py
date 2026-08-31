import json
import asyncio
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Invoice))
        invoices = result.scalars().all()
        for inv in invoices:
            acc_out = inv.current_accounting_output or inv.accounting_output or {}
            tds = acc_out.get('tds') or acc_out.get('tds_assessment') or {}
            if tds.get('applicable') is True or tds.get('tds_applicable') is True or (tds.get('calculated_tds_amount') or 0) > 0 or (tds.get('proposed_tds_amount') or 0) > 0:
                print(f"=== INVOICE ID: {inv.id} ===")
                print(f"Accounting Output TDS: {json.dumps(tds, indent=2)}")
                print(f"File Name: {inv.file_name}")
                return
        print('NO TDS INVOICE FOUND')

asyncio.run(main())
