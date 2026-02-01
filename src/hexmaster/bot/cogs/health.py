# src/hexmaster/bot/cogs/health.py
from __future__ import annotations

import time

import discord
import pandas as pd
from discord import app_commands
from discord.ext import commands
from sqlalchemy import text, select, func
from tabulate import tabulate

DISCORD_CHARACTER_LIMIT = 2000


class HealthCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._autocomplete_cache: dict[str, tuple[float, list[str]]] = {}

    def _get_cached_towns(self, query: str) -> list[str] | None:
        if query in self._autocomplete_cache:
            expires_at, results = self._autocomplete_cache[query]
            if time.time() < expires_at:
                return results
            del self._autocomplete_cache[query]
        return None

    def _set_cached_towns(self, query: str, results: list[str], ttl: int = 30):
        self._autocomplete_cache[query] = (time.time() + ttl, results)

    @app_commands.command(name="ping", description="Healthcheck and DB connectivity test.")
    async def ping(self, interaction: discord.Interaction) -> None:
        # Lightweight DB connectivity check.
        async with self.bot.engine.connect() as conn:  # type: ignore[attr-defined]
            await conn.execute(text("SELECT 1"))
        await interaction.response.send_message("Pong. DB OK.", ephemeral=True)

    @app_commands.command(name="db_stats", description="Show DB seed status (regions/towns counts + samples).")
    async def db_stats(self, interaction: discord.Interaction) -> None:
        async with self.bot.engine.connect() as conn:  # type: ignore[attr-defined]
            # Total row counts (simple sanity check that seeding worked).

            snapshots_count = await conn.scalar(text("SELECT COUNT(*) FROM stockpile_snapshots"))
            snapshot_items_count = await conn.scalar(text("SELECT COUNT(*) FROM snapshot_items"))

        snapshots_count_i = int(snapshots_count or 0)
        snapshot_items_count_i = int(snapshot_items_count or 0)

        lines: list[str] = [
            "**DB Stats**",
            f"• **Stockpile Snapshots:** `{snapshots_count_i}`",
            f"• **Snapshot Items:** `{snapshot_items_count_i}`",
            "",
        ]

        msg = "\n".join(lines)
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(
        name="stockpile",
        description="View Town Stockpile",
    )
    @app_commands.describe(town="Town name, e.g. TheManacle")
    async def stockpile(self, interaction: discord.Interaction, town: str) -> None:
        town = (town or "").strip()
        if not town:
            await interaction.response.send_message("Town is required.", ephemeral=True)
            return

        sql = text(
            """
            WITH latest_per_key AS (SELECT DISTINCT ON (s.town, s.struct_type, s.stockpile_name) s.id,
                                                                                                 s.town,
                                                                                                 s.struct_type,
                                                                                                 s.stockpile_name,
                                                                                                 s.captured_at
                                    FROM stockpile_snapshots s
                                    WHERE s.town = :town
                                    ORDER BY s.town,
                                             s.struct_type,
                                             s.stockpile_name,
                                             s.captured_at DESC,
                                             s.id DESC)
            SELECT l.town,
                   l.struct_type,
                   l.stockpile_name,
                   si.item_name,
                   si.is_crated,
                   si.quantity

            FROM latest_per_key l
                     JOIN snapshot_items si
                          ON si.snapshot_id = l.id
            ORDER BY l.town,
                     l.struct_type,
                     l.stockpile_name,
                     si.item_name,
                     si.is_crated DESC

            """
        )

        async with self.bot.engine.connect() as conn:  # type: ignore[attr-defined]
            rows = (await conn.execute(sql, {"town": town})).mappings().all()

        if not rows:
            await interaction.response.send_message(
                f"No snapshot items found for town `{town}`.",
                ephemeral=True,
            )
            return

        # Keep output tiny and predictable for Discord.

        df = pd.DataFrame(rows).sort_values(by=[ 'is_crated', 'quantity'], ascending=[False, False])
        desired = ["struct_type", "stockpile_name", "item_name", "quantity", "is_crated"]
        headers = ["Type", "Stockpile", "Item", "Qty", "Crate?"]
        tab_options = {"headers": headers, "showindex": False}
        lines = tabulate(df[desired], **tab_options)
        row_count = len(df.index)
        while len(lines) > DISCORD_CHARACTER_LIMIT - 50:  # Leave room for formatting
            row_count -= 1
            lines = tabulate(df[desired].head(row_count), **tab_options)
            if row_count == 0:
                lines = "No items found for this town..."
                break
        char_size = len(lines)

        msg = f"**{town} | {row_count} | {char_size} **\n```" + lines + "```\n"
        await interaction.response.send_message(msg, ephemeral=True)

    @stockpile.autocomplete("town")
    async def town_autocomplete(
            self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        query = (current or "").strip().casefold()

        # Check cache first
        cached = self._get_cached_towns(query)
        if cached is not None:
            return [app_commands.Choice(name=t, value=t) for t in cached]

        try:
            async with self.bot.engine.connect() as conn:  # type: ignore[attr-defined]
                # Query unique town names from the snapshots table
                sql = "SELECT DISTINCT town FROM stockpile_snapshots"
                params = {}

                if query:
                    sql += " WHERE town ILIKE :query"
                    params["query"] = f"%{query}%"

                sql += " ORDER BY town LIMIT 25"

                result = await conn.execute(text(sql), params)
                town_names = [row[0] for row in result.all()]

            self._set_cached_towns(query, town_names)
            return [app_commands.Choice(name=t, value=t) for t in town_names]
        except Exception as e:
            # Helpful for debugging if the table or column name is slightly different
            print(f"Autocomplete error: {e}")
            return []


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HealthCog(bot))
