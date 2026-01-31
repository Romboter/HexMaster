from __future__ import annotations

import asyncio
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from hexmaster.config import Settings
from hexmaster.db.init import init_db
from hexmaster.db.models import Region, Town

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # .../src/hexmaster/db -> project root
SAMPLE_DATA = PROJECT_ROOT / "sample_data"


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    s = value.strip()
    if s == "":
        return None
    return float(s)


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    s = value.strip()
    if s == "":
        return None
    return int(s)


@dataclass(frozen=True)
class SeedPaths:
    regions_csv: Path
    towns_tsv: Path


def default_seed_paths() -> SeedPaths:
    return SeedPaths(
        regions_csv=SAMPLE_DATA / "Regions.csv",
        towns_tsv=SAMPLE_DATA / "towns.tsv",
    )


async def seed_regions(engine: AsyncEngine, regions_csv: Path) -> None:
    if not regions_csv.exists():
        raise FileNotFoundError(f"Regions file not found: {regions_csv}")

    with regions_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows: list[dict[str, Any]] = []
        for r in reader:
            name = (r.get("Region") or "").strip()
            if not name:
                continue
            rows.append(
                {
                    "name": name,
                    "q": _to_float(r.get("q")),
                    "raw_r": _to_float(r.get("raw r")),
                    "r": _to_float(r.get("r")),
                    "distance_to_origin": _to_float(r.get("Distance To Origin")),
                }
            )

    if not rows:
        return

    stmt = insert(Region).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Region.name],
        set_={
            "q": stmt.excluded.q,
            "raw_r": stmt.excluded.raw_r,
            "r": stmt.excluded.r,
            "distance_to_origin": stmt.excluded.distance_to_origin,
        },
    )

    async with engine.begin() as conn:
        await conn.execute(stmt)


async def seed_towns(engine: AsyncEngine, towns_tsv: Path) -> None:
    if not towns_tsv.exists():
        raise FileNotFoundError(f"Towns file not found: {towns_tsv}")

    # towns.tsv is comma-separated in your sample_data (despite .tsv extension)
    # Header: Region,Town,x,y,MarkerType,global q,global r,Type
    with towns_tsv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=",")
        towns: list[dict[str, Any]] = []
        region_names: set[str] = set()

        for r in reader:
            region_name = (r.get("Region") or "").strip()
            town_name = (r.get("Town") or "").strip()
            if not region_name or not town_name:
                continue

            region_names.add(region_name)
            towns.append(
                {
                    "region_name": region_name,
                    "name": town_name,
                    "x": _to_float(r.get("x")),
                    "y": _to_float(r.get("y")),
                    "marker_type": (r.get("MarkerType") or "").strip() or None,
                    "global_q": _to_float(r.get("global q")),
                    "global_r": _to_float(r.get("global r")),
                    "town_type": (r.get("Type") or "").strip() or None,
                }
            )

    if not towns:
        return

    # Build a mapping Region.name -> Region.id
    async with engine.begin() as conn:
        res = await conn.execute(select(Region.id, Region.name).where(Region.name.in_(sorted(region_names))))
        region_map = {name: rid for rid, name in res.all()}

        missing = sorted(region_names - set(region_map.keys()))
        if missing:
            raise RuntimeError(
                "towns.tsv references regions that do not exist in regions table. "
                f"Missing regions: {missing}. Seed regions first."
            )

        town_rows = [
            {
                "region_id": region_map[t["region_name"]],
                "name": t["name"],
                "x": t["x"],
                "y": t["y"],
                "marker_type": t["marker_type"],
                "global_q": t["global_q"],
                "global_r": t["global_r"],
                "town_type": t["town_type"],
            }
            for t in towns
        ]

        stmt = insert(Town).values(town_rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_towns_name",
            set_={
                "region_id": stmt.excluded.region_id,
                "x": stmt.excluded.x,
                "y": stmt.excluded.y,
                "marker_type": stmt.excluded.marker_type,
                "global_q": stmt.excluded.global_q,
                "global_r": stmt.excluded.global_r,
                "town_type": stmt.excluded.town_type,
            },
        )
        await conn.execute(stmt)


async def seed_all(engine: AsyncEngine, paths: SeedPaths) -> None:
    await init_db(engine)
    await seed_regions(engine, paths.regions_csv)
    await seed_towns(engine, paths.towns_tsv)


async def _amain() -> None:
    settings = Settings.load()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        await seed_all(engine, default_seed_paths())
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
