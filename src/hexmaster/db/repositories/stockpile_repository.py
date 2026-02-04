from sqlalchemy import select, insert, desc, text
from sqlalchemy.ext.asyncio import AsyncEngine
from datetime import datetime, timezone
from hexmaster.db.models import StockpileSnapshot, SnapshotItem, CatalogItem, Town, Priority, Region

# TODO: Add docstrings
class StockpileRepository:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def get_all_towns(self) -> list[str]:
        """Fetches all valid town names from the reference table."""
        async with self.engine.connect() as conn:
            stmt = select(Town.name).order_by(Town.name)
            result = await conn.execute(stmt)
            return [row[0] for row in result.all()]

    async def get_towns_with_snapshots(self) -> list[str]:
        """Fetches unique town names that already have snapshots in the DB."""
        async with self.engine.connect() as conn:
            stmt = (
                select(StockpileSnapshot.town)
                .distinct()
                .order_by(StockpileSnapshot.town)
            )
            result = await conn.execute(stmt)
            return [row[0] for row in result.all() if row[0]]

    async def get_towns_with_hub_snapshots(self) -> list[str]:
        """Fetches towns that have at least one Seaport or Storage Warehouse snapshot."""
        async with self.engine.connect() as conn:
            stmt = (
                select(StockpileSnapshot.town)
                .distinct()
                .where(
                    (StockpileSnapshot.struct_type.ilike("%Storage Warehouse%")) |
                    (StockpileSnapshot.struct_type.ilike("%Storage Depot%")) |
                    (StockpileSnapshot.struct_type.ilike("%Seaport%"))
                )
                .order_by(StockpileSnapshot.town)
            )
            result = await conn.execute(stmt)
            return [row[0] for row in result.all() if row[0]]

    async def get_catalog_items(self) -> set[tuple[str, str]]:
        """Fetches codename/displayname pairs for validation."""
        async with self.engine.connect() as conn:
            stmt = select(CatalogItem.codename, CatalogItem.displayname)
            result = await conn.execute(stmt)
            return {(row.codename, row.displayname) for row in result}

    async def ingest_snapshot(self, town: str, struct_type: str, stockpile_name: str, items_data: list[dict]):
        """Creates a new snapshot and inserts its items in a single transaction."""
        async with self.engine.begin() as conn:
            # 1. Insert the snapshot header
            # Normalize names to avoid duplicates due to casing/spaces
            norm_town = town.strip().lower()
            norm_struct = struct_type.strip()
            norm_stockpile = stockpile_name.strip()

            stmt = insert(StockpileSnapshot).values(
                town=norm_town,
                struct_type=norm_struct,
                stockpile_name=norm_stockpile,
                captured_at=datetime.now(timezone.utc)
            ).returning(StockpileSnapshot.id)

            res = await conn.execute(stmt)
            snapshot_id = res.scalar_one()

            # 2. Insert items in bulk
            if items_data:
                for item in items_data:
                    item["snapshot_id"] = snapshot_id

                await conn.execute(insert(SnapshotItem), items_data)

            return snapshot_id

    async def get_latest_inventory(self, town: str, stockpile: str = None):
        """Fetches the latest item counts for a specific town."""
        async with self.engine.connect() as conn:
            norm_town = town.strip().lower()
            subq = (
                select(StockpileSnapshot.id)
                .where(StockpileSnapshot.town == norm_town)
                .distinct(StockpileSnapshot.town, StockpileSnapshot.struct_type, StockpileSnapshot.stockpile_name)
                .order_by(
                    StockpileSnapshot.town,
                    StockpileSnapshot.struct_type,
                    StockpileSnapshot.stockpile_name,
                    desc(StockpileSnapshot.captured_at),
                    desc(StockpileSnapshot.id)
                )
            )

            if stockpile:
                subq = subq.where(StockpileSnapshot.stockpile_name == stockpile.strip())

            # Join with SnapshotItem to get the actual inventory
            stmt = (
                select(
                    StockpileSnapshot.struct_type,
                    StockpileSnapshot.stockpile_name,
                    SnapshotItem.item_name,
                    SnapshotItem.code_name,
                    SnapshotItem.quantity,
                    SnapshotItem.is_crated,
                    SnapshotItem.total
                )
                .join(SnapshotItem, SnapshotItem.snapshot_id == StockpileSnapshot.id)
                .where(StockpileSnapshot.id.in_(subq))
                .order_by(StockpileSnapshot.stockpile_name, desc(SnapshotItem.is_crated), desc(SnapshotItem.quantity))
            )

            result = await conn.execute(stmt)
            return result.mappings().all()

    async def get_priority_list(self) -> list[dict]:
        """Fetches the full priority list from the DB."""
        async with self.engine.connect() as conn:
            stmt = select(Priority).order_by(Priority.priority)
            result = await conn.execute(stmt)
            return [dict(row) for row in result.mappings().all()]

    async def get_latest_snapshot_for_town(self, town: str):
        """Fetches the latest snapshot and its items for a specific town across ALL stockpiles."""
        async with self.engine.connect() as conn:
            norm_town = town.strip().lower()
            # Find the latest snapshot IDs for each unique stockpile in this town
            subq = (
                select(StockpileSnapshot.id)
                .where(StockpileSnapshot.town == norm_town)
                .distinct(StockpileSnapshot.town, StockpileSnapshot.struct_type, StockpileSnapshot.stockpile_name)
                .order_by(
                    StockpileSnapshot.town,
                    StockpileSnapshot.struct_type,
                    StockpileSnapshot.stockpile_name,
                    desc(StockpileSnapshot.captured_at),
                    desc(StockpileSnapshot.id)
                )
            )
            
            # Fetch all items from these latest snapshots
            stmt_items = (
                select(SnapshotItem)
                .where(SnapshotItem.snapshot_id.in_(subq))
            )
            items_res = await conn.execute(stmt_items)
            items = items_res.mappings().all()
            
            # Return any snapshot header as a reference
            latest_snap_stmt = (
                select(StockpileSnapshot)
                .where(StockpileSnapshot.town == norm_town)
                .order_by(desc(StockpileSnapshot.captured_at))
                .limit(1)
            )
            snap_res = await conn.execute(latest_snap_stmt)
            snapshot = snap_res.mappings().first()

            return snapshot, items

    async def search_item_across_stockpiles(self, item_name: str):
        """Finds all latest instances of an item across all towns with pretty town names."""
        async with self.engine.connect() as conn:
            subq = (
                select(StockpileSnapshot.id)
                .distinct(StockpileSnapshot.town, StockpileSnapshot.struct_type, StockpileSnapshot.stockpile_name)
                .order_by(
                    StockpileSnapshot.town,
                    StockpileSnapshot.struct_type,
                    StockpileSnapshot.stockpile_name,
                    desc(StockpileSnapshot.captured_at),
                    desc(StockpileSnapshot.id)
                )
            )

            stmt = (
                select(
                    Town.name.label("town"),
                    StockpileSnapshot.struct_type,
                    StockpileSnapshot.stockpile_name,
                    SnapshotItem.quantity,
                    SnapshotItem.is_crated,
                    SnapshotItem.per_crate,
                    SnapshotItem.total
                )
                .join(SnapshotItem, SnapshotItem.snapshot_id == StockpileSnapshot.id)
                # Join towns to get the pretty name
                .join(Town, text("LOWER(towns.name) = stockpile_snapshots.town"))
                .where(StockpileSnapshot.id.in_(subq))
                .where(SnapshotItem.item_name == item_name)
                .order_by(Town.name)
            )

            result = await conn.execute(stmt)
            return result.mappings().all()

    async def get_town_data(self, town_name: str):
        """Fetches coordinates and region offsets for a specific town (case-insensitive)."""
        async with self.engine.connect() as conn:
            from sqlalchemy import func
            stmt = (
                select(Town.name, Town.x, Town.y, Region.q, Region.r)
                .join(Region, Region.id == Town.region_id)
                .where(func.lower(Town.name) == town_name.strip().lower())
            )
            res = await conn.execute(stmt)
            return res.mappings().first()

    async def get_all_catalog_item_names(self) -> list[str]:
        """Fetches all item names from the catalog for autocomplete."""
        async with self.engine.connect() as conn:
            # Use DISTINCT on item_name from SnapshotItem or displayname from CatalogItem
            # CatalogItem is more robust for autocomplete
            stmt = select(CatalogItem.displayname).distinct().order_by(CatalogItem.displayname)
            result = await conn.execute(stmt)
            return [row[0] for row in result.all()]

    async def get_items_in_stockpiles(self) -> list[str]:
        """Fetches unique item names that are currently present in at least one stockpile snapshot."""
        async with self.engine.connect() as conn:
            stmt = select(SnapshotItem.item_name).distinct().order_by(SnapshotItem.item_name)
            result = await conn.execute(stmt)
            return [row[0] for row in result.all() if row[0]]
