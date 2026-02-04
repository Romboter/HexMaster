import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from hexmaster.config import Settings

async def migrate():
    settings = Settings.load()
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        print("Checking for id column in snapshot_items...")
        check_stmt = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'snapshot_items' AND column_name = 'id'
        """)
        res = await conn.execute(check_stmt)
        if not res.fetchone():
            print("Adding id column to snapshot_items...")
            # We use SERIAL for primary key
            await conn.execute(text("ALTER TABLE snapshot_items ADD COLUMN id SERIAL PRIMARY KEY"))
            print("Successfully added id column.")
        else:
            print("id column already exists.")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
