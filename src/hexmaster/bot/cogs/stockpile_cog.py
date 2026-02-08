import time
import math
import discord
import inspect
import asyncio
import datetime
from discord import app_commands
from discord.ext import commands
from tabulate import tabulate

from hexmaster.services.stockpile_service import StockpileService
from hexmaster.utils.datetime_utils import get_age_str
from hexmaster.utils.discord_utils import (
    render_and_truncate_table,
    send_success,
    send_error
)


class StockpileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Core data access
        self.repo = getattr(bot, "repo")
        
        # Initialize business service
        self.service = StockpileService(
            repo=self.repo,
            ocr_service=getattr(bot, "ocr_service"),
            war_service=getattr(bot, "war_service", None)
        )
        
        self.war_service = self.service.war_service
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
        """Helper to handle caching and filtering for town autocomplete."""
        now = time.time()
        try:
            if cache_key in self._autocomplete_cache:
                timestamp, cached_towns = self._autocomplete_cache[cache_key]
                if now - timestamp < 60:
                    towns = cached_towns
                else:
                    towns = await (fetch_func() if inspect.iscoroutinefunction(fetch_func) else asyncio.to_thread(fetch_func))
                    self._autocomplete_cache[cache_key] = (now, towns)
            else:
                towns = await (fetch_func() if inspect.iscoroutinefunction(fetch_func) else asyncio.to_thread(fetch_func))
                self._autocomplete_cache[cache_key] = (now, towns)

            search = current.lower().strip()
            choices = []

            for town in towns:
                if not town: continue
                town_name = str(town)
                if not search or search in town_name.lower():
                    choices.append(app_commands.Choice(name=town_name[:100], value=town_name[:100]))
                if len(choices) >= 25: break
            return choices
        except Exception as e:
            print(f"Autocomplete error for {cache_key}: {e}")
            return []

    async def _get_cached_choices(self, current: str, cache_key: str, fetch_func, *args) -> list[app_commands.Choice[str]]:
        """Helper to handle caching and filtering for general autocomplete."""
        now = time.time()
        # Decorate cache key with args if any
        full_cache_key = f"{cache_key}:{':'.join(map(str, args))}" if args else cache_key
        
        try:
            if full_cache_key in self._autocomplete_cache:
                timestamp, cached_items = self._autocomplete_cache[full_cache_key]
                if now - timestamp < 30: # Shorter cache for town-specific items
                    items = cached_items
                else:
                    items = await (fetch_func(*args) if inspect.iscoroutinefunction(fetch_func) else asyncio.to_thread(fetch_func, *args))
                    self._autocomplete_cache[full_cache_key] = (now, items)
            else:
                items = await (fetch_func(*args) if inspect.iscoroutinefunction(fetch_func) else asyncio.to_thread(fetch_func, *args))
                self._autocomplete_cache[full_cache_key] = (now, items)

            search = current.lower().strip()
            choices = []

            for item in items:
                if not item: continue
                item_name = str(item)
                if not search or search in item_name.lower():
                    choices.append(app_commands.Choice(name=item_name[:100], value=item_name[:100]))
                if len(choices) >= 25: break
            return choices
        except Exception as e:
            print(f"Autocomplete error for {full_cache_key}: {e}")
            return []

    @app_commands.command(name="report", description="File an Intelligence Report (upload screenshot)")
    @app_commands.describe(image="Stockpile screenshot", town="Town name", stockpile_name="Optional specific stockpile name")
    async def report(self, interaction: discord.Interaction, image: discord.Attachment, town: str, stockpile_name: str = "Public") -> None:
        if not image.content_type or not image.content_type.startswith("image/"):
            return await send_error(interaction, "Please upload a valid image file.")

        await interaction.response.defer(ephemeral=True)
        try:
            image_bytes = await image.read()
            war_number = await self.war_service.get_current_war_number() if self.war_service else None

            snapshot_id, count, struct_type = await self.service.process_remote_and_ingest(
                image_bytes, town, stockpile_name, war_number
            )
            await send_success(
                interaction, 
                f"Imported {count} items for `{stockpile_name}` ({struct_type}) in `{town}`.\nSnapshot ID: `{snapshot_id}`"
            )
        except Exception as e:
            await send_error(interaction, f"Error during upload: {str(e)}")

    @report.autocomplete("town")
    async def report_town_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "all_towns", self.repo.get_all_towns)

    @app_commands.command(name="inventory", description="View the Inventory for a specific town")
    @app_commands.describe(town="Town name", struct_type="Specific structure type", stockpile="Specific stockpile name")
    async def view_inventory(self, interaction: discord.Interaction, town: str, struct_type: str, stockpile: str) -> None:
        town_input = (town or "").strip()
        if not town_input:
            return await send_error(interaction, "Town is required.")

        rows = await self.repo.get_latest_inventory(town_input, struct_type, stockpile)
        if not rows:
            filter_msg = f" (filtered by `{struct_type}`/`{stockpile}`)" if struct_type or stockpile else ""
            return await send_error(interaction, f"No snapshots found for `{town_input}`{filter_msg}.")

        priority_list = await self.repo.get_priority_list()
        priority_map = {p["codename"]: p for p in priority_list}

        table_rows = []
        row_colors = []
        for r in rows:
            qty_crates = self.service.get_qty_crates(r["total"], r.get("catalog_qpc"), r.get("per_crate"))
            
            p_data = priority_map.get(r["code_name"])
            min_val = 0
            color = "" # Default
            
            if p_data:
                min_val = p_data.get("min_for_base_crates") or 0
                if qty_crates < min_val:
                    color = "31" # Red
                else:
                    color = "32" # Green

            crated_tag = "(Cr)" if r["is_crated"] else "(itm)"
            table_rows.append([
                f"{r['item_name']} {crated_tag}", 
                f"{round(qty_crates, 1):g}",
                f"{round(min_val, 1):g}" if min_val > 0 else "-"
            ])
            row_colors.append(color)

        pretty_name = rows[0].get("pretty_town") or town_input.title()
        war_num = rows[0].get("war_number")
        
        past_war_warning = ""
        if self.war_service:
            current_war = await self.war_service.get_current_war_number()
            if war_num and current_war and war_num < current_war:
                past_war_warning = f"\n⚠️ **Warning: Data from past war (War {war_num})**"

        oldest_snapshot = min(r["captured_at"] for r in rows if r.get("captured_at"))
        age_str = get_age_str(oldest_snapshot)
        
        title = f"{pretty_name} ({age_str})"
        if war_num and not past_war_warning: title += f" (War {war_num})"
        if stockpile: title += f" (Filter: {stockpile})"
        if past_war_warning: title += past_war_warning

        await render_and_truncate_table(
            interaction, 
            table_rows, 
            ["Item", "Qty", "Min"], 
            title, 
            as_embed=True,
            row_colors=row_colors
        )

    @view_inventory.autocomplete("town")
    async def inventory_town_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "snapshot_towns", self.repo.get_towns_with_snapshots)

    @view_inventory.autocomplete("struct_type")
    async def inventory_struct_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        town = interaction.namespace.town
        if not town: return []
        return await self._get_cached_choices(current, "struct_types", self.repo.get_struct_types_for_town, town)

    @view_inventory.autocomplete("stockpile")
    async def inventory_stockpile_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        town = interaction.namespace.town
        struct = interaction.namespace.struct_type
        if not town: return []
        return await self._get_cached_choices(current, "stockpile_names", self.repo.get_stockpile_names_for_town, town, struct)

    @app_commands.command(name="requisition", description="Requisition Order")
    @app_commands.describe(
        shipping_hub="The shipping hub", 
        ship_struct="Specific shipping structure",
        ship_stockpile="Specific shipping stockpile",
        receiving="The receiving hub/base", 
        recv_struct="Specific receiving structure",
        recv_stockpile="Specific receiving stockpile",
        min_multiplier="Target Multiplier"
    )
    async def requisition(
        self, 
        interaction: discord.Interaction, 
        shipping_hub: str, 
        ship_struct: str,
        ship_stockpile: str,
        receiving: str, 
        recv_struct: str,
        recv_stockpile: str,
        min_multiplier: float | None = None
    ) -> None:

        await interaction.response.defer(ephemeral=True)

        try:
            result = await self.service.get_requisition_comparison(
                shipping_hub, 
                receiving, 
                min_multiplier,
                ship_struct,
                ship_stockpile,
                recv_struct,
                recv_stockpile
            )
            
            comparison_data = result["comparison_data"]
            if not comparison_data:
                msg = f"✅ `{receiving}` meets all priority minimums!"
                if result.get("warning"): msg = f"{result['warning']}\n{msg}"
                return await send_success(interaction, msg, title="Requisition Order Complete")

            table_rows = []
            row_colors = []
            for d in comparison_data:
                table_rows.append([d["Item"], f"{round(d['Avail'], 1):g}", f"{round(d['Need'], 1):g}"])
                if d["Avail"] <= 0:
                    row_colors.append("31") # Red (None avail)
                elif d["Avail"] < d["Need"]:
                    row_colors.append("33") # Yellow (Some avail but not enough)
                else:
                    row_colors.append("32") # Green (Enough avail)
            
            ship_snap, recv_snap = result["ship_snap"], result["recv_snap"]
            ship_p = ship_snap["pretty_town"] if ship_snap and ship_snap.get("pretty_town") else shipping_hub.title()
            recv_p = recv_snap["pretty_town"] if recv_snap and recv_snap.get("pretty_town") else receiving.title()
            
            ship_age = f" ({get_age_str(ship_snap['captured_at'])})" if ship_snap else ""
            recv_age = f" ({get_age_str(recv_snap['captured_at'])})" if recv_snap else ""

            # Enhance title with filters
            filter_info = ""
            if any([ship_struct, ship_stockpile, recv_struct, recv_stockpile]):
                filters = []
                if ship_struct or ship_stockpile: filters.append(f"Ship: {ship_struct or ''} {ship_stockpile or ''}")
                if recv_struct or recv_stockpile: filters.append(f"Recv: {recv_struct or ''} {recv_stockpile or ''}")
                filter_info = f"\nFilters: { ' | '.join(filters) }"

            title = f"{ship_p}{ship_age} ➔ {recv_p}{recv_age} ({result['actual_multiplier']:g}x)"
            if filter_info: title += f"\n{filter_info}"
            
            await render_and_truncate_table(
                interaction, 
                table_rows, 
                ["Item", "Avail", "Need"], 
                title, 
                as_embed=True,
                row_colors=row_colors
            )

        except Exception as e:
            await send_error(interaction, f"Error during comparison: {str(e)}")

    @requisition.autocomplete("shipping_hub")
    async def requisition_ship_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "hub_towns", self.repo.get_towns_with_hub_snapshots)

    @requisition.autocomplete("ship_struct")
    async def requisition_ship_struct_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        town = interaction.namespace.shipping_hub
        if not town: return []
        return await self._get_cached_choices(current, "struct_types", self.repo.get_struct_types_for_town, town)

    @requisition.autocomplete("ship_stockpile")
    async def requisition_ship_stockpile_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        town = interaction.namespace.shipping_hub
        struct = interaction.namespace.ship_struct
        if not town: return []
        return await self._get_cached_choices(current, "stockpile_names", self.repo.get_stockpile_names_for_town, town, struct)

    @requisition.autocomplete("receiving")
    async def requisition_recv_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "snapshot_towns", self.repo.get_towns_with_snapshots)

    @requisition.autocomplete("recv_struct")
    async def requisition_recv_struct_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        town = interaction.namespace.receiving
        if not town: return []
        return await self._get_cached_choices(current, "struct_types", self.repo.get_struct_types_for_town, town)

    @requisition.autocomplete("recv_stockpile")
    async def requisition_recv_stockpile_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        town = interaction.namespace.receiving
        struct = interaction.namespace.recv_struct
        if not town: return []
        return await self._get_cached_choices(current, "stockpile_names", self.repo.get_stockpile_names_for_town, town, struct)

    @app_commands.command(name="locate", description="Locate an item")
    @app_commands.describe(item="Item name", from_town="Requesting town")
    async def locate(self, interaction: discord.Interaction, item: str, from_town: str) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            results, ref_town = await self.service.locate_item(item, from_town)
            if not results:
                return await send_error(interaction, f"`{item}` is not in any stockpile.")

            table_rows = [
                [d["Town"], d["Stockpile"], d["Type"], f"{round(d['Qty'], 1):g}", f"{d['Dist']:.1f}", get_age_str(d["captured_at"])] 
                for d in results
            ]

            title = f"Available Stockpiles for {item}"
            if ref_town and ref_town.get("name"):
                title += f" (Ref: {ref_town['name']})"
                
            await render_and_truncate_table(
                interaction, 
                table_rows, 
                ["Town", "Stockpile", "Type", "Qty", "Dist", "Age"], 
                title,
                as_embed=True
            )

        except Exception as e:
            await send_error(interaction, f"Error during search: {str(e)}")

    @locate.autocomplete("item")
    async def locate_item_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "stockpile_items", self.repo.get_items_in_stockpiles)

    @locate.autocomplete("from_town")
    async def locate_town_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "all_towns", self.repo.get_all_towns)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StockpileCog(bot))
