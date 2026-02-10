import discord
from discord import app_commands
from discord.ext import commands
from hexmaster.db.repositories.settings_repository import SettingsRepository
from hexmaster.utils.discord_utils import send_success, send_error

class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.repo = getattr(bot, "repo")
        self.settings_repo = SettingsRepository(self.repo.engine)
        self.war_service = getattr(bot, "war_service")

    setup_group = app_commands.Group(
        name="setup",
        description="Configure the bot for your server",
        default_permissions=discord.Permissions(administrator=True)
    )

    @setup_group.command(name="config", description="Set your server's faction and shard")
    @app_commands.describe(
        faction="Your faction (Colonial or Warden)",
        shard="The shard you are playing on (Alpha, Bravo, or Charlie)"
    )
    @app_commands.choices(faction=[
        app_commands.Choice(name="Colonial", value="Colonial"),
        app_commands.Choice(name="Warden", value="Warden")
    ], shard=[
        app_commands.Choice(name="Alpha", value="Alpha"),
        app_commands.Choice(name="Bravo", value="Bravo"),
        app_commands.Choice(name="Charlie", value="Charlie")
    ])
    async def configure(self, interaction: discord.Interaction, faction: str = None, shard: str = None):
        await interaction.response.defer(ephemeral=True)
        try:
            guild_id = interaction.guild_id
            if not guild_id:
                return await send_error(interaction, "This command can only be used in a server.")

            await self.settings_repo.upsert_config(guild_id, faction=faction, shard=shard)
            
            msg = "Configuration updated!"
            if faction: msg += f"\nFaction: **{faction}**"
            if shard: msg += f"\nShard: **{shard}**"
            
            await send_success(interaction, msg)
        except Exception as e:
            await send_error(interaction, f"Error updating configuration: {e}")

    @setup_group.command(name="priorities", description="Load default priorities for your server")
    @app_commands.describe(template="The priority template to load")
    @app_commands.choices(template=[
        app_commands.Choice(name="Standard Logistics", value="standard"),
        app_commands.Choice(name="Clear All", value="clear")
    ])
    async def load_priorities(self, interaction: discord.Interaction, template: str):
        await interaction.response.defer(ephemeral=True)
        try:
            guild_id = interaction.guild_id
            if not guild_id:
                return await send_error(interaction, "This command can only be used in a server.")

            if template == "clear":
                await self.repo.delete_all_priorities(guild_id)
                await send_success(interaction, "Cleared all priorities for this server.")
                return

            if template == "standard":
                # We could load from a CSV or a predefined list
                # For simplicity in this demo, I'll just mention it's coming soon or implement a few
                import pandas as pd
                from pathlib import Path
                priority_csv = Path("data/Priority.csv")
                if priority_csv.exists():
                    df = pd.read_csv(priority_csv)
                    for _, row in df.iterrows():
                        await self.repo.upsert_priority_item(
                            guild_id=guild_id,
                            codename=row["CodeName"],
                            name=row["Name"],
                            qty_per_crate=int(row["Qty per Crate"]),
                            min_for_base_crates=int(row["Min For Base (crates)"]) if pd.notna(row["Min For Base (crates)"]) else None,
                            priority=float(row["Priority"])
                        )
                    await send_success(interaction, "Loaded standard logistics priorities from template.")
                else:
                    await send_error(interaction, "Priority template file not found.")
            
            elif template == "clear":
                # We need a delete all for guild method
                # I'll add it to the repo later or just do it here if I had access to session
                # Let's assume repo has it
                await send_success(interaction, "Cleared all priorities. (Note: Not yet implemented in repo)")

        except Exception as e:
            await send_error(interaction, f"Error loading priorities: {e}")

    @setup_group.command(name="cleanup_commands", description="Clear legacy guild-specific commands")
    async def cleanup_commands(self, interaction: discord.Interaction):
        """Removes all commands synced specifically to this guild to resolve duplicates."""
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            if not guild:
                return await send_error(interaction, "This command can only be used in a server.")
            
            # Clear guild-specific commands
            self.bot.tree.clear_commands(guild=guild)
            await self.bot.tree.sync(guild=guild)
            
            await send_success(
                interaction, 
                "Guild commands cleared. It may take a few minutes for Discord to update your UI. "
                "Global commands will remain available."
            )
        except Exception as e:
            await send_error(interaction, f"Error cleaning up commands: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
