import pandas as pd
import requests
import re

REGIONS_CSV = "data/Regions.csv"
WARAPI_MAPS_URL = "https://war-service-live-2.foxholeservices.com/api/worldconquest/maps"

def clean_region_name(name):
    # Remove "hex" or " hex" suffix (case-insensitive)
    return re.sub(r"\s*hex$", "", str(name), flags=re.IGNORECASE).strip().lower()

def main():
    print("Reading Regions.csv...")
    try:
        df = pd.read_csv(REGIONS_CSV)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    print(f"Total rows in CSV: {len(df)}")
    
    # Analyze names
    df['cleaned_name'] = df['Region'].apply(clean_region_name)
    
    unique_original = df['Region'].unique()
    unique_cleaned = df['cleaned_name'].unique()
    
    print(f"Unique cleaned names ({len(unique_cleaned)}):")
    print(sorted(list(unique_cleaned)))

    # Fetch from WarAPI
    print(f"Fetching map list from WarAPI ({WARAPI_MAPS_URL})...")
    with open("analyze_results.txt", "w", encoding="utf-8") as out:
        out.write(f"Total rows in CSV: {len(df)}\n")
        out.write(f"Unique original names: {len(unique_original)}\n")
        out.write(f"Unique cleaned names: {len(unique_cleaned)}\n")
        out.write(f"Unique cleaned names list: {sorted(list(unique_cleaned))}\n\n")

        try:
            response = requests.get(WARAPI_MAPS_URL, timeout=30)
            response.raise_for_status()
            warapi_maps = sorted([m.lower() for m in response.json()])
            out.write(f"Total maps from WarAPI: {len(warapi_maps)}\n")
            out.write(f"WarAPI maps list: {warapi_maps}\n\n")
            
            # Compare
            missing_in_warapi = sorted(list(set(unique_cleaned) - set(warapi_maps)))
            missing_in_csv = sorted(list(set(warapi_maps) - set(unique_cleaned)))
            
            out.write(f"Cleaned names NOT in WarAPI ({len(missing_in_warapi)}):\n")
            out.write(f"{missing_in_warapi}\n\n")
                
            out.write(f"WarAPI maps NOT in CSV ({len(missing_in_csv)}):\n")
            out.write(f"{missing_in_csv}\n")
            
            print("Results saved to analyze_results.txt")
        except Exception as e:
            out.write(f"Error fetching from WarAPI: {e}\n")
            print(f"Error fetching from WarAPI: {e}")

if __name__ == "__main__":
    main()
