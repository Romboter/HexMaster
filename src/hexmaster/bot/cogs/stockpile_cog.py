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

DISCORD_CHARACTER_LIMIT = 2000


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

    async def _render_and_truncate_table(
            self,
            interaction: discord.Interaction,
            rows: list[list],
            headers: list[str],
            title: str,
            ephemeral: bool = True
    ) -> None:
        """Renders a table with tabulate and handles Discord character limit truncation."""

        def render(data):
            return tabulate(data, headers=headers, tablefmt="simple")

        lines = render(rows)
        limit = DISCORD_CHARACTER_LIMIT - 300  # Buffer for title and code blocks

        if len(lines) > limit:
            current_rows = rows
            while len(render(current_rows)) > limit and current_rows:
                current_rows = current_rows[:-1]

            hidden_count = len(rows) - len(current_rows)
            lines = render(current_rows) + f"\n(+ {hidden_count} items hidden)"
            
        msg = f"{title}\n```\n{lines}\n```"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(msg, ephemeral=ephemeral)

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

    @app_commands.command(name="report", description="File an Intelligence Report (upload screenshot)")
    @app_commands.describe(image="Stockpile screenshot", town="Town name", stockpile_name="Optional specific stockpile name")
    async def report(self, interaction: discord.Interaction, image: discord.Attachment, town: str, stockpile_name: str = "Public") -> None:
        if not image.content_type or not image.content_type.startswith("image/"):
            return await interaction.response.send_message("Please upload a valid image file.", ephemeral=True)

        await interaction.response.defer(ephemeral=False)
        try:
            image_bytes = await image.read()
            war_number = await self.war_service.get_current_war_number() if self.war_service else None

            snapshot_id, count, struct_type = await self.service.process_remote_and_ingest(
                image_bytes, town, stockpile_name, war_number
            )
            await interaction.followup.send(
                f"✅ **Success!** Imported {count} items for `{stockpile_name}` ({struct_type}) in `{town}`.\n"
                f"Snapshot ID: `{snapshot_id}`"
            )
        except Exception as e:
            await interaction.followup.send(f"❌ **Error during upload:** {str(e)}")

    @report.autocomplete("town")
    async def report_town_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "all_towns", self.repo.get_all_towns)

    @app_commands.command(name="inventory", description="View the Inventory for a specific town")
    @app_commands.describe(town="Town name", stockpile="Optional stockpile name")
    async def view_inventory(self, interaction: discord.Interaction, town: str, stockpile: str | None = None) -> None:
        town_input = (town or "").strip()
        if not town_input:
            return await interaction.response.send_message("Town is required.", ephemeral=True)

        rows = await self.repo.get_latest_inventory(town_input, stockpile)
        if not rows:
            return await interaction.response.send_message(f"No snapshots found for `{town_input}`.", ephemeral=True)

        table_rows = []
        for r in rows:
            qty_crates = self.service.get_qty_crates(r["total"], r.get("catalog_qpc"), r.get("per_crate"))
            status = "(Cr)" if r["is_crated"] else "(itm)"
            table_rows.append([f"{r['item_name']} {status}", f"{round(qty_crates, 1):g}"])

        pretty_name = rows[0].get("pretty_town") or town_input.title()
        war_num = rows[0].get("war_number")
        
        past_war_warning = ""
        if self.war_service:
            current_war = await self.war_service.get_current_war_number()
            if war_num and current_war and war_num < current_war:
                past_war_warning = f"\n⚠️ **Warning: Data from past war (War {war_num})**"

        oldest_snapshot = min(r["captured_at"] for r in rows if r.get("captured_at"))
        age_str = get_age_str(oldest_snapshot)
        
        title = f"**{pretty_name}** ({age_str})"
        if war_num and not past_war_warning: title += f" (War {war_num})"
        if stockpile: title += f" (Filter: {stockpile})"
        if past_war_warning: title += past_war_warning

        await self._render_and_truncate_table(interaction, table_rows, ["Item", "Qty"], title)

    @view_inventory.autocomplete("town")
    async def inventory_town_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "snapshot_towns", self.repo.get_towns_with_snapshots)

    @app_commands.command(name="requisition", description="Requisition Order")
    @app_commands.describe(shipping_hub="The shipping hub", receiving="The receiving hub/base", min_multiplier="Target Multiplier")
    async def requisition(self, interaction: discord.Interaction, shipping_hub: str, receiving: str, min_multiplier: float | None = None) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            result = await self.service.get_requisition_comparison(shipping_hub, receiving, min_multiplier)
            
            comparison_data = result["comparison_data"]
            if not comparison_data:
                return await interaction.followup.send(f"{result['warning']}✅ `{receiving}` meets all priority minimums!")

            table_rows = [[d["Item"], f"{round(d['Avail'], 1):g}", f"{round(d['Need'], 1):g}"] for d in comparison_data]
            
            ship_snap, recv_snap = result["ship_snap"], result["recv_snap"]
            ship_p = ship_snap["pretty_town"] if ship_snap and ship_snap.get("pretty_town") else shipping_hub.title()
            recv_p = recv_snap["pretty_town"] if recv_snap and recv_snap.get("pretty_town") else receiving.title()
            
            ship_age = f" ({get_age_str(ship_snap['captured_at'])})" if ship_snap else ""
            recv_age = f" ({get_age_str(recv_snap['captured_at'])})" if recv_snap else ""

            title = f"{result['warning']}**{ship_p}{ship_age} ➔ {recv_p}{recv_age} ({result['actual_multiplier']:g}x)**"
            await self._render_and_truncate_table(interaction, table_rows, ["Item", "Avail", "Need"], title)

        except Exception as e:
            await interaction.followup.send(f"❌ **Error during comparison:** {str(e)}")

    @requisition.autocomplete("shipping_hub")
    async def requisition_ship_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "hub_towns", self.repo.get_towns_with_hub_snapshots)

    @requisition.autocomplete("receiving")
    async def requisition_recv_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "snapshot_towns", self.repo.get_towns_with_snapshots)

    @app_commands.command(name="locate", description="Locate an item")
    @app_commands.describe(item="Item name", from_town="Requesting town")
    async def locate(self, interaction: discord.Interaction, item: str, from_town: str) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            results, ref_town = await self.service.locate_item(item, from_town)
            if not results:
                return await interaction.followup.send(f"❌ `{item}` is not in any stockpile.")

            table_rows = [
                [d["Town"], d["Stockpile"], d["Type"], f"{round(d['Qty'], 1):g}", f"{d['Dist']:.1f}", get_age_str(d["captured_at"])] 
                for d in results
            ]

            title = f"**Available Stockpiles for `{item}`**"
            if ref_town and ref_town.get("name"):
                title += f" Request from `{ref_town['name']}`"
                
            await self._render_and_truncate_table(interaction, table_rows, ["Town", "Stockpile", "Type", "Qty", "Dist", "Age"], title)

        except Exception as e:
            await interaction.followup.send(f"❌ **Error during search:** {str(e)}")

    @locate.autocomplete("item")
    async def locate_item_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "stockpile_items", self.repo.get_items_in_stockpiles)

    @locate.autocomplete("from_town")
    async def locate_town_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self._get_cached_town_choices(current, "all_towns", self.repo.get_all_towns)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StockpileCog(bot))
