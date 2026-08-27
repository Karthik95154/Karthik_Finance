import asyncio
from app.db.database import engine
from sqlalchemy import text

async def check():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        print('Tables:', [r[0] for r in res.fetchall()])
        res2 = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'invoices'"))
        print('Invoices columns:', [r[0] for r in res2.fetchall()])
        res3 = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'journal_entries'"))
        print('Journal Entries columns:', [r[0] for r in res3.fetchall()])
        res4 = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'journal_lines'"))
        print('Journal Lines columns:', [r[0] for r in res4.fetchall()])

if __name__ == '__main__':
    asyncio.run(check())
