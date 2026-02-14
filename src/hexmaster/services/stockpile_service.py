# Copyright (c) 2024-2025 Gary Kuepper
# Licensed under the MIT License.

import pandas as pd

from hexmaster.utils.geo_utils import calculate_distance


class StockpileService:
    def __init__(self, repo, ocr_service, war_service=None):
        self.repo = repo
        self.ocr_service = ocr_service
        self.war_service = war_service

    def get_qty_crates(
        self, total: float, catalog_qpc: int | None, per_crate: int | None
    ) -> float:
        """Calculates quantity in crates based on available metadata."""
        qpc = catalog_qpc or per_crate or 1
        return total / qpc

    async def process_remote_and_ingest(
        self,
        guild_id: int,
        image_bytes: bytes,
        town: str,
        stockpile_name: str,
        shard: str = "Alpha",
        war_number: int | None = None,
    ):
        """Coordinates the OCR process and database ingestion."""
        try:
            df = await self.ocr_service.process_image(image_bytes, town, stockpile_name)
        except Exception:
            # Let OCRServiceError bubble up to the cog for better formatting
            raise

        if df.empty:
            raise ValueError("OCR returned no data from the image.")

        struct_type = str(df.iloc[0].get("Structure Type", "Unknown")).strip()
        if stockpile_name == "Public":
            sheet_stockpile = str(df.iloc[0].get("Stockpile Name", "")).strip()
            if sheet_stockpile:
                stockpile_name = sheet_stockpile

        valid_keys = await self.repo.get_catalog_items()
        items = []
        for _, r in df.iterrows():
            cname, iname = (
                str(r.get("CodeName", "")).strip(),
                str(r.get("Name", "")).strip(),
            )
            if (cname, iname) in valid_keys:
                items.append(
                    {
                        "code_name": cname,
                        "item_name": iname,
                        "quantity": (
                            int(r["Quantity"]) if pd.notna(r.get("Quantity")) else 0
                        ),
                        "is_crated": str(r.get("Crated?", "")).upper()
                        in ("TRUE", "YES", "T", "Y"),
                        "per_crate": (
                            int(r["Per Crate"]) if pd.notna(r.get("Per Crate")) else 0
                        ),
                        "total": int(r["Total"]) if pd.notna(r.get("Total")) else 0,
                        "description": str(r.get("Description", "")).strip(),
                    }
                )

        snapshot_id = await self.repo.ingest_snapshot(
            guild_id, shard, town, struct_type, stockpile_name, items, war_number
        )
        return snapshot_id, len(items), struct_type

    async def get_requisition_comparison(
        self,
        guild_id: int,
        shipping_hub: str,
        receiving: str,
        shard: str = "Alpha",
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
            guild_id, shard, shipping_hub, ship_struct, ship_stockpile
        )
        recv_snap, recv_items = await self.repo.get_latest_snapshot_for_town_filtered(
            guild_id, shard, receiving, recv_struct, recv_stockpile
        )

        if not recv_snap:
            raise ValueError(f"No snapshots found for receiving town `{receiving}`.")

        # Process inventories into total quantities by (code_name, is_crated)
        ship_total_map: dict[tuple[str, bool], int] = {}
        for item in ship_items:
            key = (item["code_name"], item["is_crated"])
            ship_total_map[key] = ship_total_map.get(key, 0) + item["total"]

        recv_total_map: dict[str, int] = {}
        for item in recv_items:
            recv_total_map[item["code_name"]] = (
                recv_total_map.get(item["code_name"], 0) + item["total"]
            )

        # Determine types
        hubs = ["Storage Depot", "Seaport"]
        is_recv_hub = any(h in recv_snap["struct_type"] for h in hubs)
        is_ship_hub = (
            any(h in ship_snap["struct_type"] for h in hubs) if ship_snap else False
        )

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
                # For priority items, we usually just want to know if we can fill the need.
                # However, we still need to respect the display rules.
                # Since priority items are usually requested in crates, we look for crates first.

                # Check for crates
                avail_crates_crated = (
                    ship_total_map.get((codename, True), 0) / qty_per_crate
                )
                if avail_crates_crated > 0:
                    comparison_data.append(
                        {
                            "Item": p["name"],
                            "Avail": avail_crates_crated,
                            "Need": lacking_crates,
                            "is_crated": True,
                        }
                    )

                # Check for loose items if destination is a HUB
                if is_recv_hub:
                    avail_crates_loose = (
                        ship_total_map.get((codename, False), 0) / qty_per_crate
                    )
                    if avail_crates_loose > 0:
                        comparison_data.append(
                            {
                                "Item": p["name"],
                                "Avail": avail_crates_loose,
                                "Need": lacking_crates,  # Same need, just different source form
                                "is_crated": False,
                            }
                        )

                # If neither found but needed, show 0 avail (defaulting to crate view for priority)
                if avail_crates_crated == 0 and (
                    not is_recv_hub or (is_recv_hub and avail_crates_loose == 0)
                ):
                    comparison_data.append(
                        {
                            "Item": p["name"],
                            "Avail": 0,
                            "Need": lacking_crates,
                            "is_crated": True,
                        }
                    )

        # Process Non-Priority Items
        # Gather all code names present in shipping
        ship_codenames = {k[0] for k in ship_total_map.keys()}
        non_priority_codenames = ship_codenames - handled_codenames

        item_details_map = {i["code_name"]: i for i in ship_items}
        codename_to_name = {i["code_name"]: i["item_name"] for i in ship_items}

        for codename in sorted(
            non_priority_codenames, key=lambda c: codename_to_name.get(c, c)
        ):
            item_ref = item_details_map.get(codename)
            qpc = item_ref.get("catalog_qpc") if item_ref else None
            per_crate = item_ref.get("per_crate") if item_ref else None

            # Check Crated
            ship_total_crated = ship_total_map.get((codename, True), 0)
            if ship_total_crated > 0:
                qty_crates = self.get_qty_crates(ship_total_crated, qpc, per_crate)
                comparison_data.append(
                    {
                        "Item": codename_to_name.get(codename, codename),
                        "Avail": qty_crates,
                        "Need": 0,
                        "is_crated": True,
                    }
                )

            # Check Loose - ONLY if destination is a HUB
            if is_recv_hub:
                ship_total_loose = ship_total_map.get((codename, False), 0)
                if ship_total_loose > 0:
                    qty_crates = self.get_qty_crates(ship_total_loose, qpc, per_crate)
                    comparison_data.append(
                        {
                            "Item": codename_to_name.get(codename, codename),
                            "Avail": qty_crates,
                            "Need": 0,
                            "is_crated": False,
                        }
                    )

        return {
            "comparison_data": comparison_data,
            "actual_multiplier": actual_multiplier,
            "warning": warning,
            "ship_snap": ship_snap,
            "recv_snap": recv_snap,
        }

    async def locate_item(
        self, guild_id: int, item: str, from_town: str, shard: str = "Alpha"
    ):
        """Locates an item and calculates distances from a reference town for a specific shard."""
        ref_town = await self.repo.get_town_data(from_town)
        if not ref_town:
            raise ValueError(f"Town `{from_town}` not found.")

        results = await self.repo.search_item_across_stockpiles(guild_id, item, shard)
        if not results:
            return None, ref_town

        processed_results = []
        for r in results:
            dist = calculate_distance(ref_town, r)
            qty_crates = self.get_qty_crates(
                r["total"], r.get("catalog_qpc"), r.get("per_crate")
            )

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
