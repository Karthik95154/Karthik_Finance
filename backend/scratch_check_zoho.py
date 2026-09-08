import sys
import os
sys.path.append(os.getcwd())
import asyncio
import json
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import User, Tenant, ZohoConnection

async def inspect_zoho():
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User))).scalars().all()
        print("USERS IN DB:")
        for u in users:
            print(f"ID: {u.id}, Email: {u.email}, Role: {u.role}, TenantID: {u.tenant_id}")
        
        print("\nZOHO CONNECTIONS IN DB:")
        conns = (await session.execute(select(ZohoConnection))).scalars().all()
        for c in conns:
            print(f"ID: {c.id}, TenantID: {c.tenant_id}, UserID: {c.user_id}, Status: {c.status}, OrgID: {c.organization_id}, OrgName: {c.organization_name}")

if __name__ == "__main__":
    asyncio.run(inspect_zoho())
