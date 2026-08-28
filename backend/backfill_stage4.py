import asyncio
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice
from app.services.invoice_processing import get_effective_invoice_data
from app.services.gst_engine import gst_engine
from app.services.itc_engine import itc_engine


async def backfill():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Invoice))
        invoices = result.scalars().all()
        print(f"Backfilling {len(invoices)} invoices...")
        for inv in invoices:
            if inv.raw_vlm_output or inv.current_vlm_output:
                eff_data = get_effective_invoice_data(inv)
                eff_acc = inv.current_accounting_output or inv.accounting_output
                inv.gst_result = gst_engine.evaluate_gst(eff_data)
                inv.itc_result = itc_engine.evaluate_itc(eff_data, eff_acc)
                print(
                    f"Invoice {inv.file_name} ({inv.id}): "
                    f"GST Status={inv.gst_result.get('validation_status')}, "
                    f"Supply={inv.gst_result.get('supply_type')}, "
                    f"Supplier State={inv.gst_result.get('supplier_state_code')} ({inv.gst_result.get('supplier_state_name')}), "
                    f"POS={inv.gst_result.get('place_of_supply_state_code')} ({inv.gst_result.get('place_of_supply_state_name')}), "
                    f"Extracted CGST={inv.gst_result.get('extracted', {}).get('cgst_amount')}, "
                    f"Extracted SGST={inv.gst_result.get('extracted', {}).get('sgst_amount')}, "
                    f"Extracted IGST={inv.gst_result.get('extracted', {}).get('igst_amount')}, "
                    f"ITC Status={inv.itc_result.get('status')}, Eligible=Rs.{inv.itc_result.get('eligible_amount')}"
                )
        await session.commit()
        print("Backfill complete!")


if __name__ == "__main__":
    asyncio.run(backfill())
