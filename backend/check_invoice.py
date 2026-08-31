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
            data = inv.current_vlm_output.get('data', {}) if inv.current_vlm_output else {}
            total = data.get('total_amount', 0)
            items = data.get('line_items', [])
            if total == 90000 or any('Rent' in item.get('description', '') for item in items):
                print('=== INVOICE FOUND ===')
                print(f'ID: {inv.id}')
                
                itc_res = inv.itc_result if inv.itc_result else {}
                itc_stat = itc_res.get('status')
                print(f'ITC Status: {itc_stat}')
                print(f'ITC Result: {json.dumps(inv.itc_result, indent=2)}')
                print(f'GST Result: {json.dumps(inv.gst_result, indent=2)}')
                print(f'VLM Data: {json.dumps(data, indent=2)}')
                print('=====================\n')

asyncio.run(main())
