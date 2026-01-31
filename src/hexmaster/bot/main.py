# src/hexmaster/bot/main.py
from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import create_async_engine

from hexmaster.config import Settings
from hexmaster.logging_ import configure_logging

log = logging.getLogger(__name__)


class HexmasterBot(commands.Bot):
    def __init__(self, settings: Settings):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

        self.settings = settings
        self.engine = create_async_engine(settings.database_url, pool_pre_ping=True)

    async def setup_hook(self) -> None:
        await self.load_extension("hexmaster.bot.cogs.health")
        await self.tree.sync()
        log.info("Slash commands synced.")

    async def close(self) -> None:
        await super().close()
        await self.engine.dispose()


async def main() -> None:
    configure_logging()
    settings = Settings.load()

    bot = HexmasterBot(settings)
    await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())