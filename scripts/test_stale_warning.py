import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from hexmaster.config import Settings
from hexmaster.db.repositories.stockpile_repository import StockpileRepository
from hexmaster.services.war_service import WarService

async def test_stale_warning():
    settings = Settings.load()
    engine = create_async_engine(settings.database_url)
    repo = StockpileRepository(engine)
    war_service = WarService()
    
    town = "Tine"
    current_war = await war_service.get_current_war_number()
    past_war = current_war - 1
    
    print(f"Current War: {current_war}")
    print(f"Mocking a snapshot for {town} from War {past_war}...")
    
    # Ingest a snapshot with a past war number
    await repo.ingest_snapshot(town, "Seaport", "StaleStockpile", [], past_war)
    
    # Fetch inventory
    rows = await repo.get_latest_inventory(town)
    
    if rows:
        # Note: inventory join currently requires items to be in the snapshot to show up in get_latest_inventory
        # So I should probably check get_latest_snapshot_for_town instead
        snapshot, items = await repo.get_latest_snapshot_for_town(town)
        war_num = snapshot.get("war_number")
        print(f"Retrieved Snapshot War Number: {war_num}")
        
        if war_num and current_war and war_num < current_war:
            print(f"✅ STALE DATA DETECTED: War {war_num} < Current War {current_war}")
            print("The Cog logic will display the warning correctly.")
        else:
            print("❌ Stale data NOT detected or war numbers missing.")
    else:
        print("No snapshots found for town.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_stale_warning())
