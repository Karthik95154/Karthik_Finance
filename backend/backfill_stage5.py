import asyncio
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice
from app.services.invoice_processing import get_effective_invoice_data
from app.services.gst_engine import gst_engine
from app.services.itc_engine import itc_engine
from app.services.financial_validator import financial_validator


async def backfill():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Invoice))
        invoices = result.scalars().all()
        print(f"Backfilling Stage 5 Financial Validation on {len(invoices)} invoices...")
        for inv in invoices:
            if inv.raw_vlm_output or inv.current_vlm_output:
                eff_data = get_effective_invoice_data(inv)
                eff_acc = inv.current_accounting_output or inv.accounting_output
                inv.gst_result = gst_engine.evaluate_gst(eff_data)
                inv.itc_result = itc_engine.evaluate_itc(eff_data, eff_acc)
                inv.financial_validation_result = financial_validator.validate_invoice(eff_data, inv.gst_result)
                print(
                    f"Invoice {inv.file_name} ({inv.id}): "
                    f"Financial Status={inv.financial_validation_result.get('overall_status')}, "
                    f"Extracted Total=Rs.{inv.financial_validation_result.get('source', {}).get('total_amount')}, "
                    f"Calculated Total=Rs.{inv.financial_validation_result.get('calculated', {}).get('grand_total')}, "
                    f"Differences={inv.financial_validation_result.get('differences')}"
                )
        await session.commit()
        print("Stage 5 Backfill complete!")


if __name__ == "__main__":
    asyncio.run(backfill())
