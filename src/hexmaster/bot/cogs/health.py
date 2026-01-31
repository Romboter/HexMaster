# src/hexmaster/bot/cogs/health.py
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import text, select, func
from tabulate import tabulate

from hexmaster.db.models import Region, Town

DISCORD_CONTENT_LIMIT = 2000
# Leave space for headings + code fences so we don't accidentally hit 2000.
SAFE_LIMIT = 1900


def _github_table(rows: list, headers: list[str]) -> str:
    return tabulate(rows, headers=headers, tablefmt="github")


def _fit_sections_by_row_count(
        *,
        header: str,
        regions_rows: list,
        regions_headers: list[str],
        towns_rows: list,
        towns_headers: list[str],
        start_rows: int = 10,
) -> str:
    """
    Build a message that fits within SAFE_LIMIT by reducing ONLY the number of rows shown.
    """
    start_rows = max(0, start_rows)

    def build(n: int) -> str:
        regions_md = _github_table(regions_rows[:n], regions_headers)
        towns_md = _github_table(towns_rows[:n], towns_headers)
        return (
            f"{header}"
            f"**Regions preview** (showing {min(n, len(regions_rows))} row(s))\n"
            f"```md\n{regions_md}\n```\n"
            f"**Towns preview** (showing {min(n, len(towns_rows))} row(s))\n"
            f"```md\n{towns_md}\n```"
        )

    # Decrease rows until it fits.
    for n in range(start_rows, -1, -1):
        msg = build(n)
        if len(msg) <= SAFE_LIMIT:
            return msg

    # Shouldn't happen, but keep it safe.
    return header.rstrip()


class HealthCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Healthcheck and DB connectivity test.")
    async def ping(self, interaction: discord.Interaction) -> None:
        async with self.bot.engine.connect() as conn:  # type: ignore[attr-defined]
            await conn.execute(text("SELECT 1"))
        await interaction.response.send_message("Pong. DB OK.", ephemeral=True)

    @app_commands.command(name="db_stats", description="Show DB seed status (regions/towns counts + samples).")
    async def db_stats(self, interaction: discord.Interaction) -> None:
        async with self.bot.engine.connect() as conn:  # type: ignore[attr-defined]
            regions_count = await conn.scalar(select(func.count()).select_from(Region))
            towns_count = await conn.scalar(select(func.count()).select_from(Town))

            # Select columns + fetch some rows (we'll display fewer if needed).
            region_cols = [
                c for c in Region.__table__.columns
                if c.key not in {"id", "created_at"}
            ]
            town_cols = [
                c for c in Town.__table__.columns
                if c.key not in {"id", "region_id", "created_at"}
            ]

            regions_headers = [c.key for c in region_cols]
            towns_headers = [c.key for c in town_cols]

            regions_rows = (
                await conn.execute(
                    select(*region_cols)
                    .order_by(Region.id)
                    .limit(50)
                )
            ).all()

            towns_rows = (
                await conn.execute(
                    select(*town_cols)
                    .order_by(Town.id)
                    .limit(50)
                )
            ).all()

        regions_count_i = int(regions_count or 0)
        towns_count_i = int(towns_count or 0)

        header = (
            "**DB Stats**\n"
            f"• **Regions:** `{regions_count_i}`\n"
            f"• **Towns:** `{towns_count_i}`\n\n"
        )

        msg = _fit_sections_by_row_count(
            header=header,
            regions_rows=list(regions_rows),
            regions_headers=regions_headers,
            towns_rows=list(towns_rows),
            towns_headers=towns_headers,
            start_rows=10,
        )

        # Absolute last resort: never send > 2000 chars.
        if len(msg) > DISCORD_CONTENT_LIMIT:
            msg = (
                "**DB Stats**\n"
                f"• **Regions:** `{regions_count_i}`\n"
                f"• **Towns:** `{towns_count_i}`\n\n"
                "_Preview omitted because it won't fit in a Discord message._"
            )

        await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HealthCog(bot))
