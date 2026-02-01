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

    @app_commands.command(name="ping", description="Healthcheck and DB connectivity test.")
    async def ping(self, interaction: discord.Interaction) -> None:
        async with self.bot.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await interaction.response.send_message("Pong. DB OK.", ephemeral=True)

    @app_commands.command(name="db_stats", description="Show system database statistics.")
    async def db_stats(self, interaction: discord.Interaction) -> None:
        async with self.bot.engine.connect() as conn:
            snapshots = await conn.scalar(text("SELECT COUNT(*) FROM stockpile_snapshots"))
            items = await conn.scalar(text("SELECT COUNT(*) FROM snapshot_items"))

        msg = (f"**System Stats**\n"
               f"• Snapshots: `{snapshots or 0}`\n"
               f"• Items: `{items or 0}`")
        await interaction.response.send_message(msg, ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HealthCog(bot))
