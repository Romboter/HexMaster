from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

async def sync_schema(conn: AsyncConnection) -> None:
    """
    Ensures that the database schema matches the expected models by adding 
    any missing columns. This handles environments where the database 
    already exists but lacks newer additions.
    """
    print("📋 Checking database schema consistency...")

    # Define migrations as (table_name, column_definition)
    # Using 'IF NOT EXISTS' for columns requires Postgres 9.6+
    migrations = [
        # Regions Table
        ("regions", "ALTER TABLE regions ADD COLUMN IF NOT EXISTS q FLOAT"),
        ("regions", "ALTER TABLE regions ADD COLUMN IF NOT EXISTS raw_r FLOAT"),
        ("regions", "ALTER TABLE regions ADD COLUMN IF NOT EXISTS r FLOAT"),
        ("regions", "ALTER TABLE regions ADD COLUMN IF NOT EXISTS distance_to_origin FLOAT"),
        ("regions", "ALTER TABLE regions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"),

        # Towns Table
        ("towns", "ALTER TABLE towns ADD COLUMN IF NOT EXISTS region_id INTEGER REFERENCES regions(id) ON DELETE CASCADE"),
        ("towns", "ALTER TABLE towns ADD COLUMN IF NOT EXISTS x FLOAT"),
        ("towns", "ALTER TABLE towns ADD COLUMN IF NOT EXISTS y FLOAT"),
        ("towns", "ALTER TABLE towns ADD COLUMN IF NOT EXISTS marker_type VARCHAR"),
        ("towns", "ALTER TABLE towns ADD COLUMN IF NOT EXISTS global_q FLOAT"),
        ("towns", "ALTER TABLE towns ADD COLUMN IF NOT EXISTS global_r FLOAT"),
        ("towns", "ALTER TABLE towns ADD COLUMN IF NOT EXISTS town_type VARCHAR"),
        ("towns", "ALTER TABLE towns ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"),
        
        # Stockpile Snapshots Table
        ("stockpile_snapshots", "ALTER TABLE stockpile_snapshots ADD COLUMN IF NOT EXISTS guild_id BIGINT"),
        ("stockpile_snapshots", "ALTER TABLE stockpile_snapshots ADD COLUMN IF NOT EXISTS war_number INTEGER"),
        
        # Snapshot Items Table (Ensuring primary key is correct is harder, but we can ensure columns)
        ("snapshot_items", "ALTER TABLE snapshot_items ADD COLUMN IF NOT EXISTS code_name VARCHAR"),
        ("snapshot_items", "ALTER TABLE snapshot_items ADD COLUMN IF NOT EXISTS item_name VARCHAR"),
        ("snapshot_items", "ALTER TABLE snapshot_items ADD COLUMN IF NOT EXISTS quantity INTEGER DEFAULT 0"),
        ("snapshot_items", "ALTER TABLE snapshot_items ADD COLUMN IF NOT EXISTS is_crated BOOLEAN DEFAULT FALSE"),
        ("snapshot_items", "ALTER TABLE snapshot_items ADD COLUMN IF NOT EXISTS per_crate INTEGER DEFAULT 0"),
        ("snapshot_items", "ALTER TABLE snapshot_items ADD COLUMN IF NOT EXISTS total INTEGER DEFAULT 0"),
        ("snapshot_items", "ALTER TABLE snapshot_items ADD COLUMN IF NOT EXISTS description TEXT"),
    ]

    for table, stmt in migrations:
        try:
            await conn.execute(text(stmt))
        except Exception as e:
            # Some errors (like foreign key conflicts if types mismatch) might trigger here
            # But ADD COLUMN IF NOT EXISTS is generally safe
            print(f"⚠️ Could not apply migration for {table}: {e}")

    # Special case: Drop old columns if they exist and are problematic
    # towns.region (string) might conflict with the new towns.region_id (FK)
    # but we'll keep it for now as a non-destructive migration. 
    
    print("✅ Schema sync complete.")
