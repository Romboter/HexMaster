import csv
import re
import pandas as pd
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine
from hexmaster.db.models import Town, CatalogItem, Priority, Region

# Manual overrides for regions that have different names in WarAPI vs In-Game
NAME_OVERRIDES = {
    "mooringcounty": "themoors"
}

def clean_region_name(name: str) -> str:
    """Removes 'hex' suffix and applies manual overrides."""
    if not name:
        return ""
    cleaned = re.sub(r"\s*hex$", "", name, flags=re.IGNORECASE).strip().lower()
    return NAME_OVERRIDES.get(cleaned, cleaned)


async def seed_towns_from_csv(engine: AsyncEngine, csv_path: Path) -> None:
    """Seeds the towns table from sample_data/Towns.csv."""
    if not csv_path.exists():
        return

    async with engine.connect() as conn:
        # 1. Fetch region name -> id mapping
        region_res = await conn.execute(select(Region.id, Region.name))
        region_map = {row.name: row.id for row in region_res}

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        towns_dict = {}
        for row in reader:
            name = row["Town"].strip()
            region_raw = row["Region"].strip()
            region_clean = clean_region_name(region_raw)
            
            region_id = region_map.get(region_clean)
            if region_id is None:
                print(f"⚠️ Warning: Region '{region_clean}' (from '{region_raw}') not found in DB. Skipping town '{name}'.")
                continue

            towns_dict[name] = {
                "name": name,
                "region_id": region_id,
                "x": float(row["x"]) if row.get("x") else 0.0,
                "y": float(row["y"]) if row.get("y") else 0.0,
                "marker_type": row.get("MarkerType", "Unknown").strip()
            }

        towns_data = list(towns_dict.values())

    if not towns_data:
        return

    async with engine.begin() as conn:
        # 3. UPSERT towns
        stmt = insert(Town).values(towns_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Town.name],
            set_={
                "region_id": stmt.excluded.region_id,
                "x": stmt.excluded.x,
                "y": stmt.excluded.y,
                "marker_type": stmt.excluded.marker_type,
            }
        )
        await conn.execute(stmt)
        
        # 4. DELETE towns not in the CSV
        all_town_names = [t["name"] for t in towns_data]
        from sqlalchemy import delete
        del_stmt = delete(Town).where(Town.name.not_in(all_town_names))
        res = await conn.execute(del_stmt)
        
        print(f"✅ Town reference seeded ({len(towns_data)} entries). Purged {res.rowcount} stale entries.")


async def seed_catalog_from_csv(engine: AsyncEngine, csv_path: Path) -> None:
    """Seeds the catalog_items table from sample_data/catalog.csv."""
    if not csv_path.exists():
        return

    df = pd.read_csv(csv_path)
    # 1. Map CSV columns to Model columns
    catalog_data = []
    for _, row in df.iterrows():
        qty = row.get("QuantityPerCrate")
        if pd.isna(qty) or str(qty).strip() == "":
            qty_val = None
        else:
            try:
                qty_val = int(float(qty))
            except (ValueError, TypeError):
                qty_val = None

        catalog_data.append({
            "codename": str(row["CodeName"]).strip(),
            "displayname": str(row["DisplayName"]).strip(),
            "factionvariant": str(row.get("FactionVariant", "Both")).strip(),
            "quantitypercrate": qty_val
        })

    # 2. Deduplicate by (codename, displayname)
    clean_data = {(item["codename"], item["displayname"]): item for item in catalog_data}
    items = list(clean_data.values())

    if not items:
        return

    async with engine.begin() as conn:
        stmt = insert(CatalogItem).values(items)
        stmt = stmt.on_conflict_do_update(
            index_elements=[CatalogItem.codename, CatalogItem.displayname],
            set_={
                "factionvariant": stmt.excluded.factionvariant,
                "quantitypercrate": stmt.excluded.quantitypercrate
            }
        )
        await conn.execute(stmt)
        print(f"✅ Catalog items seeded ({len(items)} entries).")


async def seed_priority_from_csv(engine: AsyncEngine, csv_path: Path) -> None:
    """Seeds the priority table from sample_data/Priority.csv."""
    if not csv_path.exists():
        return

    df = pd.read_csv(csv_path)
    priority_map = {}
    for _, row in df.iterrows():
        # Handle empty Min For Base (crates)
        min_crates = row.get("Min For Base (crates)")
        if pd.isna(min_crates) or min_crates == "":
            min_crates = None
        else:
            min_crates = int(min_crates)

        codename = str(row["CodeName"]).strip()
        priority_map[codename] = {
            "codename": codename,
            "name": str(row["Name"]).strip(),
            "qty_per_crate": int(row["Qty per Crate"]),
            "min_for_base_crates": min_crates,
            "priority": float(row["Priority"])
        }

    priority_data = list(priority_map.values())
    if not priority_data:
        return

    async with engine.begin() as conn:
        stmt = insert(Priority).values(priority_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Priority.codename],
            set_={
                "name": stmt.excluded.name,
                "qty_per_crate": stmt.excluded.qty_per_crate,
                "min_for_base_crates": stmt.excluded.min_for_base_crates,
                "priority": stmt.excluded.priority
            }
        )
        await conn.execute(stmt)
        print(f"✅ Priority list seeded ({len(priority_data)} entries).")


async def seed_regions_from_csv(engine: AsyncEngine, csv_path: Path) -> None:
    """Seeds the regions table from sample_data/Regions.csv."""
    if not csv_path.exists():
        return

    df = pd.read_csv(csv_path)
    regions_map = {}
    for _, row in df.iterrows():
        name = str(row["Region"]).strip().lower()
        # Map raw r from CSV to both 'r' and 'raw_r' to be safe and match DB observations
        q_val = float(row["raw q"]) if not pd.isna(row.get("raw q")) else 0.0
        r_val = float(row["raw r"]) if not pd.isna(row.get("raw r")) else 0.0
        
        regions_map[name] = {
            "name": name,
            "q": q_val,
            "raw_r": r_val,
            "r": r_val
        }

    regions_data = list(regions_map.values())
    if not regions_data:
        return

    async with engine.begin() as conn:
        # 1. UPSERT all regions from CSV
        stmt = insert(Region).values(regions_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Region.name],
            set_={
                "q": stmt.excluded.q,
                "raw_r": stmt.excluded.raw_r,
                "r": stmt.excluded.r,
            }
        )
        await conn.execute(stmt)
        
        # 2. DELETE regions that are not in the CSV
        all_names = [r["name"] for r in regions_data]
        from sqlalchemy import delete
        del_stmt = delete(Region).where(Region.name.not_in(all_names))
        res = await conn.execute(del_stmt)
        
        print(f"✅ Region reference seeded ({len(regions_data)} entries). Purged {res.rowcount} stale entries.")
