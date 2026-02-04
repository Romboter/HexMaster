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
    @app_commands.default_permissions(administrator=True)
    async def ping(self, interaction: discord.Interaction) -> None:
        async with self.bot.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await interaction.response.send_message("Pong. DB OK.", ephemeral=True)

    @app_commands.command(name="db_stats", description="Show system database statistics.")
    @app_commands.default_permissions(administrator=True)
    async def db_stats(self, interaction: discord.Interaction) -> None:
        async with self.bot.engine.connect() as conn:
            snapshots = await conn.scalar(text("SELECT COUNT(*) FROM stockpile_snapshots"))
            items = await conn.scalar(text("SELECT COUNT(*) FROM snapshot_items"))

        msg = (f"**System Stats**\n"
               f"• Snapshots: `{snapshots or 0}`\n"
               f"• Items: `{items or 0}`")
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="check_towns", description="Verify the towns table content.")
    @app_commands.default_permissions(administrator=True)
    async def check_towns(self, interaction: discord.Interaction) -> None:
        """Health check to see if towns are correctly seeded."""
        async with self.bot.engine.connect() as conn:
            # Join with regions to get the region name instead of ID
            result = await conn.execute(text("""
                SELECT t.name, r.name 
                FROM towns t 
                JOIN regions r ON t.region_id = r.id 
                ORDER BY t.name LIMIT 10
            """))
            rows = result.all()
            total = await conn.scalar(text("SELECT COUNT(*) FROM towns"))

        if not rows:
            return await interaction.response.send_message("❌ The `towns` table is empty!", ephemeral=True)

        lines = "\n".join([f"• {row[0]} ({row[1]})" for row in rows])
        await interaction.response.send_message(
            f"✅ **Towns Preview (Total: {total})**\n{lines}\n*Showing first 10 alphabetically.*",
            ephemeral=True
        )

    @app_commands.command(name="check_regions", description="Verify the regions table content.")
    @app_commands.default_permissions(administrator=True)
    async def check_regions(self, interaction: discord.Interaction) -> None:
        """Health check to see if regions are correctly seeded."""
        async with self.bot.engine.connect() as conn:
            result = await conn.execute(text("SELECT name, q, r FROM regions ORDER BY name LIMIT 10"))
            rows = result.all()
            total = await conn.scalar(text("SELECT COUNT(*) FROM regions"))

        if not rows:
            return await interaction.response.send_message("❌ The `regions` table is empty!", ephemeral=True)

        lines = "\n".join([f"• {row[0]} (q: {row[1]}, r: {row[2]})" for row in rows])
        await interaction.response.send_message(
            f"✅ **Regions Preview (Total: {total})**\n{lines}\n*Showing first 10 alphabetically.*",
            ephemeral=True
        )

    @app_commands.command(name="check_priority", description="Verify the priority table content.")
    @app_commands.default_permissions(administrator=True)
    async def check_priority(self, interaction: discord.Interaction) -> None:
        """Health check to see if priority list is correctly seeded."""
        async with self.bot.engine.connect() as conn:
            result = await conn.execute(text("SELECT name, codename, priority FROM priority ORDER BY priority LIMIT 10"))
            rows = result.all()
            total = await conn.scalar(text("SELECT COUNT(*) FROM priority"))

        if not rows:
            return await interaction.response.send_message("❌ The `priority` table is empty!", ephemeral=True)

        lines = "\n".join([f"• {row[0]} (`{row[1]}`) - Prio: {row[2]}" for row in rows])
        await interaction.response.send_message(
            f"✅ **Priority Preview (Total: {total})**\n{lines}\n*Showing first 10 by priority.*",
            ephemeral=True
        )

    @app_commands.command(name="help", description="List all available commands and their usage.")
    async def help(self, interaction: discord.Interaction) -> None:
        """Shows help information for the bot."""
        help_text = (
            "### 🛠️ HexMaster Commands\n"
            "**General**\n"
            "• `/help`: Show this help message.\n\n"
            "**Stockpiles**\n"
            "• `/report [image] [town] [name]`: File an Intelligence Report (upload screenshot).\n"
            "• `/manifest [town] [filter]`: View the Shipping Manifest for a town.\n"
            "• `/locate [item] [from_town]`: Perform Reconnaissance to locate assets globally.\n"
            "• `/requisition [shipping] [receiving]`: Calculate a Requisition Order to fill gaps.\n\n"
            "**Maintenance**\n"
            "• `/ping`: Check bot and database health (Admin only).\n"
            "• `/db_stats`: Show database statistics (Admin only).\n"
            "• `/check_towns`: Debug current town seeding status (Admin only).\n"
            "• `/check_regions`: Debug current region seeding status (Admin only).\n"
            "• `/check_priority`: Debug current priority list status (Admin only)."
        )
        await interaction.response.send_message(help_text, ephemeral=True)




async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HealthCog(bot))
