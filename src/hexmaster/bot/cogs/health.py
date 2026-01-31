# src/hexmaster/bot/cogs/health.py
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import text


class HealthCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Healthcheck and DB connectivity test.")
    async def ping(self, interaction: discord.Interaction) -> None:
        async with self.bot.engine.connect() as conn:  # type: ignore[attr-defined]
            await conn.execute(text("SELECT 1"))

        await interaction.response.send_message("Pong. DB OK.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HealthCog(bot))