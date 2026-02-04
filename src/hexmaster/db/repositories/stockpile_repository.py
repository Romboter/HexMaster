from sqlalchemy import select, insert, desc
from sqlalchemy.ext.asyncio import AsyncEngine
from datetime import datetime, timezone
from hexmaster.db.models import StockpileSnapshot, SnapshotItem, CatalogItem, Town, Priority, Region


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
            stmt = insert(StockpileSnapshot).values(
                town=town,
                struct_type=struct_type,
                stockpile_name=stockpile_name,
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
            # Subquery to find the IDs of the latest snapshots for each unique combination
            # This uses Postgres 'DISTINCT ON' equivalent in SQLAlchemy
            subq = (
                select(StockpileSnapshot.id)
                .where(StockpileSnapshot.town == town)
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
                subq = subq.where(StockpileSnapshot.stockpile_name == stockpile)

            # Join with SnapshotItem to get the actual inventory
            stmt = (
                select(
                    StockpileSnapshot.struct_type,
                    StockpileSnapshot.stockpile_name,
                    SnapshotItem.item_name,
                    SnapshotItem.quantity,
                    SnapshotItem.is_crated
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
        """Fetches the latest snapshot and its items for a specific town."""
        async with self.engine.connect() as conn:
            # Find the latest snapshot for this town (highest ID/captured_at)
            stmt_snap = (
                select(StockpileSnapshot)
                .where(StockpileSnapshot.town == town)
                .order_by(desc(StockpileSnapshot.captured_at), desc(StockpileSnapshot.id))
                .limit(1)
            )
            snap_res = await conn.execute(stmt_snap)
            snapshot = snap_res.mappings().first()

            if not snapshot:
                return None, []

            # Get items for this snapshot
            stmt_items = (
                select(SnapshotItem)
                .where(SnapshotItem.snapshot_id == snapshot["id"])
            )
            items_res = await conn.execute(stmt_items)
            return snapshot, items_res.mappings().all()

    async def search_item_across_stockpiles(self, item_name: str):
        """Finds all latest instances of an item across all towns."""
        async with self.engine.connect() as conn:
            # Subquery to find the IDs of the latest snapshots for all towns
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
                    StockpileSnapshot.town,
                    StockpileSnapshot.struct_type,
                    StockpileSnapshot.stockpile_name,
                    SnapshotItem.quantity,
                    SnapshotItem.is_crated,
                    SnapshotItem.per_crate,
                    SnapshotItem.total
                )
                .join(SnapshotItem, SnapshotItem.snapshot_id == StockpileSnapshot.id)
                .where(StockpileSnapshot.id.in_(subq))
                .where(SnapshotItem.item_name == item_name)
                .order_by(StockpileSnapshot.town)
            )

            result = await conn.execute(stmt)
            return result.mappings().all()

    async def get_town_data(self, town_name: str):
        """Fetches coordinates and region offsets for a specific town."""
        async with self.engine.connect() as conn:
            stmt = (
                select(Town.name, Town.x, Town.y, Region.q, Region.r)
                .join(Region, Region.id == Town.region_id)
                .where(Town.name == town_name)
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
