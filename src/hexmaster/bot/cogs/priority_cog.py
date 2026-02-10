import discord
from discord import app_commands
from discord.ext import commands
from hexmaster.utils.discord_utils import (
    render_and_truncate_table,
    send_success,
    send_error
)

class PriorityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.repo = getattr(bot, "repo")

    priority_group = app_commands.Group(
        name="priority", 
        description="Manage the stockpile priority list",
        default_permissions=discord.Permissions(administrator=True)
    )

    @priority_group.command(name="list", description="List all items in the priority list")
    async def list_priority(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            guild_id = interaction.guild_id
            if not guild_id:
                return await interaction.followup.send("This command can only be used in a server.")
            
            items = await self.repo.get_priority_list(guild_id)
            if not items:
                return await interaction.followup.send("The priority list is currently empty.")

            # Sort by priority field
            items.sort(key=lambda x: x["priority"])

            table_rows = [
                [item["name"], f"{item['qty_per_crate']}", f"{item['min_for_base_crates'] or 0}", f"{item['priority']:g}"]
                for item in items
            ]
            await render_and_truncate_table(
                interaction, 
                table_rows, 
                ["Item", "QPC", "Min", "Prio"], 
                "Current Priority List",
                as_embed=True
            )
        except Exception as e:
            await send_error(interaction, f"Error listing priority: {e}")

    @priority_group.command(name="add", description="Add or update an item in the priority list")
    @app_commands.describe(
        item="The item to add (from catalog)",
        min_crates="Target minimum crates",
        priority="Priority weight (lower is higher in list)"
    )
    async def add_priority(self, interaction: discord.Interaction, item: str, min_crates: int, priority: float):
        await interaction.response.defer(ephemeral=True)
        try:
            guild_id = interaction.guild_id
            if not guild_id:
                return await send_error(interaction, "This command can only be used in a server.")

            catalog_item = await self.repo.get_catalog_item_by_name(item)
            if not catalog_item:
                return await send_error(interaction, f"Item `{item}` not found in catalog.")
            
            await self.repo.upsert_priority_item(
                guild_id=guild_id,
                codename=catalog_item.codename,
                name=catalog_item.displayname,
                qty_per_crate=catalog_item.quantitypercrate or 1,
                min_for_base_crates=min_crates,
                priority=priority
            )
            await send_success(interaction, f"Updated priority for **{catalog_item.displayname}**.")
        except Exception as e:
            await send_error(interaction, f"Error updating priority: {e}")

    @add_priority.autocomplete("item")
    async def add_priority_autocomplete(self, interaction: discord.Interaction, current: str):
        # Catalog is global, but we still use interaction
        names = await self.repo.get_all_catalog_item_names()
        choices = [
            app_commands.Choice(name=name[:100], value=name[:100])
            for name in names if current.lower() in name.lower()
        ][:25]
        return choices

    @priority_group.command(name="remove", description="Remove an item from the priority list")
    @app_commands.describe(item="The item to remove")
    async def remove_priority(self, interaction: discord.Interaction, item: str):
        await interaction.response.defer(ephemeral=True)
        try:
            guild_id = interaction.guild_id
            if not guild_id:
                return await send_error(interaction, "This command can only be used in a server.")

            priority_list = await self.repo.get_priority_list(guild_id)
            matched = next((p for p in priority_list if p["name"] == item), None)
            
            if not matched:
                return await send_error(interaction, f"Item `{item}` not found in priority list.")

            await self.repo.delete_priority_item(guild_id, matched["codename"])
            await send_success(interaction, f"Removed **{item}** from priority list.")
        except Exception as e:
            await send_error(interaction, f"Error removing priority: {e}")

    @remove_priority.autocomplete("item")
    async def remove_priority_autocomplete(self, interaction: discord.Interaction, current: str):
        guild_id = interaction.guild_id
        if not guild_id: return []
        priority_list = await self.repo.get_priority_list(guild_id)
        choices = [
            app_commands.Choice(name=p["name"][:100], value=p["name"][:100])
            for p in priority_list if current.lower() in p["name"].lower()
        ][:25]
        return choices

async def setup(bot: commands.Bot):
    await bot.add_cog(PriorityCog(bot))
