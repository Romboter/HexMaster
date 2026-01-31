# src/hexmaster/bot/cogs/health.py
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import text, select, func

from hexmaster.db.models import Region, Town


class HealthCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
            regions_count = await conn.scalar(select(func.count()).select_from(Region))
            towns_count = await conn.scalar(select(func.count()).select_from(Town))

            # Random samples (5 each) to quickly confirm the data "looks right".
            # Implementation detail:
            # - SQLite + Postgres: ORDER BY random()
            # - MySQL/MariaDB: ORDER BY rand()
            # This is not the most efficient on huge tables, but it's perfect for small seed tables.
            region_names = (
                await conn.execute(
                    select(Region.name)
                    .order_by(func.random())
                    .limit(5)
                )
            ).scalars().all()

            town_names = (
                await conn.execute(
                    select(Town.name)
                    .order_by(func.random())
                    .limit(5)
                )
            ).scalars().all()

        # Convert None -> 0 (just in case the scalar returns None).
        regions_count_i = int(regions_count or 0)
        towns_count_i = int(towns_count or 0)

        # Build a simple Markdown message (no tables) so it stays readable in Discord.
        lines: list[str] = [
            "**DB Stats**",
            f"• **Regions:** `{regions_count_i}`",
            f"• **Towns:** `{towns_count_i}`",
            "",
            "**Random Regions (5)**",
        ]

        # Add region samples (or a placeholder if empty).
        if region_names:
            lines.extend(f"• {n}" for n in region_names)
        else:
            lines.append("• _(none)_")

        lines += ["", "**Random Towns (5)**"]

        # Add town samples (or a placeholder if empty).
        if town_names:
            lines.extend(f"• {n}" for n in town_names)
        else:
            lines.append("• _(none)_")

        msg = "\n".join(lines)

        await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HealthCog(bot))
