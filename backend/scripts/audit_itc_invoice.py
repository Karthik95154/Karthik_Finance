import asyncio, json, uuid
from app.db.database import AsyncSessionLocal
from app.services.invoice_processing import get_effective_invoice_data
from app.services.gst_engine import gst_engine
from app.services.itc_engine import itc_engine
from app.db.models import Invoice, JournalEntry
from sqlalchemy import select

async def audit():
    async with AsyncSessionLocal() as db:
        inv_id = uuid.UUID('19f69e82-e16b-401c-b466-f2161f8ec215')
        inv = (await db.execute(select(Invoice).where(Invoice.id == inv_id))).scalar_one()
        vlm_data = get_effective_invoice_data(inv)
        
        # 1. GST Engine
        gst_res = gst_engine.evaluate_gst(vlm_data)
        
        # 2. ITC Engine
        cur_acct = inv.current_accounting_output or inv.accounting_output or {}
        itc_res = itc_engine.evaluate_itc(
            invoice_data=vlm_data,
            accounting_output=cur_acct,
        )
        
        # 3. Journal Entry
        j_query = select(JournalEntry).where(JournalEntry.invoice_id == inv_id)
        j_res = (await db.execute(j_query)).scalar_one_or_none()
        
        print('=== GST ENGINE ===')
        print(json.dumps(gst_res, indent=2))
        
        print('=== ITC ENGINE ===')
        print('Status:', itc_res.get('status'))
        print('Eligible ITC:', itc_res.get('eligible_itc'))
        print('Blocked ITC:', itc_res.get('blocked_itc'))
        print('Reversal ITC:', itc_res.get('reversal_itc'))
        print('Review ITC:', itc_res.get('review_amount'))
        print('Rule Reference:', itc_res.get('rule_reference'))
        print('Reason:', itc_res.get('reason'))
        print('Line breakdown:')
        for lb in itc_res.get('line_item_breakdown', []):
            l_idx = lb.get("line_index")
            desc = lb.get("description", "")[:40]
            st = lb.get("itc_status")
            tax = lb.get("tax_amount")
            elig = lb.get("eligible_amount")
            rule = lb.get("rule_reference")
            print(f'   Line {l_idx}: {desc} | Status: {st} | Tax: {tax} | Elig: {elig} | Rule: {rule}')

        if j_res:
            print('=== JOURNAL ENTRY ===')
            print(f'Total Debit: {j_res.total_debit}, Total Credit: {j_res.total_credit}, Balanced: {j_res.is_balanced}')
            lines = j_res.line_items or []
            for l in lines:
                acode = l.get("account_code")
                aname = l.get("account_name")
                deb = l.get("debit")
                crd = l.get("credit")
                ref = l.get("rule_reference")
                print(f'   {acode} ({aname}): Debit={deb}, Credit={crd}, Ref={ref}')

if __name__ == '__main__':
    asyncio.run(audit())
