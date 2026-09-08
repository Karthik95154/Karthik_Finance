import argparse
import asyncio
import uuid
from sqlalchemy import select, update
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice, EmailConnection, ZohoConnection, User

async def backfill_user_data(target_user_id_str: str):
    try:
        target_user_id = uuid.UUID(target_user_id_str)
    except ValueError:
        print(f"ERROR: '{target_user_id_str}' is not a valid UUID.")
        return

    async with AsyncSessionLocal() as db:
        user_res = await db.execute(select(User).where(User.id == str(target_user_id)))
        user = user_res.scalar_one_or_none()
        if not user:
            print(f"ERROR: User with ID '{target_user_id}' does not exist.")
            return

        print(f"Target User: {user.email} ({user.id})")

        # 1. Audit records with NULL user_id
        inv_null_res = await db.execute(select(Invoice).where(Invoice.user_id.is_(None)))
        null_invoices = inv_null_res.scalars().all()

        email_null_res = await db.execute(select(EmailConnection).where(EmailConnection.user_id.is_(None)))
        null_emails = email_null_res.scalars().all()

        zoho_null_res = await db.execute(select(ZohoConnection).where(ZohoConnection.user_id.is_(None)))
        null_zohos = zoho_null_res.scalars().all()

        print(f"Found NULL user_id records:")
        print(f"  - Invoices: {len(null_invoices)}")
        print(f"  - Email Connections: {len(null_emails)}")
        print(f"  - Zoho Connections: {len(null_zohos)}")

        if not null_invoices and not null_emails and not null_zohos:
            print("No NULL records to update.")
            return

        # 2. Update records
        res_inv = await db.execute(update(Invoice).where(Invoice.user_id.is_(None)).values(user_id=target_user_id))
        res_email = await db.execute(update(EmailConnection).where(EmailConnection.user_id.is_(None)).values(user_id=target_user_id))
        res_zoho = await db.execute(update(ZohoConnection).where(ZohoConnection.user_id.is_(None)).values(user_id=target_user_id))

        await db.commit()

        print("Successfully backfilled NULL records:")
        print(f"  - Invoices updated: {res_inv.rowcount}")
        print(f"  - Email Connections updated: {res_email.rowcount}")
        print(f"  - Zoho Connections updated: {res_zoho.rowcount}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Explicitly backfill NULL user_id records to a specified target user.")
    parser.add_argument("--user-id", required=True, help="Target User UUID string")
    args = parser.parse_args()

    asyncio.run(backfill_user_data(args.user_id))
