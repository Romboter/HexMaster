import csv
import pandas as pd
from pathlib import Path
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine
from hexmaster.db.models import Town, CatalogItem


async def seed_towns_from_csv(engine: AsyncEngine, csv_path: Path) -> None:
    """Seeds the towns table from sample_data/Towns.csv."""
    if not csv_path.exists():
        return

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        towns_dict = {}
        for row in reader:
            name = row["Town"].strip()
            towns_dict[name] = {
                "name": name,
                "region": row["Region"].strip(),
                "x": float(row["x"]) if row.get("x") else 0.0,
                "y": float(row["y"]) if row.get("y") else 0.0,
                "marker_type": row.get("MarkerType", "Unknown").strip()
            }

        towns_data = list(towns_dict.values())

    if not towns_data:
        return

    async with engine.begin() as conn:
        stmt = insert(Town).values(towns_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Town.name],
            set_={
                "region": stmt.excluded.region,
                "x": stmt.excluded.x,
                "y": stmt.excluded.y,
                "marker_type": stmt.excluded.marker_type,
            }
        )
        await conn.execute(stmt)
        print(f"✅ Town reference seeded ({len(towns_data)} entries).")


async def seed_catalog_from_csv(engine: AsyncEngine, csv_path: Path) -> None:
    """Seeds the catalog_items table from sample_data/catalog.csv."""
    if not csv_path.exists():
        return

    df = pd.read_csv(csv_path)
    # 1. Map CSV columns to Model columns and filter only what we need
    # This handles the "Unconsumed column names" error by ignoring extra CSV columns
    catalog_data = []
    for _, row in df.iterrows():
        catalog_data.append({
            "codename": str(row["CodeName"]).strip(),
            "displayname": str(row["DisplayName"]).strip()
        })

    # 2. Deduplicate by codename (last entry wins)
    clean_data = {item["codename"]: item for item in catalog_data}
    items = list(clean_data.values())

    if not items:
        return

    async with engine.begin() as conn:
        stmt = insert(CatalogItem).values(items)
        stmt = stmt.on_conflict_do_update(
            index_elements=[CatalogItem.codename],
            set_={"displayname": stmt.excluded.displayname}
        )
        await conn.execute(stmt)
        print(f"✅ Catalog items seeded ({len(items)} entries).")
