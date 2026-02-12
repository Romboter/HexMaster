# Copyright (c) 2024-2025 Gary Kuepper
# Licensed under the MIT License.

import os
import re
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
WARAPI_BASE_URL = os.getenv("WARAPI_BASE_URL", "https://war-service-live.foxholeservices.com/api")
WARAPI_MAPS_URL = f"{WARAPI_BASE_URL}/worldconquest/maps"
REGIONS_CSV_PATH = Path("data/core/Regions.csv")

# Manual overrides for regions that have different names in WarAPI vs In-Game
NAME_OVERRIDES = {"mooringcounty": "themoors"}


def clean_region_name(name):
    """
    Removes 'hex' suffix (case-insensitive) and strips whitespace.
    Applies manual name overrides (e.g., mooringcounty -> themoors).
    """
    if not isinstance(name, str):
        return ""
    # Remove 'hex' at the end, handling potential ' Hex' as well
    cleaned = re.sub(r"\s*hex$", "", name, flags=re.IGNORECASE).strip().lower()

    # Apply overrides
    return NAME_OVERRIDES.get(cleaned, cleaned)


def main():
    print("Fetching map list from WarAPI...")
    try:
        response = requests.get(WARAPI_MAPS_URL, timeout=30)
        response.raise_for_status()
        warapi_maps = response.json()
        print(f"Found {len(warapi_maps)} maps in WarAPI.")
    except Exception as e:
        print(f"Error fetching from WarAPI: {e}")
        return

    # 1. Build a map of existing coordinates from Regions.csv
    coords_map: dict[str, tuple[float, float]] = {}
    if REGIONS_CSV_PATH.exists():
        print(f"Reading existing coordinates from {REGIONS_CSV_PATH}...")
        df_old = pd.read_csv(REGIONS_CSV_PATH)
        for _, row in df_old.iterrows():
            orig_name = str(row["Region"]).strip()
            # We clean the name to use as a key, but we want the best coords
            # Usually the coords are the same for 'name' and 'namehex'
            clean_name = clean_region_name(orig_name)
            q = row["raw q"]
            r = row["raw r"]

            # If we don't have coords for this clean name yet, or if they were 0,0, prefer non-zero
            if clean_name not in coords_map or (coords_map[clean_name][0] == 0 and coords_map[clean_name][1] == 0):
                coords_map[clean_name] = (q, r)
    else:
        print(f"Warning: {REGIONS_CSV_PATH} not found. Will use (0,0) for new regions.")

    # 2. Build the new list of regions based on WarAPI
    new_rows = []
    for map_name in warapi_maps:
        cleaned_name = clean_region_name(map_name)
        q, r = coords_map.get(cleaned_name, (0.0, 0.0))
        new_rows.append({"Region": cleaned_name, "raw q": q, "raw r": r})

    # 3. Create DataFrame and deduplicate just in case (though WarAPI should be unique)
    df_new = pd.DataFrame(new_rows).drop_duplicates(subset=["Region"])

    # 4. Save to CSV
    # Ensure directory exists (though it should)
    REGIONS_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Sort by name for consistency
    df_new = df_new.sort_values(by="Region")

    df_new.to_csv(REGIONS_CSV_PATH, index=False)
    print(f"Successfully updated {REGIONS_CSV_PATH} with {len(df_new)} regions.")

    # Verification
    if len(df_new) != len(warapi_maps):
        print(f"Warning: Resulting count ({len(df_new)}) does not match WarAPI count ({len(warapi_maps)}).")
        # Check for duplicates in WarAPI that might have caused this
        seen = set()
        dupes = []
        for m in warapi_maps:
            c = clean_region_name(m)
            if c in seen:
                dupes.append(m)
            seen.add(c)
        if dupes:
            print(f"Duplicate cleaned names in WarAPI: {dupes}")


if __name__ == "__main__":
    main()
