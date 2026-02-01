import io
import requests
import pandas as pd
import discord
from datetime import datetime, timezone
from discord import app_commands
from discord.ext import commands
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from hexmaster.config import Settings

class StockpileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = Settings.load()
        # Use existing engine from bot if possible
        self.engine = getattr(bot, "engine", create_async_engine(self.settings.database_url))

    async def process_remote_and_ingest(self, image_bytes: bytes, town: str, stockpile_name: str):
        """
        Sends bytes to the remote Docker server and ingests the TSV response into Postgres.
        """
        # 1. Remote Processing
        # Adjust 'localhost' to your Ubuntu server's IP if the bot is running elsewhere
        url = "http://192.168.50.44:5000/process"
        data = {
            "label": town,
            "stockpile": stockpile_name,
            "version": "airborne-63"
        }
        files = {'image': ('upload.png', image_bytes, 'image/png')}

        try:
            response = requests.post(url, data=data, files=files, timeout=180)
            response.raise_for_status()
            df = pd.read_csv(io.StringIO(response.text), sep='\t').fillna("")
        except Exception as e:
            raise RuntimeError(f"OCR Server Error: {e}")

        if df.empty:
            raise ValueError("The processing server returned an empty dataset.")

        # Extract struct_type from the CSV data provided by the server
        # We assume all rows in one image share the same structure type
        struct_type = str(df.iloc[0].get("struct_type", "Unknown")).strip()

        # 2. Database Ingestion
        async with self.engine.begin() as conn:
            # Validate items against master catalog
            catalog_res = await conn.execute(text("SELECT codename, displayname FROM catalog_items"))
            valid_keys = {(row.codename, row.displayname) for row in catalog_res}

            # Create the Snapshot record
            res = await conn.execute(
                text("""
                    INSERT INTO stockpile_snapshots (town, struct_type, stockpile_name, captured_at)
                    VALUES (:town, :struct_type, :stockpile_name, :captured_at)
                    RETURNING id
                """),
                {
                    "town": town,
                    "struct_type": struct_type,
                    "stockpile_name": stockpile_name,
                    "captured_at": datetime.now(timezone.utc),
                }
            )
            snapshot_id = res.scalar_one()

            # Batch prepare items
            items = []
            for _, r in df.iterrows():
                cname, iname = str(r.get("CodeName", "")).strip(), str(r.get("Name", "")).strip()
                if (cname, iname) in valid_keys:
                    items.append({
                        "snapshot_id": snapshot_id,
                        "code_name": cname,
                        "item_name": iname,
                        "quantity": int(r["Quantity"]) if r.get("Quantity") else 0,
                        "is_crated": str(r.get("Crated?", "")).upper() in ("TRUE", "YES", "T", "Y"),
                        "per_crate": int(r["Per Crate"]) if r.get("Per Crate") else 0,
                        "total": int(r["Total"]) if r.get("Total") else 0,
                        "description": str(r.get("Description", "")).strip()
                    })

            if items:
                await conn.execute(
                    text("""
                        INSERT INTO snapshot_items 
                        (snapshot_id, code_name, item_name, quantity, is_crated, per_crate, total, description)
                        VALUES (:snapshot_id, :code_name, :item_name, :quantity, :is_crated, :per_crate, :total, :description)
                    """),
                    items
                )
        
        return snapshot_id, len(items), struct_type

    # Replace @commands.command with @app_commands.command
    @app_commands.command(name="upload", description="Process and save a stockpile screenshot")
    @app_commands.describe(
        image="The screenshot to process",
        town="Name of the town (e.g. Tine, TheManacle)",
        stockpile="Optional name of the stockpile (defaults to Public)"
    )
    async def upload(
        self, 
        interaction: discord.Interaction, 
        image: discord.Attachment, 
        town: str, 
        stockpile: str = "Public"
    ):
        # Slash commands use interaction.response instead of ctx.send
        if not image.content_type or not image.content_type.startswith("image/"):
            return await interaction.response.send_message("❌ Please upload a valid image file.", ephemeral=True)

        # Defer because processing takes time
        await interaction.response.defer(ephemeral=False)

        try:
            image_bytes = await image.read()
            sid, count, s_type = await self.process_remote_and_ingest(image_bytes, town, stockpile)
            
            await interaction.followup.send(
                f"✅ **Stockpile Ingested**\n"
                f"• **Location:** `{town}`\n"
                f"• **Type:** `{s_type}`\n"
                f"• **Stockpile:** `{stockpile}`\n"
                f"• **Items:** `{count}`\n"
                f"• **Snapshot ID:** `{sid}`"
            )
        except Exception as e:
            await interaction.followup.send(f"❌ **Processing Failed:** {str(e)}")
async def setup(bot: commands.Bot):
    await bot.add_cog(StockpileCog(bot))
