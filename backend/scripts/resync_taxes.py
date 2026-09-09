import asyncio
from app.db.database import AsyncSessionLocal
from app.services.master_data_service import master_data_service

async def main():
    async with AsyncSessionLocal() as session:
        print("Starting live tax sync with Zoho...")
        taxes = await master_data_service.sync_taxes("default-tenant-001", session, organization_id="60081887558")
        print(f"Sync complete! Fetched {len(taxes)} taxes.")

if __name__ == "__main__":
    asyncio.run(main())
