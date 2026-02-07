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

    def _normalize_name(self, name: str) -> str:
        """Helper to normalize town/stockpile names."""
        return name.strip().lower() if name else ""

    def _latest_snapshots_subquery(self, town: str = None, struct_type: str = None, stockpile: str = None):
        """Helper to find the most recent snapshot IDs for unique (town, struct, stockpile) tuples."""
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
        if town:
            subq = subq.where(StockpileSnapshot.town == self._normalize_name(town))
        if struct_type:
            subq = subq.where(StockpileSnapshot.struct_type == struct_type.strip())
        if stockpile:
            subq = subq.where(StockpileSnapshot.stockpile_name == stockpile.strip())
        return subq

    async def get_towns_with_snapshots(self) -> list[str]:
        """Fetches unique pretty town names that already have snapshots in the DB."""
        async with self.engine.connect() as conn:
            stmt = (
                select(Town.name)
                .distinct()
                .join(StockpileSnapshot, text("LOWER(towns.name) = stockpile_snapshots.town"))
                .order_by(Town.name)
            )
            result = await conn.execute(stmt)
            return [row[0] for row in result.all()]

    async def get_struct_types_for_town(self, town: str) -> list[str]:
        """Fetches unique structure types for a specific town."""
        async with self.engine.connect() as conn:
            stmt = (
                select(StockpileSnapshot.struct_type)
                .distinct()
                .where(StockpileSnapshot.town == self._normalize_name(town))
                .order_by(StockpileSnapshot.struct_type)
            )
            result = await conn.execute(stmt)
            return [row[0] for row in result.all()]

    async def get_stockpile_names_for_town(self, town: str, struct_type: str = None) -> list[str]:
        """Fetches unique stockpile names for a specific town and optional structure type."""
        async with self.engine.connect() as conn:
            stmt = (
                select(StockpileSnapshot.stockpile_name)
                .distinct()
                .where(StockpileSnapshot.town == self._normalize_name(town))
            )
            if struct_type:
                stmt = stmt.where(StockpileSnapshot.struct_type == struct_type.strip())
            
            stmt = stmt.order_by(StockpileSnapshot.stockpile_name)
            result = await conn.execute(stmt)
            return [row[0] for row in result.all()]

    async def get_towns_with_hub_snapshots(self) -> list[str]:
        """Fetches pretty town names that have at least one Seaport or Storage Depot snapshot."""
        async with self.engine.connect() as conn:
            stmt = (
                select(Town.name)
                .distinct()
                .join(StockpileSnapshot, text("LOWER(towns.name) = stockpile_snapshots.town"))
                .where(
                    (StockpileSnapshot.struct_type.ilike("%Storage Depot%")) |
                    (StockpileSnapshot.struct_type.ilike("%Seaport%"))
                )
                .order_by(Town.name)
            )
            result = await conn.execute(stmt)
            return [row[0] for row in result.all()]

    async def get_catalog_items(self) -> set[tuple[str, str]]:
        """Fetches codename/displayname pairs for validation."""
        async with self.engine.connect() as conn:
            stmt = select(CatalogItem.codename, CatalogItem.displayname)
            result = await conn.execute(stmt)
            return {(row.codename, row.displayname) for row in result}

    async def ingest_snapshot(self, town: str, struct_type: str, stockpile_name: str, items_data: list[dict], war_number: int | None = None):
        """Creates a new snapshot and inserts its items in a single transaction."""
        async with self.engine.begin() as conn:
            # 1. Insert the snapshot header
            # Normalize names to avoid duplicates due to casing/spaces
            norm_town = self._normalize_name(town)
            norm_struct = struct_type.strip()
            norm_stockpile = stockpile_name.strip()

            stmt = insert(StockpileSnapshot).values(
                town=norm_town,
                struct_type=norm_struct,
                stockpile_name=norm_stockpile,
                war_number=war_number,
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

    async def get_latest_inventory(self, town: str, struct_type: str = None, stockpile: str = None):
        """Fetches the latest item counts for a specific town."""
        async with self.engine.connect() as conn:
            subq = self._latest_snapshots_subquery(town=town, struct_type=struct_type, stockpile=stockpile)

            # Join with SnapshotItem and Town to get actual inventory with pretty names
            stmt = (
                select(
                    StockpileSnapshot.struct_type,
                    StockpileSnapshot.stockpile_name,
                    SnapshotItem.item_name,
                    SnapshotItem.code_name,
                    SnapshotItem.quantity,
                    SnapshotItem.is_crated,
                    SnapshotItem.total,
                    StockpileSnapshot.war_number,
                    CatalogItem.quantitypercrate.label("catalog_qpc"),
                    Town.name.label("pretty_town"),
                    StockpileSnapshot.captured_at
                )
                .join(SnapshotItem, SnapshotItem.snapshot_id == StockpileSnapshot.id)
                .join(CatalogItem, CatalogItem.codename == SnapshotItem.code_name)
                .join(Town, text("LOWER(towns.name) = stockpile_snapshots.town"))
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

    async def get_latest_snapshot_for_town_filtered(self, town: str, struct_type: str = None, stockpile: str = None):
        """Fetches the latest snapshot and its items for a specific town with optional filters."""
        async with self.engine.connect() as conn:
            norm_town = self._normalize_name(town)
            # Find the latest snapshot IDs for each unique (struct, stockpile) in this town
            subq = self._latest_snapshots_subquery(town=town, struct_type=struct_type, stockpile=stockpile)
            
            # Fetch all items from these latest snapshots
            stmt_items = (
                select(
                    SnapshotItem.code_name,
                    SnapshotItem.item_name,
                    SnapshotItem.total,
                    SnapshotItem.per_crate,
                    CatalogItem.quantitypercrate.label("catalog_qpc")
                )
                .join(CatalogItem, CatalogItem.codename == SnapshotItem.code_name)
                .where(SnapshotItem.snapshot_id.in_(subq))
            )
            items_res = await conn.execute(stmt_items)
            items = items_res.mappings().all()
            
            # Return any snapshot header as a reference, with pretty town name
            latest_snap_stmt = (
                select(
                    StockpileSnapshot.struct_type, 
                    StockpileSnapshot.stockpile_name, 
                    StockpileSnapshot.war_number,
                    Town.name.label("pretty_town"),
                    StockpileSnapshot.captured_at
                )
                .join(Town, text("LOWER(towns.name) = stockpile_snapshots.town"))
                .where(StockpileSnapshot.town == norm_town)
            )
            if struct_type:
                latest_snap_stmt = latest_snap_stmt.where(StockpileSnapshot.struct_type == struct_type.strip())
            if stockpile:
                latest_snap_stmt = latest_snap_stmt.where(StockpileSnapshot.stockpile_name == stockpile.strip())
            
            latest_snap_stmt = latest_snap_stmt.order_by(desc(StockpileSnapshot.captured_at)).limit(1)
            
            snap_res = await conn.execute(latest_snap_stmt)
            snapshot = snap_res.mappings().first()

            return snapshot, items

    async def get_latest_snapshot_for_town(self, town: str):
        """Deprecated: Use get_latest_snapshot_for_town_filtered instead. 
        Fetches the latest snapshot and its items for a specific town across ALL stockpiles."""
        return await self.get_latest_snapshot_for_town_filtered(town)

    async def search_item_across_stockpiles(self, item_name: str):
        """Finds all latest instances of an item across all towns with pretty town names."""
        async with self.engine.connect() as conn:
            subq = self._latest_snapshots_subquery()

            stmt = (
                select(
                    Town.name.label("town"),
                    StockpileSnapshot.struct_type,
                    StockpileSnapshot.stockpile_name,
                    SnapshotItem.quantity,
                    SnapshotItem.is_crated,
                    SnapshotItem.per_crate,
                    SnapshotItem.total,
                    CatalogItem.quantitypercrate.label("catalog_qpc"),
                    Town.x,
                    Town.y,
                    Region.q,
                    Region.r,
                    StockpileSnapshot.captured_at
                )
                .join(SnapshotItem, SnapshotItem.snapshot_id == StockpileSnapshot.id)
                # Join towns to get the pretty name and x, y
                .join(Town, text("LOWER(towns.name) = stockpile_snapshots.town"))
                # Join regions to get q, r
                .join(Region, Region.id == Town.region_id)
                # Join catalog to get canonical crate size
                .join(CatalogItem, CatalogItem.codename == SnapshotItem.code_name)
                .where(StockpileSnapshot.id.in_(subq))
                .where(SnapshotItem.item_name == item_name)
                .order_by(Town.name)
            )

            result = await conn.execute(stmt)
            return result.mappings().all()

    async def get_latest_snapshots_summary(self, limit: int = 10):
        """Fetches a summary of the most recent snapshots across all towns."""
        async with self.engine.connect() as conn:
            stmt = (
                select(
                    StockpileSnapshot.id,
                    Town.name.label("pretty_town"),
                    StockpileSnapshot.struct_type,
                    StockpileSnapshot.stockpile_name,
                    StockpileSnapshot.captured_at,
                    StockpileSnapshot.war_number
                )
                .join(Town, text("LOWER(towns.name) = stockpile_snapshots.town"))
                .order_by(desc(StockpileSnapshot.captured_at))
                .limit(limit)
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
                .where(func.lower(Town.name) == self._normalize_name(town_name))
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

