import json
from pathlib import Path

import pandas as pd


CATALOG_PATH = Path("../data/catalog.json")

def normalize_faction(value) -> str:
    if isinstance(value, str):
        if "Colonials" in value:
            return "Colonials"
        if "Wardens" in value:
            return "Wardens"
    return "Both"

def load_catalog(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def extract_items(raw_items: list[dict]) -> pd.DataFrame:
    records = []

    for item in raw_items:
        code_name = item.get("CodeName")
        display_name = item.get("DisplayName")
        faction = item.get("FactionVariant")

        # QuantityPerCrate is nested and not guaranteed to exist
        quantity_per_crate = None
        item_dynamic = item.get("ItemDynamicData")
        if isinstance(item_dynamic, dict):
            quantity_per_crate = item_dynamic.get("QuantityPerCrate")

        # Skip entries without required keys
        if not code_name or not display_name:
            continue

        records.append(
            {
                "CodeName": code_name,
                "DisplayName": display_name,
                "FactionVariant": faction,
                "QuantityPerCrate": quantity_per_crate,
            }
        )

    df = pd.DataFrame.from_records(records)
    df["FactionVariant"] = df["FactionVariant"].apply(normalize_faction)

    return df


def enforce_primary_keys(df: pd.DataFrame) -> pd.DataFrame:
    # Ensure uniqueness like a DB primary key constraint
    if df["CodeName"].duplicated().any():
        dupes = df[df["CodeName"].duplicated(keep=False)]
        raise ValueError(f"Duplicate CodeName detected:\n{dupes}")

    if df["DisplayName"].duplicated().any():
        dupes = df[df["DisplayName"].duplicated(keep=False)]
        raise ValueError(f"Duplicate DisplayName detected:\n{dupes}")

    return df


def main() -> None:
    raw_items = load_catalog(CATALOG_PATH)
    df = extract_items(raw_items)
    df = enforce_primary_keys(df)

    # Optional: make them explicit index keys
    df = df.set_index(["CodeName", "DisplayName"])

    print(df.head())
    print(f"\nLoaded {len(df)} unique catalog items.")
    input_csv = "data/core/catalog.csv"
    output_json = "data/core/catalog.json"
    df.to_csv(input_csv)

if __name__ == "__main__":
    main()
