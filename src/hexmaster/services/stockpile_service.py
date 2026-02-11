# Copyright (c) 2024-2025 Gary Kuepper
# Licensed under the MIT License.

import pandas as pd

from hexmaster.utils.geo_utils import calculate_distance


class StockpileService:
    def __init__(self, repo, ocr_service, war_service=None):
        self.repo = repo
        self.ocr_service = ocr_service
        self.war_service = war_service

    def get_qty_crates(self, total: float, catalog_qpc: int | None, per_crate: int | None) -> float:
        """Calculates quantity in crates based on available metadata."""
        qpc = catalog_qpc or per_crate or 1
        return total / qpc

    async def process_remote_and_ingest(
        self, guild_id: int, image_bytes: bytes, town: str, stockpile_name: str, war_number: int | None = None
    ):
        """Coordinates the OCR process and database ingestion."""
        try:
            # town and stockpile_name passed here are used as fallbacks if FS fails to detect them
            df = await self.ocr_service.process_image(image_bytes, town, stockpile_name)
        except Exception:
            # Let OCRServiceError bubble up to the cog for better formatting
            raise

        if df.empty:
            raise ValueError("OCR returned no data from the image.")

        # Extract metadata from the first row (populated by OCRService)
        first_row = df.iloc[0]
        struct_type = str(first_row.get("Structure Type", "Unknown")).strip()
        
        # Priority: OCR Detected Name > User Fallback (if default set to "Public")
        detected_stockpile = str(first_row.get("Stockpile Name", "")).strip()
        if detected_stockpile:
             stockpile_name = detected_stockpile

        # --- UPDATED LOOKUP LOGIC ---
        valid_pairs = await self.repo.get_catalog_items()
        # Create a map of CodeName -> DisplayName
        code_to_name = {c: n for c, n in valid_pairs}

        items = []
        for _, r in df.iterrows():
            cname = str(r.get("CodeName", "")).strip()
            
            # If valid code, use the DB's pretty name. 
            # If invalid code, skip it (it might be a modded item or OCR error)
            if cname in code_to_name:
                real_name = code_to_name[cname]
                
                qty = int(r["Quantity"]) if pd.notna(r.get("Quantity")) else 0
                is_crated = str(r.get("Crated?", "")).upper() in ("TRUE", "YES", "T", "Y")
                
                # Calculate totals if not provided by OCR
                # (FS usually provides raw quantity and crated status, not total items)
                # We let the repo/view logic handle the crates-to-items math based on the catalog definition
                
                items.append({
                    "code_name": cname,
                    "item_name": real_name, # Use the clean name from DB
                    "quantity": qty,
                    "is_crated": is_crated,
                    "per_crate": 0, # Will be filled by DB default on read if 0
                    "total": qty,   # Temporarily store raw qty; detailed math happens on read
                    "description": ""
                })
        snapshot_id = await self.repo.ingest_snapshot(guild_id, town, struct_type, stockpile_name, items, war_number)
        return snapshot_id, len(items), struct_type

    async def get_requisition_comparison(
        self,
        guild_id: int,
        shipping_hub: str,
        receiving: str,
        min_multiplier: float | None = None,
        ship_struct: str | None = None,
        ship_stockpile: str | None = None,
        recv_struct: str | None = None,
        recv_stockpile: str | None = None,
    ):
        """Calculates logic for comparing two towns for requisition."""
        priority_list = await self.repo.get_priority_list(guild_id)
        if not priority_list:
            raise ValueError("Priority list is empty.")

        ship_snap, ship_items = await self.repo.get_latest_snapshot_for_town_filtered(
            guild_id, shipping_hub, ship_struct, ship_stockpile
        )
        recv_snap, recv_items = await self.repo.get_latest_snapshot_for_town_filtered(
            guild_id, receiving, recv_struct, recv_stockpile
        )

        if not recv_snap:
            raise ValueError(f"No snapshots found for receiving town `{receiving}`.")

        # Process inventories into total quantities by code_name
        ship_total_map: dict[str, int] = {}
        for item in ship_items:
            ship_total_map[item["code_name"]] = ship_total_map.get(item["code_name"], 0) + item["total"]

        recv_total_map: dict[str, int] = {}
        for item in recv_items:
            recv_total_map[item["code_name"]] = recv_total_map.get(item["code_name"], 0) + item["total"]

        # Determine types
        hubs = ["Storage Depot", "Seaport"]
        is_recv_hub = any(h in recv_snap["struct_type"] for h in hubs)
        is_ship_hub = any(h in ship_snap["struct_type"] for h in hubs) if ship_snap else False

        # Use dynamic defaults if not provided
        if min_multiplier is None:
            actual_multiplier = 4.0 if is_recv_hub else 1.0
        else:
            actual_multiplier = min_multiplier

        warning = ""
        if ship_snap and not is_ship_hub:
            warning = f"⚠️ **Warning**: `{shipping_hub}` is a `{ship_snap['struct_type']}`, not a Hub.\n"

        comparison_data = []
        handled_codenames = set()

        # Process Priority Items
        for p in priority_list:
            codename = p["codename"]
            handled_codenames.add(codename)

            qty_per_crate = p["qty_per_crate"] or 1
            base_min_crates = p["min_for_base_crates"] or 0
            target_min_crates = base_min_crates * actual_multiplier

            held_crates = recv_total_map.get(codename, 0) / qty_per_crate
            lacking_crates = target_min_crates - held_crates

            if lacking_crates > 0:
                avail_crates = ship_total_map.get(codename, 0) / qty_per_crate
                comparison_data.append({"Item": p["name"], "Avail": avail_crates, "Need": lacking_crates})

        # Process Non-Priority Items
        item_details_map = {i["code_name"]: i for i in ship_items + recv_items}
        all_inventory_codenames = set(recv_total_map.keys()) | set(ship_total_map.keys())
        non_priority_codenames = all_inventory_codenames - handled_codenames

        codename_to_name = {i["code_name"]: i["item_name"] for i in ship_items + recv_items}

        for codename in sorted(non_priority_codenames, key=lambda c: codename_to_name.get(c, c)):
            ship_total = ship_total_map.get(codename, 0)
            item_ref = item_details_map.get(codename)
            qty_crates = self.get_qty_crates(
                ship_total,
                item_ref.get("catalog_qpc") if item_ref else None,
                item_ref.get("per_crate") if item_ref else None,
            )

            comparison_data.append({"Item": codename_to_name.get(codename, codename), "Avail": qty_crates, "Need": 0})

        return {
            "comparison_data": comparison_data,
            "actual_multiplier": actual_multiplier,
            "warning": warning,
            "ship_snap": ship_snap,
            "recv_snap": recv_snap,
        }

    async def locate_item(self, guild_id: int, item: str, from_town: str):
        """Locates an item and calculates distances from a reference town."""
        ref_town = await self.repo.get_town_data(from_town)
        if not ref_town:
            raise ValueError(f"Town `{from_town}` not found.")

        results = await self.repo.search_item_across_stockpiles(guild_id, item)
        if not results:
            return None, ref_town

        processed_results = []
        for r in results:
            dist = calculate_distance(ref_town, r)
            qty_crates = self.get_qty_crates(r["total"], r.get("catalog_qpc"), r.get("per_crate"))

            processed_results.append(
                {
                    "Town": r["town"],
                    "Stockpile": r["stockpile_name"],
                    "Type": r["struct_type"],
                    "Qty": qty_crates,
                    "Dist": dist,
                    "captured_at": r.get("captured_at"),
                }
            )

        processed_results.sort(key=lambda x: x["Dist"])
        return processed_results, ref_town
