import asyncio
import math
from sqlalchemy.ext.asyncio import create_async_engine
from hexmaster.config import Settings
from hexmaster.db.repositories.stockpile_repository import StockpileRepository
from hexmaster.db.init import init_db
from hexmaster.db.seed_reference import seed_regions_from_csv, seed_towns_from_csv
from pathlib import Path

async def test_global_dist():
    settings = Settings.load()
    engine = create_async_engine(settings.database_url)
    repo = StockpileRepository(engine)
    
    # Ensure DB is up to date
    await init_db(engine)
    data_dir = Path("sample_data")
    await seed_regions_from_csv(engine, data_dir / "Regions.csv")
    await seed_towns_from_csv(engine, data_dir / "Towns.csv")

    # 1. Compare Deadlands (Abandoned Ward) to something else
    # Abandoned Ward is in Deadlands (0,0)
    aw = await repo.get_town_data("AbandonedWard")
    
    # Basinhome is in Basin Sionnach (0, 3)
    bh = await repo.get_town_data("Basinhome")
    
    print(f"AbandonedWard Data: {aw}")
    print(f"Basinhome Data: {bh}")

    if aw and bh:
        x1, y1 = aw["q"] + aw["x"], aw["r"] + aw["y"]
        x2, y2 = bh["q"] + bh["x"], bh["r"] + bh["y"]
        dist = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        print(f"Calculated Distance from AW to BH: {dist:.2f}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_global_dist())
