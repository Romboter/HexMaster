import time
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

    @app_commands.command(name="upload", description="Upload a stockpile screenshot for processing")
    @app_commands.describe(image="Stockpile screenshot", town="Town name",
                           stockpile_name="Optional specific stockpile name")
    async def upload(
            self,
            interaction: discord.Interaction,
            image: discord.Attachment,  # ✅ moved up
            town: str,  # ✅ moved down
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

    @upload.autocomplete("town")
    async def upload_town_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        # if len(current.strip()) < 3:
        #     return []
        return await self._get_cached_town_choices(current, "all_towns", self.repo.get_all_towns)

    @app_commands.command(name="stockpile", description="View the latest items for a specific town")
    @app_commands.describe(town="Town name", stockpile="Optional specific stockpile filter")
    async def view_stockpile(self, interaction: discord.Interaction, town: str, stockpile: str | None = None) -> None:
        town = (town or "").strip()
        if not town:
            return await interaction.response.send_message("Town is required.", ephemeral=True)

        rows = await self.repo.get_latest_inventory(town, stockpile)
        if not rows:
            return await interaction.response.send_message(f"No snapshots found for `{town}`.", ephemeral=False)

        df = pd.DataFrame(rows)
        df['is_crated'] = df['is_crated'].map({True: 'Y', False: 'N'})
        cols = ['item_name', 'quantity', 'is_crated']
        headers = ["Item", "Qty", "Crate"]

        def get_table(data_frame):
            return tabulate(data_frame, headers=headers, showindex=False, tablefmt="simple")

        df_select = df[cols]
        lines = get_table(df_select)

        # Discord message limit handling
        n_rows = len(df.index)
        while len(lines) > DISCORD_CHARACTER_LIMIT - 150:
            n_rows -= 1
            lines = get_table(df_select.head(n_rows)) + "\n... (truncated)"

        title = f"**{town} Inventory**" + (f" (Filter: {stockpile})" if stockpile else "")
        await interaction.response.send_message(f"{title}\n```\n{lines}\n```", ephemeral=False)

    @view_stockpile.autocomplete("town")
    async def stockpile_town_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
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


    @app_commands.command(name="compare", description="Compare shipping hub to receiving hub or base")
    @app_commands.describe(
        shipping_hub="The hub with available supplies",
        receiving="The hub or base that needs supplies",
        min_multiplier="Multiplier for hub minimums (default 4)"
    )
    async def compare(
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
            hubs = ["Storage Warehouse", "Seaport"]
            is_recv_hub = any(h in recv_snap["struct_type"] for h in hubs)
            is_ship_hub = any(h in ship_snap["struct_type"] for h in hubs) if ship_snap else False

            warning = ""
            if ship_snap and not is_ship_hub:
                warning = f"⚠️ **Warning**: `{shipping_hub}` is a `{ship_snap['struct_type']}`, not a Hub (Storage Warehouse/Seaport).\n"

            comparison_data = []
            for p in priority_list:
                codename = p["codename"]
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
                        "Need": f"{lacking_crates:g}", # :g removes trailing .0 or unnecessary decimals
                        "Avail": f"{avail_crates:g}"
                    })

            if not comparison_data:
                return await interaction.followup.send(f"{warning}✅ `{receiving}` meets all priority minimums!")

            # 4. Format table
            headers = ["Item", "Need", "Avail"]
            table_rows = [[d["Item"], d["Need"], d["Avail"]] for d in comparison_data]
            
            def render_table(rows):
                return tabulate(rows, headers=headers, tablefmt="simple")

            lines = render_table(table_rows)
            
            # Truncate if too long
            if len(lines) > DISCORD_CHARACTER_LIMIT - 300:
                current_rows = table_rows
                while len(render_table(current_rows)) > DISCORD_CHARACTER_LIMIT - 300:
                    current_rows = current_rows[:-1]
                lines = render_table(current_rows) + "\n... (truncated)"

            title = f"**Comparison: {shipping_hub} ➔ {receiving}**"
            mode_str = f"Mode: {'Hub' if is_recv_hub else 'Base'} ({min_multiplier}x Multiplier)"
            msg = f"{warning}{title}\n{mode_str}\n```\n{lines}\n```"
            await interaction.followup.send(msg)

        except Exception as e:
            await interaction.followup.send(f"❌ **Error during comparison:** {str(e)}")

    @compare.autocomplete("shipping_hub")
    async def compare_ship_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "hub_towns", self.repo.get_towns_with_hub_snapshots)

    @compare.autocomplete("receiving")
    async def compare_recv_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "snapshot_towns", self.repo.get_towns_with_snapshots)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StockpileCog(bot))
