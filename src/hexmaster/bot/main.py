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
        super().__init__(command_prefix="!", intents=intents)

        self.settings = settings
        self.engine = create_async_engine(settings.database_url, pool_pre_ping=True)

    async def setup_hook(self) -> None:
        await init_db(self.engine)

        await self.load_extension("hexmaster.bot.cogs.health")

        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            synced = await self.tree.sync(guild=discord.Object(id=int(guild_id)))
            log.info("Slash commands synced to guild %s: %s", guild_id, [c.name for c in synced])
        else:
            synced = await self.tree.sync()
            log.info("Slash commands synced globally: %s", [c.name for c in synced])

    async def close(self) -> None:
        # Dispose DB resources while the event loop is still alive.
        # This prevents asyncpg from trying to close sockets after loop shutdown.
        await self.engine.dispose()
        await super().close()


async def main() -> None:
    configure_logging()
    settings = Settings.load()

    bot = HexmasterBot(settings)

    # Ensure cleanup happens even on cancellation / Ctrl+C.
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())