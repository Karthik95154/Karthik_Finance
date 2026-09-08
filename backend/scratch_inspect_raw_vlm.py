import sys
import os
sys.path.append(os.getcwd())
import asyncio
import json
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice

async def inspect_raw_vlm():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Invoice).where(Invoice.id == "1d508a39-081e-4258-9b2e-a62ed9060a9f"))
        inv = result.scalar_one_or_none()
        if inv:
            print("RAW VLM OUTPUT:")
            print(json.dumps(inv.raw_vlm_output, indent=2))
            print("\nCURRENT VLM OUTPUT:")
            print(json.dumps(inv.current_vlm_output, indent=2))

if __name__ == "__main__":
    asyncio.run(inspect_raw_vlm())
