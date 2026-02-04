import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from hexmaster.config import Settings

async def inspect():
    settings = Settings.load()
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        print("\nChecking columns for snapshot_items:")
        stmt = text("""
            SELECT c.column_name, c.data_type, 
                   tc.constraint_type
            FROM information_schema.columns c
            LEFT JOIN information_schema.key_column_usage kcu 
              ON c.table_name = kcu.table_name AND c.column_name = kcu.column_name
            LEFT JOIN information_schema.table_constraints tc 
              ON kcu.constraint_name = tc.constraint_name AND kcu.table_name = tc.table_name
            WHERE c.table_name = 'snapshot_items'
        """)
        r = await conn.execute(stmt)
        for row in r:
            print(f" - {row[0]} ({row[1]}) PK: {row[2]}")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(inspect())
