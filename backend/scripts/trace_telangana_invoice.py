import asyncio
from uuid import UUID
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice, JournalEntry, JournalLineModel
from app.services.itc_engine import get_effective_itc_data, ITCStatus, ZOHO_ITC_MAPPING
from app.services.invoice_processing import get_effective_invoice_data
from sqlalchemy import select

async def run_trace():
    inv_id = UUID('19f69e82-e16b-401c-b466-f2161f8ec215')
    async with AsyncSessionLocal() as session:
        inv = (await session.execute(select(Invoice).where(Invoice.id == inv_id))).scalar_one_or_none()
        if not inv:
            print('INVOICE NOT FOUND')
            return
        
        data = get_effective_invoice_data(inv)
        acct = inv.current_accounting_output or inv.accounting_output or {}
        
        print('=== INVOICE DATA ===')
        print('Invoice Number:', data.get('invoice_number'))
        print('Supplier GSTIN:', data.get('supplier_gstin') or data.get('vendor_gstin'))
        print('Customer GSTIN:', data.get('customer_gstin') or data.get('buyer_gstin'))
        print('Supplier State Code:', data.get('supplier_state_code'))
        print('POS State Code:', data.get('place_of_supply_state_code') or data.get('place_of_supply'))
        print('Taxable Total:', data.get('subtotal'))
        print('CGST:', data.get('cgst_amount'))
        print('SGST:', data.get('sgst_amount'))
        print('IGST:', data.get('igst_amount'))
        print('Tax Total:', data.get('tax_total'))
        print('Total Amount:', data.get('total_amount'))
        
        # 1. Authoritative ITC SSOT Resolution
        itc_ssot = get_effective_itc_data(
            invoice_or_data=inv,
            recipient_state_code='36',
        )
        print('\n=== AUTHORITATIVE ITC SSOT ===')
        print('Status:', itc_ssot.get('status'))
        print('Eligible ITC:', itc_ssot.get('eligible_itc'))
        print('Blocked ITC:', itc_ssot.get('blocked_itc'))
        print('Review Amount:', itc_ssot.get('review_amount'))
        print('GSTR-2B Status:', itc_ssot.get('gstr2b_status'))
        print('Out of State Local Tax:', itc_ssot.get('is_out_of_state_local_tax'))
        print('Rule Reference:', itc_ssot.get('rule_reference'))
        for idx, l in enumerate(itc_ssot.get('line_item_breakdown', []), 1):
            desc = l.get("description")
            tax = l.get("tax_amount")
            st = l.get("itc_status")
            zoho_itc = l.get("zoho_itc_eligibility")
            rule = l.get("rule_reference")
            print(f'Line {idx}: {desc} | Tax: Rs {tax} | Status: {st} | Zoho ITC: {zoho_itc} | Rule: {rule}')

        # 2. Journal General Ledger Check
        je = (await session.execute(select(JournalEntry).where(JournalEntry.invoice_id == inv_id))).scalar_one_or_none()
        if je:
            jlines = (await session.execute(select(JournalLineModel).where(JournalLineModel.journal_entry_id == je.id))).scalars().all()
            input_tax_debits = sum(float(jl.debit or 0.0) for jl in jlines if jl.line_type == 'INPUT_TAX')
            print('\n=== JOURNAL GENERAL LEDGER ENTRIES ===')
            print('Journal Status:', je.status)
            print('Total Debits:', je.total_debit)
            print('Total Credits:', je.total_credit)
            print('Input Tax GL Debits:', round(input_tax_debits, 2))
            print('Reconciled with SSOT Eligible ITC?', abs(input_tax_debits - float(itc_ssot.get('eligible_itc', 0.0))) <= 0.01)

if __name__ == '__main__':
    asyncio.run(run_trace())
