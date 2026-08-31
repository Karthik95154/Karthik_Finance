import asyncio
import json
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice
from app.services.itc_engine import itc_engine
from app.services.invoice_processing import get_effective_invoice_data
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Invoice))
        invoices = res.scalars().all()
        print(f"Total database invoices: {len(invoices)}\n")
        
        sample_count = 0
        for inv in invoices:
            eff_data = get_effective_invoice_data(inv)
            if not eff_data or not (eff_data.get('total_amount') or eff_data.get('tax_total') or eff_data.get('line_items')):
                continue
            eff_acc = inv.current_accounting_output or inv.accounting_output
            itc_res = itc_engine.evaluate_itc(eff_data, eff_acc)
            inv_no = eff_data.get('invoice_number') or eff_data.get('invoice_no') or 'N/A'
            lines = itc_res.get('line_item_breakdown') or []
            rules = [l.get('rule_reference') for l in lines] if lines else [itc_res.get('rule_reference')]
            evidence = lines[0].get('evidence_used') if lines else itc_res.get('evidence')
            
            print("================================================================================")
            print(f"Invoice:    {inv.file_name} ({inv_no})")
            print(f"Input Tax:  Rs.{itc_res['total_tax_amount']:,.2f}")
            print(f"Eligible:   Rs.{itc_res['eligible_itc']:,.2f}")
            print(f"Blocked:    Rs.{itc_res['blocked_itc']:,.2f}")
            print(f"Reversal:   Rs.{itc_res['reversal_itc']:,.2f}")
            print(f"Review:     Rs.{itc_res['review_amount']:,.2f}")
            print(f"Net ITC:    Rs.{itc_res['net_itc_available']:,.2f}")
            print(f"Status:     {itc_res['status']}")
            print(f"Reason:     {itc_res['reason']}")
            print(f"Rules:      {rules}")
            print(f"Evidence:   {evidence}")
            print()
            sample_count += 1
            if sample_count >= 10:
                break

if __name__ == '__main__':
    asyncio.run(main())
