from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from hexmaster.config import Settings
from hexmaster.db.init import init_db

CREATE_TABLE_SQL = """
                       CREATE TABLE IF NOT EXISTS catalog_items
                       (
                           codename         text    NOT NULL,
                           displayname      text    NOT NULL,
                           factionvariant   text    NOT NULL CHECK (factionvariant IN ('Colonials', 'Wardens', 'Both')),
                           quantitypercrate integer NULL,
                           PRIMARY KEY (codename, displayname)
                       );
                       """

CREATE_STAGE_SQL = """
                       CREATE TABLE IF NOT EXISTS catalog_items_stage
                       (
                           codename         text    NOT NULL,
                           displayname      text    NOT NULL,
                           factionvariant   text    NOT NULL,
                           quantitypercrate integer NULL
                       );
                       """

TRUNCATE_STAGE_SQL = "TRUNCATE TABLE catalog_items_stage;"

UPSERT_SQL = """
                 INSERT INTO catalog_items AS t (codename, displayname, factionvariant, quantitypercrate)
             SELECT codename, displayname, factionvariant, quantitypercrate
             FROM catalog_items_stage
             ON CONFLICT (codename, displayname)
                 DO UPDATE SET factionvariant   = EXCLUDED.factionvariant,
                               quantitypercrate = EXCLUDED.quantitypercrate; \
             """


def load_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # Normalize expected column names (handles accidental casing differences)
    df = df.rename(
        columns={
            "CodeName": "codename",
            "DisplayName": "displayname",
            "FactionVariant": "factionvariant",
            "QuantityPerCrate": "quantitypercrate",
        }
    )

    required = {"codename", "displayname", "factionvariant", "quantitypercrate"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")

    # Ensure DB-friendly dtypes
    df["codename"] = df["codename"].astype(str)
    df["displayname"] = df["displayname"].astype(str)
    df["factionvariant"] = df["factionvariant"].fillna("Both").astype(str)

    # QuantityPerCrate may be blank -> NULL; use pandas nullable Int64
    df["quantitypercrate"] = pd.to_numeric(df["quantitypercrate"], errors="coerce").astype("Int64")

    # Enforce uniqueness before insert (matches your “primary keys” expectation)
    if df["codename"].duplicated().any():
        dupes = df[df["codename"].duplicated(keep=False)][["codename", "displayname"]]
        raise ValueError(f"Duplicate codename(s) found:\n{dupes.to_string(index=False)}")

    if df["displayname"].duplicated().any():
        dupes = df[df["displayname"].duplicated(keep=False)][["codename", "displayname"]]
        raise ValueError(f"Duplicate displayname(s) found:\n{dupes.to_string(index=False)}")

    # Final column order
    return df[["codename", "displayname", "factionvariant", "quantitypercrate"]]


async def import_catalog(csv_path: Path) -> None:
    settings = Settings.load()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)

    try:
        # Ensure your DB is initialized (keeps consistent with bot startup)
        await init_db(engine)

        df = load_csv(csv_path)

        async with engine.begin() as conn:
            # Ensure tables exist
            await conn.execute(text(CREATE_TABLE_SQL))
            await conn.execute(text(CREATE_STAGE_SQL))
            await conn.execute(text(TRUNCATE_STAGE_SQL))

            # Load into stage table via pandas (sync side), inside the async connection
            def _to_sql(sync_conn):
                df.to_sql(
                    "catalog_items_stage",
                    con=sync_conn,
                    if_exists="append",
                    index=False,
                    method="multi",
                    chunksize=2000,
                )

            await conn.run_sync(_to_sql)

            # Upsert into final table
            await conn.execute(text(UPSERT_SQL))

        print(f"Imported {len(df)} rows from {csv_path} into catalog_items")

    finally:
        await engine.dispose()


def main() -> None:
    # Calculate path relative to this script
    script_dir = Path(__file__).parent
    csv_path = script_dir.parent / "sample_data" / "catalog.csv"

    if not csv_path.exists():
        print(f"Error: CSV file not found at: {csv_path.absolute()}")
        return

    asyncio.run(import_catalog(csv_path))


if __name__ == "__main__":
    main()
