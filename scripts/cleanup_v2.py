import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from hexmaster.config import Settings

async def clean_snapshots():
    settings = Settings.load()
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        print("Normalizing existing stockpile_snapshots town names...")
        # 1. Lowercase all towns
        await conn.execute(text("UPDATE stockpile_snapshots SET town = LOWER(TRIM(town))"))
        
        # 2. Re-run migration for guild_id just in case
        print("Ensuring guild_id exists...")
        check_stmt = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'stockpile_snapshots' AND column_name = 'guild_id'
        """)
        res = await conn.execute(check_stmt)
        if not res.fetchone():
            await conn.execute(text("ALTER TABLE stockpile_snapshots ADD COLUMN guild_id BIGINT"))
            await conn.execute(text("CREATE INDEX ix_stockpile_snapshots_guild_id ON stockpile_snapshots (guild_id)"))
            print("Added guild_id.")
        else:
            print("guild_id exists.")
            
    await engine.dispose()
    print("Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(clean_snapshots())
