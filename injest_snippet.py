import os
import asyncio
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def parse_bool(x) -> bool | None:
    if pd.isna(x):
        return None
    s = str(x).strip().upper()
    if s in ("TRUE", "T", "1", "YES", "Y"):
        return True
    if s in ("FALSE", "F", "0", "NO", "N"):
        return False
    return None


async def ingest_tsv(tsv_path: str, stockpile_key: str) -> int:
    """
    Inserts:
      - 1 row into stockpile_snapshots
      - N rows into snapshot_items (one per TSV line)
    Returns snapshot_id.
    """
    db_url = os.environ["DATABASE_URL"]  # e.g. postgresql+asyncpg://user:pass@localhost:5432/db

    # This script must match an async URL (postgresql+asyncpg://...) with an async engine.
    engine = create_async_engine(db_url)

    df = pd.read_csv(tsv_path, sep="\t", dtype=str).fillna("")

    # Expected columns include:
    # Quantity, Name, Crated?, Per Crate, Total, Description, CodeName, etc.

    # Normalize / convert types
    df["quantity"] = pd.to_numeric(df.get("Quantity", ""), errors="coerce").astype("Int64")
    df["per_crate"] = pd.to_numeric(df.get("Per Crate", ""), errors="coerce").astype("Int64")
    df["total"] = pd.to_numeric(df.get("Total", ""), errors="coerce").astype("Int64")
    df["is_crated"] = df.get("Crated?", "").map(parse_bool)

    captured_at = datetime.now(timezone.utc)

    async with engine.begin() as conn:
        snapshot_id = await conn.execute(
            text(
                """
                INSERT INTO stockpile_snapshots (stockpile_key, captured_at)
                VALUES (:stockpile_key, :captured_at)
                RETURNING id
                """
            ),
            {"stockpile_key": stockpile_key, "captured_at": captured_at},
        )
        snapshot_id = snapshot_id.scalar_one()

        rows: list[dict] = []
        for _, r in df.iterrows():
            code_name = r.get("CodeName", "").strip()
            item_name = r.get("Name", "").strip()

            if not code_name or not item_name:
                continue  # skip malformed lines

            rows.append(
                {
                    "snapshot_id": snapshot_id,
                    "code_name": code_name,
                    "item_name": item_name,
                    "quantity": None if pd.isna(r["quantity"]) else int(r["quantity"]),
                    "is_crated": r["is_crated"],
                    "per_crate": None if pd.isna(r["per_crate"]) else int(r["per_crate"]),
                    "total": None if pd.isna(r["total"]) else int(r["total"]),
                    "description": r.get("Description", "").strip(),
                }
            )

        if rows:
            await conn.execute(
                text(
                    """
                    INSERT INTO snapshot_items
                    (snapshot_id, code_name, item_name, quantity, is_crated, per_crate, total, description)
                    VALUES (:snapshot_id, :code_name, :item_name, :quantity, :is_crated, :per_crate, :total, :description)
                    """
                ),
                rows,
            )

    await engine.dispose()
    return snapshot_id


async def main() -> None:
    snapshot_id = await ingest_tsv(
        tsv_path="sample_data/Foxhole Logi Tool - TheManacle.tsv",
        stockpile_key="TheManacle|Seaport|Public",
    )
    print(f"Inserted snapshot_id={snapshot_id}")


if __name__ == "__main__":
    asyncio.run(main())
