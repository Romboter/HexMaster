import io
import requests
import time
import pandas as pd
import discord
from datetime import datetime, timezone
from discord import app_commands
from discord.ext import commands
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from tabulate import tabulate

from hexmaster.config import Settings

DISCORD_CHARACTER_LIMIT = 2000

class StockpileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = Settings.load()
        # Use existing engine from bot if available
        self.engine = getattr(bot, "engine", create_async_engine(self.settings.database_url))
        self._autocomplete_cache: dict[str, tuple[float, list[str]]] = {}

    async def process_remote_and_ingest(self, image_bytes: bytes, town: str, stockpile_name: str):
        """
        Sends bytes to the remote Docker server and ingests the TSV response into Postgres.
        """
        # 1. Remote Processing
        url = "http://localhost:5000/process"
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
            print(f"DEBUG: Received DataFrame columns: {df.columns.tolist()}")
        except Exception as e:
            raise RuntimeError(f"OCR Server Error: {e}")

        if df.empty:
            raise ValueError("The processing server returned an empty dataset.")

        # Extract values using the exact column names from your OCR output
        struct_type = str(df.iloc[0].get("Structure Type", "Unknown")).strip()
        
        # Prefer the stockpile name from the image if user left default
        if stockpile_name == "Public":
            sheet_stockpile = str(df.iloc[0].get("Stockpile Name", "")).strip()
            if sheet_stockpile:
                stockpile_name = sheet_stockpile

        # 2. Database Ingestion
        async with self.engine.begin() as conn:
            catalog_res = await conn.execute(text("SELECT codename, displayname FROM catalog_items"))
            valid_keys = {(row.codename, row.displayname) for row in catalog_res}

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

    @app_commands.command(name="upload", description="Process and save a stockpile screenshot")
    @app_commands.describe(
        image="The screenshot to process",
        town="Name of the town (e.g. Tine, TheManacle)",
        stockpile="Optional name of the stockpile (defaults to Public)"
    )
    async def upload(self, interaction: discord.Interaction, image: discord.Attachment, town: str, stockpile: str = "Public"):
        if not image.content_type or not image.content_type.startswith("image/"):
            return await interaction.response.send_message("❌ Please upload a valid image file.", ephemeral=True)

        await interaction.response.defer(ephemeral=False)
        try:
            image_bytes = await image.read()
            sid, count, s_type = await self.process_remote_and_ingest(image_bytes, town, stockpile)
            await interaction.followup.send(
                f"✅ **Stockpile Ingested**\n• **Town:** `{town}`\n• **Structure Type:** `{s_type}`\n"
                f"• **Stockpile:** `{stockpile}`\n• **Items:** `{count}`\n• **Snapshot ID:** `{sid}`"
            )
        except Exception as e:
            await interaction.followup.send(f"❌ **Processing Failed:** {str(e)}")

    @app_commands.command(name="stockpile", description="View the latest items for a specific town")
    @app_commands.describe(town="Town name", stockpile="Optional specific stockpile filter")
    async def view_stockpile(self, interaction: discord.Interaction, town: str, stockpile: str | None = None) -> None:
        town = (town or "").strip()
        if not town:
            await interaction.response.send_message("Town is required.", ephemeral=False)
            return

        stock_clause = "AND s.stockpile_name = :stockpile" if stockpile else ""
        sql = text(f"""
            WITH latest_per_key AS (
                SELECT DISTINCT ON (s.town, s.struct_type, s.stockpile_name) 
                    s.id, s.town, s.struct_type, s.stockpile_name, s.captured_at
                FROM stockpile_snapshots s
                WHERE s.town = :town {stock_clause}
                ORDER BY s.town, s.struct_type, s.stockpile_name, s.captured_at DESC, s.id DESC
            )
            SELECT l.town, l.struct_type, l.stockpile_name, si.item_name, si.is_crated, si.quantity
            FROM latest_per_key l
            JOIN snapshot_items si ON si.snapshot_id = l.id
            ORDER BY l.town, l.struct_type, l.stockpile_name, si.item_name, si.is_crated DESC
        """)

        params = {"town": town}
        if stockpile: params["stockpile"] = stockpile

        async with self.engine.connect() as conn:
            rows = (await conn.execute(sql, params)).mappings().all()

        if not rows:
            await interaction.response.send_message(f"No snapshots found for `{town}`.", ephemeral=False)
            return

        df = pd.DataFrame(rows).sort_values(by=['is_crated', 'quantity'], ascending=[False, False])
        desired = ["struct_type", "stockpile_name", "item_name", "quantity", "is_crated"]
        headers = ["Struct. Type", "Stockpile", "Item", "Qty", "Crate?"]
        
        lines = tabulate(df[desired], headers=headers, showindex=False)
        row_count = len(df.index)
        while len(lines) > DISCORD_CHARACTER_LIMIT - 150:
            row_count -= 1
            lines = tabulate(df[desired].head(row_count), headers=headers, showindex=False)
            if row_count == 0: break

        title = f"{town}: {row_count} items" + (f" [{stockpile}]" if stockpile else "")
        await interaction.response.send_message(f"**{title}**\n```\n{lines}\n```", ephemeral=False)

    @view_stockpile.autocomplete("town")
    async def town_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        query = (current or "").strip().casefold()
        if query in self._autocomplete_cache:
            exp, res = self._autocomplete_cache[query]
            if time.time() < exp: return [app_commands.Choice(name=t, value=t) for t in res]

        async with self.engine.connect() as conn:
            sql = "SELECT DISTINCT town FROM stockpile_snapshots"
            if query: sql += " WHERE town ILIKE :q"
            result = await conn.execute(text(sql + " LIMIT 25"), {"q": f"%{query}%"})
            towns = [row[0] for row in result.all()]
            
        self._autocomplete_cache[query] = (time.time() + 30, towns)
        return [app_commands.Choice(name=t, value=t) for t in towns]

    @view_stockpile.autocomplete("stockpile")
    async def stockpile_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        town = interaction.namespace.town
        if not town: return []
        query = (current or "").strip().casefold()
        
        async with self.engine.connect() as conn:
            sql = "SELECT DISTINCT stockpile_name FROM stockpile_snapshots WHERE town = :town"
            if query: sql += " AND stockpile_name ILIKE :q"
            result = await conn.execute(text(sql + " LIMIT 25"), {"town": town, "q": f"%{query}%"})
            names = [row[0] for row in result.all()]
            
        return [app_commands.Choice(name=n, value=n) for n in names]

async def setup(bot: commands.Bot):
    await bot.add_cog(StockpileCog(bot))
