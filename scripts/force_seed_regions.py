import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from hexmaster.config import Settings
from hexmaster.db.seed_reference import seed_regions_from_csv

async def main():
    settings = Settings.load()
    engine = create_async_engine(settings.database_url)
    
    print("🔄 Forcing region update from sample_data/Regions.csv...")
    csv_path = Path("sample_data/Regions.csv")
    
    await seed_regions_from_csv(engine, csv_path, force=True)
    
    await engine.dispose()
    print("✨ Region update complete.")

if __name__ == "__main__":
    asyncio.run(main())
