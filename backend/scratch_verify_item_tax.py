import sys
import os
sys.path.append(os.getcwd())
import asyncio
import json
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice

async def verify_line_items():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Invoice).where(Invoice.id == "1d508a39-081e-4258-9b2e-a62ed9060a9f"))
        inv = res.scalar_one_or_none()
        if inv and inv.current_vlm_output:
            items = inv.current_vlm_output.get("data", {}).get("line_items", [])
            print("Extracted & Calculated Line Items:")
            for item in items:
                print(f"Line {item.get('line_index')}: {item.get('description')}")
                print(f"  Qty: {item.get('quantity')}, UnitPrice: {item.get('unit_price')}, LineAmount: {item.get('line_amount')}, Taxable: {item.get('taxable_amount')}")
                print(f"  IGST Rate: {item.get('igst_rate')}%, IGST Amt: RS.{item.get('igst_amount')}, CGST Rate: {item.get('cgst_rate')}, SGST Rate: {item.get('sgst_rate')}")
                print(f"  Master GST Rate: {item.get('gst_rate')}%, Total: RS.{item.get('total')}")
                print("-" * 60)

if __name__ == "__main__":
    asyncio.run(verify_line_items())
