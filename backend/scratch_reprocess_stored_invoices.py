import sys
import os
sys.path.append(os.getcwd())
import asyncio
import json
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice
from app.services.kimi_adapter import KimiK3ResponseAdapter

async def reprocess_invoices():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Invoice))
        invoices = result.scalars().all()
        updated_count = 0
        for inv in invoices:
            if inv.raw_vlm_output:
                normalized = KimiK3ResponseAdapter.normalize_kimi_response(
                    kimi_response=inv.raw_vlm_output,
                    user_zoho_coa=[],
                )
                inv.current_vlm_output = {"data": normalized["normalized_data"]}
                inv.accounting_output = normalized["normalized_accounting"]
                inv.current_accounting_output = normalized["normalized_accounting"]
                if inv.status == "FINAL_HITL_REVIEW":
                    inv.status = "COMPLETED"
                updated_count += 1
                print(f"Reprocessed Invoice {inv.id} ({inv.file_name}): Vendor={normalized['normalized_data'].get('vendor_name')}, Total={normalized['normalized_data'].get('total_amount')}, Lines={len(normalized['normalized_data'].get('line_items', []))}")
        await session.commit()
        print(f"\nSuccessfully reprocessed {updated_count} invoices with full data.")

if __name__ == "__main__":
    asyncio.run(reprocess_invoices())
