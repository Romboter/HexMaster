import time
import pandas as pd
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.ext.asyncio import create_async_engine
from tabulate import tabulate

from hexmaster.config import Settings
from hexmaster.services.ocr_service import OCRService
from hexmaster.db.repositories.stockpile_repository import StockpileRepository

DISCORD_CHARACTER_LIMIT = 2000


class StockpileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # We grab the initialized objects directly from the bot.
        # main.py created these during bot startup.
        self.ocr_service: OCRService = getattr(bot, "ocr_service")
        self.repo: StockpileRepository = getattr(bot, "repo")
        self.settings = getattr(bot, "settings")

        self._autocomplete_cache: dict[str, tuple[float, list[str]]] = {}

    async def process_remote_and_ingest(self, image_bytes: bytes, town: str, stockpile_name: str):
        """
        Coordinates the OCR process and database ingestion.
        """
        try:
            df = await self.ocr_service.process_image(image_bytes, town, stockpile_name)
        except Exception as e:
            raise RuntimeError(f"OCR Server Error: {e}")

        if df.empty:
            raise ValueError("OCR returned no data from the image.")

        struct_type = str(df.iloc[0].get("Structure Type", "Unknown")).strip()

        # If user provided 'Public', check if the OCR detected a more specific name
        if stockpile_name == "Public":
            sheet_stockpile = str(df.iloc[0].get("Stockpile Name", "")).strip()
            if sheet_stockpile:
                stockpile_name = sheet_stockpile

        # Validate detected items against the catalog via the repository
        valid_keys = await self.repo.get_catalog_items()

        items = []
        for _, r in df.iterrows():
            cname, iname = str(r.get("CodeName", "")).strip(), str(r.get("Name", "")).strip()

            # Only ingest items that exist in our global catalog
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

        # Save to database using the Repository (ORM style)
        snapshot_id = await self.repo.ingest_snapshot(town, struct_type, stockpile_name, items)
        return snapshot_id, len(items), struct_type

    @app_commands.command(name="upload", description="Upload a stockpile screenshot for processing")
    @app_commands.describe(town="Town name", image="Stockpile screenshot",
                           stockpile_name="Optional specific stockpile name")
    async def upload(
            self,
            interaction: discord.Interaction,
            town: str,
            image: discord.Attachment,
            stockpile_name: str = "Public"
    ) -> None:
        """Handles the file upload and kicks off the OCR/Ingestion pipeline."""
        if not image.content_type or not image.content_type.startswith("image/"):
            return await interaction.response.send_message("Please upload a valid image file.", ephemeral=True)

        # Defer because OCR processing is slow and we don't want to timeout
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

    @app_commands.command(name="stockpile", description="View the latest items for a specific town")
    @app_commands.describe(town="Town name", stockpile="Optional specific stockpile filter")
    async def view_stockpile(self, interaction: discord.Interaction, town: str, stockpile: str | None = None) -> None:
        town = (town or "").strip()
        if not town:
            return await interaction.response.send_message("Town is required.", ephemeral=True)

        # Fetch data through the repository
        rows = await self.repo.get_latest_inventory(town, stockpile)

        if not rows:
            return await interaction.response.send_message(f"No snapshots found for `{town}`.", ephemeral=False)

        # Format output
        df = pd.DataFrame(rows)
        df['is_crated'] = df['is_crated'].map({True: 'Y', False: 'N'})
        cols = ['item_name', 'quantity', 'is_crated', 'stockpile_name', 'struct_type']
        headers = ["Item", "Qty", "Crate", "Stockpile", "Type"]

        def get_table(data_frame):
            return tabulate(data_frame, headers=headers, showindex=False, tablefmt="simple")

        df_select = df[cols]
        lines = tabulate(df_select, headers=headers, showindex=False, tablefmt="simple")

        # Handle Discord character limit
        n_rows = len(df.index)
        while len(lines) > DISCORD_CHARACTER_LIMIT - 150:
            n_rows -= 1
            lines = get_table(df_select.head(n_rows)) + "\n... (truncated)"

        title = f"**{town} Inventory #{len(df.index)}**" + (f" (Filter: {stockpile})" if stockpile else "")
        await interaction.response.send_message(f"{title}\n```\n{lines}\n```", ephemeral=False)

    @view_stockpile.autocomplete("town")
    async def town_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Provides autocomplete suggestions for town names."""
        now = time.time()
        cache_key = "town_names"

        # Use cached results for 60 seconds to stay snappy
        if cache_key in self._autocomplete_cache:
            timestamp, cached_towns = self._autocomplete_cache[cache_key]
            if now - timestamp < 60:
                towns = cached_towns
            else:
                towns = await self.repo.get_unique_towns()
                self._autocomplete_cache[cache_key] = (now, towns)
        else:
            towns = await self.repo.get_unique_towns()
            self._autocomplete_cache[cache_key] = (now, towns)

        return [
            app_commands.Choice(name=town, value=town)
            for town in towns if current.lower() in town.lower()
        ][:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StockpileCog(bot))
