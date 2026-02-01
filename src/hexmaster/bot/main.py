# src/hexmaster/bot/main.py
from __future__ import annotations

import asyncio
import logging
import os

import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import create_async_engine

from hexmaster.config import Settings
from hexmaster.db.init import init_db
from hexmaster.logging import configure_logging

log = logging.getLogger(__name__)

class HexmasterBot(commands.Bot):
    def __init__(self, settings: Settings):
        intents = discord.Intents.default()
        # Slash commands don't require message_content intent
        intents.message_content = False
        
        super().__init__(command_prefix="!", intents=intents)

        self.settings = settings
        # Initialize the shared database engine
        self.engine = create_async_engine(settings.database_url, pool_pre_ping=True)

    async def setup_hook(self) -> None:
        # 1. Initialize DB tables if they don't exist
        await init_db(self.engine)

        # 2. Load the cogs
        await self.load_extension("hexmaster.bot.cogs.health")
        await self.load_extension("hexmaster.bot.cogs.stockpile_cog")

        # 3. Sync Slash Commands
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            # Copies Cog commands into the guild tree for instant updates
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Slash commands synced to guild %s: %s", guild_id, [c.name for c in synced])
        else:
            # Global sync (can take up to an hour to propagate)
            synced = await self.tree.sync()
            log.info("Slash commands synced globally: %s", [c.name for c in synced])

    async def close(self) -> None:
        # Cleanup DB resources on shutdown
        await self.engine.dispose()
        await super().close()

async def main() -> None:
    configure_logging()
    settings = Settings.load()

    bot = HexmasterBot(settings)

    async with bot:
        await bot.start(settings.discord_token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot stopped by user.")
