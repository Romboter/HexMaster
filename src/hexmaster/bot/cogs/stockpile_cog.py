import time
import math
import pandas as pd
import discord
import inspect
import asyncio
from discord import app_commands
from discord.ext import commands
from tabulate import tabulate

from hexmaster.services.ocr_service import OCRService
from hexmaster.db.repositories.stockpile_repository import StockpileRepository

DISCORD_CHARACTER_LIMIT = 2000


class StockpileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Grab global services from the bot instance
        self.ocr_service: OCRService = getattr(bot, "ocr_service")
        self.repo: StockpileRepository = getattr(bot, "repo")
        self.settings = getattr(bot, "settings")

        # Cache for autocomplete results (cache_key -> (timestamp, list_of_strings))
        self._autocomplete_cache: dict[str, tuple[float, list[str]]] = {}

    async def cog_load(self) -> None:
        """Called when the cog is loaded. Pre-fills the town cache immediately."""
        try:
            # Trigger a cache fill with an empty search string
            await self._get_cached_town_choices("", "all_towns", self.repo.get_all_towns)
            print("✅ Town autocomplete cache warmed (853 entries).")
        except Exception as e:
            print(f"⚠️ Failed to warm autocomplete cache: {e}")

    async def _get_cached_town_choices(self, current: str, cache_key: str, fetch_func) -> list[
        app_commands.Choice[str]]:
        """Helper to handle caching and filtering for town autocomplete.

        Supports both async and sync fetch_func implementations.
        """
        now = time.time()
        try:
            # Refresh cache if missing or older than 60 seconds
            if cache_key in self._autocomplete_cache:
                timestamp, cached_towns = self._autocomplete_cache[cache_key]
                if now - timestamp < 60:
                    towns = cached_towns
                else:
                    if inspect.iscoroutinefunction(fetch_func):
                        towns = await fetch_func()
                    else:
                        towns = await asyncio.to_thread(fetch_func)
                    self._autocomplete_cache[cache_key] = (now, towns)
            else:
                if inspect.iscoroutinefunction(fetch_func):
                    towns = await fetch_func()
                else:
                    towns = await asyncio.to_thread(fetch_func)
                self._autocomplete_cache[cache_key] = (now, towns)

            search = current.lower().strip()
            choices = []

            for town in towns:
                if not town:
                    continue

                town_name = str(town)
                # Match partial string (case-insensitive)
                if not search or search in town_name.lower():
                    # Discord limits: name/value max 100 chars, total 25 choices
                    choices.append(app_commands.Choice(name=town_name[:100], value=town_name[:100]))

                if len(choices) >= 25:
                    break
            return choices
        except Exception as e:
            print(f"Autocomplete error for {cache_key}: {e}")
            return []

    @app_commands.command(name="report", description="File an Intelligence Report (upload screenshot)")
    @app_commands.describe(image="Stockpile screenshot", town="Town name",
                           stockpile_name="Optional specific stockpile name")
    async def report(
            self,
            interaction: discord.Interaction,
            image: discord.Attachment,
            town: str,
            stockpile_name: str = "Public"
    ) -> None:
        """Handles the file upload and kicks off the OCR/Ingestion pipeline."""
        if not image.content_type or not image.content_type.startswith("image/"):
            return await interaction.response.send_message("Please upload a valid image file.", ephemeral=True)

        await interaction.response.defer(ephemeral=False)
        try:
            image_bytes = await image.read()
            snapshot_id, count, struct_type = await self.process_remote_and_ingest(
                image_bytes, town, stockpile_name
            )
            await interaction.followup.send(
                f"✅ **Success!** Imported {count} items for `{stockpile_name}` ({struct_type}) in `{town}`.\n"
                f"Snapshot ID: `{snapshot_id}`"
            )
        except Exception as e:
            await interaction.followup.send(f"❌ **Error during upload:** {str(e)}")

    @report.autocomplete("town")
    async def report_town_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        # if len(current.strip()) < 3:
        #     return []
        return await self._get_cached_town_choices(current, "all_towns", self.repo.get_all_towns)

    @app_commands.command(name="manifest", description="View the Shipping Manifest for a specific town")
    @app_commands.describe(town="Town name", stockpile="Optional specific stockpile filter")
    async def view_manifest(self, interaction: discord.Interaction, town: str, stockpile: str | None = None) -> None:
        town_input = (town or "").strip()
        if not town_input:
            return await interaction.response.send_message("Town is required.", ephemeral=True)

        rows = await self.repo.get_latest_inventory(town_input, stockpile)
        if not rows:
            return await interaction.response.send_message(f"No snapshots found for `{town_input}`.", ephemeral=False)

        # Process data into table rows
        table_rows = []
        for r in rows:
            # Qty in crates
            qpc = r["catalog_qpc"] if r["catalog_qpc"] else (r["per_crate"] if r["per_crate"] else 1)
            qty_crates = r["total"] / qpc
            table_rows.append([r["item_name"], f"{qty_crates:g}"])

        headers = ["Item", "Qty(Cr)"]

        def get_table(data_list):
            return tabulate(data_list, headers=headers, showindex=False, tablefmt="simple")

        # Discord message limit handling
        max_rows = 40
        display_rows = table_rows[:max_rows]
        lines = get_table(display_rows)
        
        if len(table_rows) > max_rows:
            hidden_count = len(table_rows) - max_rows
            lines += f"\n... (+ {hidden_count} items hidden)"

        # Standardized header using pretty town name from DB
        pretty_name = rows[0].get("pretty_town") or town_input.title()
        title = f"**{pretty_name}**"
        if stockpile:
            title += f" (Filter: {stockpile})"
            
        await interaction.response.send_message(f"{title}\n```\n{lines}\n```", ephemeral=False)

    @view_manifest.autocomplete("town")
    async def manifest_town_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "snapshot_towns", self.repo.get_towns_with_snapshots)

    async def process_remote_and_ingest(self, image_bytes: bytes, town: str, stockpile_name: str):
        """Coordinates the OCR process and database ingestion."""
        try:
            df = await self.ocr_service.process_image(image_bytes, town, stockpile_name)
        except Exception as e:
            raise RuntimeError(f"OCR Server Error: {e}")

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
            cname, iname = str(r.get("CodeName", "")).strip(), str(r.get("Name", "")).strip()
            if (cname, iname) in valid_keys:
                items.append({
                    "code_name": cname,
                    "item_name": iname,
                    "quantity": int(r["Quantity"]) if pd.notna(r.get("Quantity")) else 0,
                    "is_crated": str(r.get("Crated?", "")).upper() in ("TRUE", "YES", "T", "Y"),
                    "per_crate": int(r["Per Crate"]) if pd.notna(r.get("Per Crate")) else 0,
                    "total": int(r["Total"]) if pd.notna(r.get("Total")) else 0,
                    "description": str(r.get("Description", "")).strip()
                })

        snapshot_id = await self.repo.ingest_snapshot(town, struct_type, stockpile_name, items)
        return snapshot_id, len(items), struct_type


    @app_commands.command(name="requisition", description="Calculate Requisition Order (compare hubs)")
    @app_commands.describe(
        shipping_hub="The hub with available supplies",
        receiving="The hub or base that needs supplies",
        min_multiplier="Multiplier for hub minimums (default 4)"
    )
    async def requisition(
            self,
            interaction: discord.Interaction,
            shipping_hub: str,
            receiving: str,
            min_multiplier: float = 4.0
    ) -> None:
        await interaction.response.defer(ephemeral=False)

        try:
            # 1. Fetch data
            priority_list = await self.repo.get_priority_list()
            if not priority_list:
                return await interaction.followup.send("❌ Priority list is empty. Please seed the database.")

            ship_snap, ship_items = await self.repo.get_latest_snapshot_for_town(shipping_hub)
            recv_snap, recv_items = await self.repo.get_latest_snapshot_for_town(receiving)

            if not recv_snap:
                return await interaction.followup.send(f"❌ No snapshots found for receiving town `{receiving}`.")

            # 2. Process inventories into total quantities by code_name
            # Sum up all 'total' counts for each item (handling both crated and loose)
            ship_total_map = {}
            for item in ship_items:
                ship_total_map[item["code_name"]] = ship_total_map.get(item["code_name"], 0) + item["total"]

            recv_total_map = {}
            for item in recv_items:
                recv_total_map[item["code_name"]] = recv_total_map.get(item["code_name"], 0) + item["total"]

            # 3. Determine types
            hubs = ["Storage Warehouse", "Storage Depot", "Seaport"]
            is_recv_hub = any(h in recv_snap["struct_type"] for h in hubs)
            is_ship_hub = any(h in ship_snap["struct_type"] for h in hubs) if ship_snap else False

            warning = ""
            if ship_snap and not is_ship_hub:
                warning = f"⚠️ **Warning**: `{shipping_hub}` is a `{ship_snap['struct_type']}`, not a Hub (Storage Warehouse/Seaport).\n"

            comparison_data = []
            handled_codenames = set()

            # 4. Process Priority Items
            for p in priority_list:
                codename = p["codename"]
                handled_codenames.add(codename)
                
                qty_per_crate = p["qty_per_crate"] or 1
                base_min_crates = p["min_for_base_crates"] or 0
                target_min_crates = base_min_crates * (min_multiplier if is_recv_hub else 1.0)

                # Total held at receiving, converted to crates
                recv_total_items = recv_total_map.get(codename, 0)
                held_crates = recv_total_items / qty_per_crate
                
                lacking_crates = target_min_crates - held_crates

                if lacking_crates > 0:
                    # Total available at shipping hub, converted to crates
                    ship_total_items = ship_total_map.get(codename, 0)
                    avail_crates = ship_total_items / qty_per_crate
                    
                    comparison_data.append({
                        "Item": p["name"],
                        "Avail": f"{round(avail_crates, 1):g}",
                        "Need": f"{round(lacking_crates, 1):g}"
                    })

            # 5. Process Non-Priority Items (Items in inventories but not on the list)
            # Create a quick lookup map for item details O(1)
            item_details_map = {
                i["code_name"]: i 
                for i in ship_items + recv_items
            }

            all_inventory_codenames = set(recv_total_map.keys()) | set(ship_total_map.keys())
            non_priority_codenames = all_inventory_codenames - handled_codenames

            # We need the display names for these codenames. 
            codename_to_name = {
                i["code_name"]: i["item_name"]
                for i in ship_items + recv_items
            }

            # Sort non-priority items alphabetically for consistency
            for codename in sorted(non_priority_codenames, key=lambda c: codename_to_name.get(c, c)):
                ship_total = ship_total_map.get(codename, 0)
                # Instant O(1) lookup
                item_ref = item_details_map.get(codename)
                qpc = item_ref["catalog_qpc"] if item_ref and item_ref["catalog_qpc"] else (item_ref["per_crate"] if item_ref and item_ref["per_crate"] else 1)
                
                avail_crates = ship_total / qpc
                
                comparison_data.append({
                    "Item": codename_to_name.get(codename, codename),
                    "Avail": f"{round(avail_crates, 1):g}",
                    "Need": "0"  # No defined minimum requirement
                })

            if not comparison_data:
                return await interaction.followup.send(f"{warning}✅ `{receiving}` meets all priority minimums!")

            # 6. Format table
            headers = ["Item", "Avail", "Need"]
            table_rows = [[d["Item"], d["Avail"], d["Need"]] for d in comparison_data]
            
            def render_table(rows):
                return tabulate(rows, headers=headers, tablefmt="simple")

            lines = render_table(table_rows)
            
            # Truncate if too long
            if len(lines) > DISCORD_CHARACTER_LIMIT - 300:
                current_rows = table_rows
                while len(render_table(current_rows)) > DISCORD_CHARACTER_LIMIT - 300:
                    current_rows = current_rows[:-1]
                hidden_count = len(table_rows) - len(current_rows)
                lines = render_table(current_rows) + f"\n... (+ {hidden_count} items hidden)"

            ship_p = ship_snap["pretty_town"] if ship_snap and ship_snap.get("pretty_town") else shipping_hub.title()
            recv_p = recv_snap["pretty_town"] if recv_snap and recv_snap.get("pretty_town") else receiving.title()

            title = f"**{ship_p} ➔ {recv_p} ({min_multiplier if is_recv_hub else 1.0:g}x)**"
            msg = f"{warning}{title}\n```\n{lines}\n```"
            await interaction.followup.send(msg)

        except Exception as e:
            await interaction.followup.send(f"❌ **Error during comparison:** {str(e)}")

    @requisition.autocomplete("shipping_hub")
    async def requisition_ship_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "hub_towns", self.repo.get_towns_with_hub_snapshots)

    @requisition.autocomplete("receiving")
    async def requisition_recv_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "snapshot_towns", self.repo.get_towns_with_snapshots)

    @app_commands.command(name="locate", description="Perform Reconnaissance (locate assets globally)")
    @app_commands.describe(
        item="The item to search for",
        from_town="Reference town for distance calculation"
    )
    async def locate(self, interaction: discord.Interaction, item: str, from_town: str) -> None:
        await interaction.response.defer(ephemeral=False)

        try:
            # 1. Fetch town and item data
            ref_town = await self.repo.get_town_data(from_town)
            if not ref_town:
                return await interaction.followup.send(f"❌ Reference town `{from_town}` not found.")

            results = await self.repo.search_item_across_stockpiles(item)
            if not results:
                return await interaction.followup.send(f"❌ `{item}` is not in any stockpile.")

            # 2. Calculate distances and format data
            processed_results = []
            for r in results:
                town_name = r["town"]
                
                dist = 0.0
                if r["q"] is not None and r["r"] is not None:
                    # Cartesian-Staggered Distance Formula
                    # q, r are the staggered axial-like centers
                    # SQRT3 ~= 1.73205
                    SQRT3 = 1.73205
                    x2 = r["q"] * 1.5 + (r["x"] - 0.5) * 2.0
                    y2 = r["r"] * SQRT3 + (r["y"] - 0.5) * SQRT3
                    
                    x1 = ref_town["q"] * 1.5 + (ref_town["x"] - 0.5) * 2.0
                    y1 = ref_town["r"] * SQRT3 + (ref_town["y"] - 0.5) * SQRT3
                    
                    dist = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                
                # Qty in crates
                # Prioritize canonical catalog qpc, then snapshot metadata, then 1
                qpc = r["catalog_qpc"] if r["catalog_qpc"] else (r["per_crate"] if r["per_crate"] else 1)
                qty_crates = r["total"] / qpc

                processed_results.append({
                    "Town": town_name,
                    "Stockpile": r["stockpile_name"],
                    "Type": r["struct_type"],
                    "Qty": f"{qty_crates:g}",
                    "Dist": dist
                })

            # Sort by distance
            processed_results.sort(key=lambda x: x["Dist"])

            # 3. Format table
            headers = ["Town", "Stockpile", "Type", "Qty(Cr)", "Dist"]
            table_rows = [[d["Town"], d["Stockpile"], d["Type"], d["Qty"], f"{d['Dist']:.1f}"] for d in processed_results]

            def render_table(rows):
                return tabulate(rows, headers=headers, tablefmt="simple")

            lines = render_table(table_rows)

            # character limit handling
            if len(lines) > DISCORD_CHARACTER_LIMIT - 300:
                current_rows = table_rows
                while len(render_table(current_rows)) > DISCORD_CHARACTER_LIMIT - 300:
                    current_rows = current_rows[:-1]
                hidden_count = len(table_rows) - len(current_rows)
                lines = render_table(current_rows) + f"\n... (+ {hidden_count} findings hidden)"

            title = f"**Findings for `{item}`**"
            if ref_town and ref_town.get("name"):
                title += f" (Referenced from `{ref_town['name']}`)"
                
            await interaction.followup.send(f"{title}\n```\n{lines}\n```")

        except Exception as e:
            await interaction.followup.send(f"❌ **Error during search:** {str(e)}")

    @locate.autocomplete("item")
    async def locate_item_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "stockpile_items", self.repo.get_items_in_stockpiles)

    @locate.autocomplete("from_town")
    async def locate_town_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        # Use all valid towns for reference, not just ones with snapshots
        return await self._get_cached_town_choices(current, "all_towns", self.repo.get_all_towns)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StockpileCog(bot))
