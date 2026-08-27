import asyncio
from app.db.database import engine
from sqlalchemy import text

async def patch():
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE journal_lines ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL"))
        await conn.execute(text("ALTER TABLE journal_lines ADD COLUMN IF NOT EXISTS debit FLOAT DEFAULT 0.0 NOT NULL"))
        await conn.execute(text("ALTER TABLE journal_lines ADD COLUMN IF NOT EXISTS credit FLOAT DEFAULT 0.0 NOT NULL"))
        await conn.execute(text("ALTER TABLE journal_lines ADD COLUMN IF NOT EXISTS source_line_index INTEGER"))
        await conn.execute(text("ALTER TABLE journal_lines ADD COLUMN IF NOT EXISTS provenance VARCHAR(50) DEFAULT 'DETERMINISTIC' NOT NULL"))
        await conn.execute(text("ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS difference FLOAT DEFAULT 0.0 NOT NULL"))
        await conn.execute(text("ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS balanced BOOLEAN DEFAULT true NOT NULL"))
        await conn.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS journal_entry JSONB"))
        await conn.execute(text("ALTER TABLE journal_lines ALTER COLUMN line_type TYPE VARCHAR(50)"))
        await conn.execute(text("ALTER TABLE journal_lines ALTER COLUMN account_id TYPE VARCHAR(100)"))
        await conn.execute(text("ALTER TABLE journal_lines ALTER COLUMN line_number DROP NOT NULL"))
        await conn.execute(text("ALTER TABLE journal_lines ALTER COLUMN amount DROP NOT NULL"))
        print('Patched journal_lines and journal_entries columns successfully.')

if __name__ == '__main__':
    asyncio.run(patch())
