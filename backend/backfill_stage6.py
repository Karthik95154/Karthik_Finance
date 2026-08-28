import asyncio
import logging
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice
from app.services.invoice_processing import get_effective_invoice_data
from app.services.journal_generator import journal_generator, sync_relational_journal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill_stage6")


async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Invoice))
        invoices = result.scalars().all()
        logger.info(f"Found {len(invoices)} invoices to evaluate Stage 6 Journal Generation.")

        for inv in invoices:
            effective_data = get_effective_invoice_data(inv)
            effective_acc = inv.current_accounting_output or inv.accounting_output
            tds_data = effective_acc.get("tds") if effective_acc else None

            journal_res = journal_generator.generate_journal(
                invoice_data=effective_data,
                accounting_classification=effective_acc,
                gst_result=inv.gst_result,
                itc_result=inv.itc_result,
                tds_result=tds_data,
                financial_validation_result=inv.financial_validation_result,
            )

            inv.journal_entry = journal_res
            await sync_relational_journal(session, inv.id, journal_res)

            logger.info(
                f"Invoice {inv.id} ({inv.file_name}): status={journal_res.get('status')}, "
                f"debit=Rs.{journal_res.get('total_debit')}, credit=Rs.{journal_res.get('total_credit')}, "
                f"diff=Rs.{journal_res.get('difference')}, lines={len(journal_res.get('lines', []))}"
            )

        await session.commit()
        logger.info("Successfully backfilled and persisted Stage 6 Journal entries for all invoices.")


if __name__ == "__main__":
    asyncio.run(main())
