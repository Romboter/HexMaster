# Copyright (c) 2024-2025 Gary Kuepper
# Licensed under the MIT License.

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import text

if TYPE_CHECKING:
    pass

from hexmaster.utils.datetime_utils import get_age_str
from hexmaster.utils.discord_utils import (
    EMBED_COLOR_INFO,
    render_and_truncate_table,
    send_error,
    send_success,
)


class HealthCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # We assume bot is HexMasterBot, but typing it as Any or casting is easier for now to avoid circular imports
        # at runtime if not careful
        # self.repo = cast("HexMasterBot", bot).repo
        # Actually simplest is just ignore or use getattr which is dynamic
        self.repo = getattr(bot, "repo")

    @property
    def engine(self):
        return getattr(self.bot, "engine")

    @app_commands.command(
        name="ping", description="Healthcheck and DB connectivity test."
    )
    @app_commands.default_permissions(administrator=True)
    async def ping(self, interaction: discord.Interaction) -> None:
        start_time = time.time()
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency = (time.time() - start_time) * 1000
        await send_success(
            interaction,
            f"Database connectivity active.\nLatency: `{latency:.1f}ms`",
            title="Pong",
            ephemeral=True,
        )

    @app_commands.command(
        name="db_stats", description="Show system database statistics."
    )
    @app_commands.default_permissions(administrator=True)
    async def db_stats(self, interaction: discord.Interaction) -> None:
        async with self.engine.connect() as conn:
            snapshots = await conn.scalar(
                text("SELECT COUNT(*) FROM stockpile_snapshots")
            )
            items = await conn.scalar(text("SELECT COUNT(*) FROM snapshot_items"))

        table_rows = [["Snapshots", snapshots or 0], ["Items", items or 0]]
        await render_and_truncate_table(
            interaction,
            table_rows,
            ["Stat", "Value"],
            "**System Database Statistics**",
            as_embed=True,
        )

    @app_commands.command(
        name="check_towns", description="Verify the towns table content."
    )
    @app_commands.default_permissions(administrator=True)
    async def check_towns(self, interaction: discord.Interaction) -> None:
        """Health check to see if towns are correctly seeded."""
        async with self.engine.connect() as conn:
            # Join with regions to get the region name instead of ID
            result = await conn.execute(
                text(
                    """
                SELECT t.name, r.name
                FROM towns t
                JOIN regions r ON t.region_id = r.id
                ORDER BY t.name LIMIT 10
            """
                )
            )
            rows = result.all()
            total = await conn.scalar(text("SELECT COUNT(*) FROM towns"))

        if not rows:
            return await send_error(interaction, "The `towns` table is empty!")

        table_rows = [[r[0], r[1]] for r in rows]
        await render_and_truncate_table(
            interaction,
            table_rows,
            ["Town", "Region"],
            f"**Towns Preview (Total: {total})**",
            as_embed=True,
        )

    @app_commands.command(
        name="check_regions", description="Verify the regions table content."
    )
    @app_commands.default_permissions(administrator=True)
    async def check_regions(self, interaction: discord.Interaction) -> None:
        """Health check to see if regions are correctly seeded."""
        async with self.engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name, q, r FROM regions ORDER BY name LIMIT 10")
            )
            rows = result.all()
            total = await conn.scalar(text("SELECT COUNT(*) FROM regions"))

        if not rows:
            return await send_error(interaction, "The `regions` table is empty!")

        table_rows = [[r[0], r[1], r[2]] for r in rows]
        await render_and_truncate_table(
            interaction,
            table_rows,
            ["Region", "Q", "R"],
            f"**Regions Preview (Total: {total})**",
            as_embed=True,
        )

    @app_commands.command(
        name="check_priority", description="Verify the priority table content."
    )
    @app_commands.default_permissions(administrator=True)
    async def check_priority(self, interaction: discord.Interaction) -> None:
        """Health check to see if priority list is correctly seeded."""
        async with self.engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT name, codename, priority FROM priority ORDER BY priority LIMIT 10"
                )
            )
            rows = result.all()
            total = await conn.scalar(text("SELECT COUNT(*) FROM priority"))

        if not rows:
            return await send_error(interaction, "The `priority` table is empty!")

        table_rows = [[r[0], r[1], f"{r[2]:g}"] for r in rows]
        await render_and_truncate_table(
            interaction,
            table_rows,
            ["Item", "Codename", "Priority"],
            f"**Priority Preview (Total: {total})**",
            as_embed=True,
        )

    @app_commands.command(
        name="snapshots", description="View recently uploaded snapshots"
    )
    @app_commands.describe(limit="Number of snapshots to show (default 10, max 25)")
    @app_commands.default_permissions(administrator=True)
    async def view_snapshots(
        self, interaction: discord.Interaction, limit: int = 10
    ) -> None:
        limit = max(1, min(limit, 25))
        await interaction.response.defer(ephemeral=True)

        try:
            results = await self.repo.get_latest_snapshots_summary(limit)
            if not results:
                return await interaction.followup.send(
                    "No snapshots found in the database."
                )

            table_rows = []
            for r in results:
                age = get_age_str(r["captured_at"])
                table_rows.append(
                    [
                        r["id"],
                        r["pretty_town"],
                        r["struct_type"],
                        r["stockpile_name"],
                        age,
                    ]
                )

            title = f"Latest {len(results)} Snapshots"
            await render_and_truncate_table(
                interaction,
                table_rows,
                ["ID", "Town", "Type", "Stockpile", "Age"],
                title,
                as_embed=True,
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ **Error fetching snapshots:** {str(e)}"
            )

    @app_commands.command(
        name="system_status", description="Comprehensive system health overview."
    )
    @app_commands.default_permissions(administrator=True)
    async def system_status(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="🌐 HexMaster System Status", color=EMBED_COLOR_INFO
        )

        # 1. Database Status
        try:
            async with self.engine.connect() as conn:
                snapshots = await conn.scalar(
                    text("SELECT COUNT(*) FROM stockpile_snapshots")
                )
                items = await conn.scalar(text("SELECT COUNT(*) FROM snapshot_items"))
                db_status = "✅ Connected"
        except Exception:
            db_status = "❌ Disconnected"
            snapshots, items = 0, 0

        embed.add_field(
            name="🗄️ Database",
            value=f"**Status:** {db_status}\n**Snapshots:** {snapshots}\n**Items:** {items}",
            inline=True,
        )

        # 2. War API Status
        war_status = "Unknown"
        war_num = "N/A"
        shard_display = "Alpha"

        try:
            guild_id = interaction.guild_id
            shard_name = "Alpha"  # Default fallback
            if guild_id and hasattr(self.bot, "settings_repo"):
                config = await self.bot.settings_repo.get_config(guild_id)
                if config and config.shard:
                    shard_name = config.shard

            shard_display = shard_name

            if hasattr(self.bot, "war_service"):
                war_data = await self.bot.war_service.get_war_status(shard_name)
                war_num = war_data.get("warNumber", "Unknown")
                war_status = "✅ Online"
        except Exception:
            war_status = "❌ Offline"

        embed.add_field(
            name="⚔️ War API",
            value=f"**Status:** {war_status}\n**Shard:** {shard_display}\n**Current War:** {war_num}",
            inline=True,
        )

        # 3. Bot Status
        latency = round(self.bot.latency * 1000, 1)
        embed.add_field(
            name="🤖 Bot",
            value=f"**Latency:** {latency}ms\n**Guilds:** {len(self.bot.guilds)}",
            inline=True,
        )

        embed.set_footer(
            text=f"Requested by {interaction.user}",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.timestamp = discord.utils.utcnow()

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="help", description="List all available commands and their usage."
    )
    async def help(self, interaction: discord.Interaction) -> None:
        """Shows help information for the bot, dynamically filtered by permissions."""
        is_admin = interaction.permissions.administrator

        embed = discord.Embed(
            title="🛠️ HexMaster Command Reference",
            description="Use these commands to manage and locate stockpile assets.",
            color=EMBED_COLOR_INFO,
        )

        # General Commands
        general_cmds = "• `/help`: Show this help message.\n"
        embed.add_field(name="📦 General", value=general_cmds, inline=False)

        # Logistics Commands
        logistics_cmds = (
            "• `/report [image] [town] [name]`: File an Intelligence Report (upload screenshot).\n"
            "• `/inventory [town] [stockpile]`: View the Inventory for a town.\n"
            "• `/locate [item] [from_town]`: Perform Reconnaissance to locate assets globally.\n"
            "• `/requisition [shipping] [receiving]`: Calculate a Requisition Order to fill gaps."
        )
        embed.add_field(name="🚛 Logistics", value=logistics_cmds, inline=False)

        # Admin Commands (only show if admin)
        if is_admin:
            admin_cmds = (
                "• `/system_status`: Comprehensive system health overview.\n"
                "• `/snapshots [limit]`: View recently uploaded snapshots.\n"
                "• `/priority list`: List items in the priority list.\n"
                "• `/priority add [item] [min] [prio]`: Add/Update priority item.\n"
                "• `/priority remove [item]`: Remove priority item.\n"
                "• `/ping`: Check DB connectivity.\n"
                "• `/db_stats`: Show database statistics.\n"
                "• `/check_towns`: Debug town seeding.\n"
                "• `/check_regions`: Debug region seeding.\n"
                "• `/check_priority`: Debug priority list seeding."
            )
            embed.add_field(name="🛡️ Administration", value=admin_cmds, inline=False)

        embed.set_footer(text="HexMaster Logistics Bot • Helping you deliver more.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HealthCog(bot))
