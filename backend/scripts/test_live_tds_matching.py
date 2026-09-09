import asyncio
from app.db.database import AsyncSessionLocal
from app.services.master_data_service import master_data_service

async def test_live_matching():
    async with AsyncSessionLocal() as session:
        tenant_id = "default-tenant-001"
        org_id = "60081887558"

        from app.db.models import TaxRate
        from sqlalchemy import select
        tax_res = await session.execute(select(TaxRate).where(TaxRate.organization_id == org_id, TaxRate.tax_type == "TDS"))
        tax_map = {t.zoho_tax_id: t for t in tax_res.scalars().all()}

        test_cases = [
            ("Professional Services", 10.0, "Section 393(1) SI6(iii)(D)(b) - Fees", "Professional fees & Legal Consulting", "4076465000000345002"),
            ("Technical Services (FTS)", 2.0, "Section 393(1) SI6(iii)D(a)", "Fees for Technical Services (FTS) & Cloud Infrastructure", "4076465000000033027"),
            ("Approved 10% Rate on FTS", 10.0, "Section 393(1) [Table Sl. No. 6(iii)] - Professional and Technical Services", "Fees for Technical Services (FTS) & Cloud Infrastructure", "4076465000000345002"),
            ("Contractor (Others)", 2.0, "Section 393(1) [Table Sl. No. 6(i)] - Payments to Contractors", "Work Contracts & Sub-contractor Services", "4076465000000033025"),
            ("Commission / Brokerage", 2.0, "Section 393(1) [Table Sl. No. 1(ii)] - Commission or Brokerage", "Commission & Brokerage Payments", "4076465000000033026"),
            ("Purchase of Goods", 0.1, "Section 393(1) [Table Sl. No. 8(ii)] - Purchase of Goods", "Purchase of Goods", "4076465000000369003"),
        ]

        for label, rate, prov, nature, expected_id in test_cases:
            z_id = await master_data_service.get_zoho_tds_tax(
                tenant_id=tenant_id,
                section="Section 393",
                provision=prov,
                nature_of_payment=nature,
                rate=rate,
                db=session,
                organization_id=org_id,
            )
            t = tax_map.get(z_id)
            tax_name = t.tax_name if t else "Not Found"
            slug = t.tax_section if t else "None"
            status_str = "PASS" if z_id == expected_id else f"FAIL (Expected {expected_id})"
            print(f"[{status_str}] Category: {label:25} | Rate: {rate:4.1f}% | Resolved Name: {tax_name:32} | Tax ID: {z_id} | Slug: {slug}")

if __name__ == "__main__":
    asyncio.run(test_live_matching())
