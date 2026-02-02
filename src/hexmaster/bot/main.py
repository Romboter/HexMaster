import asyncio
import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import create_async_engine

from hexmaster.config import Settings
from hexmaster.logging import configure_logging
from hexmaster.db.init import init_db
from hexmaster.db.repositories.stockpile_repository import StockpileRepository
from hexmaster.services.ocr_service import OCRService


class HexmasterBot(commands.Bot):
    def __init__(self, settings: Settings):
        # Default intents are enough for Slash Commands
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

        self.settings = settings
        self.engine = create_async_engine(settings.database_url)

        # Dependency Injection: Initialize once, use everywhere
        self.repo = StockpileRepository(self.engine)
        self.ocr_service = OCRService(settings.ocr_url)
#
    async def setup_hook(self):
        # 1. Ensure DB schema is created (Replaces manual SQL files)
        await init_db(self.engine)

        # 2. Load Cogs
        await self.load_extension("hexmaster.bot.cogs.stockpile_cog")
        await self.load_extension("hexmaster.bot.cogs.health")

        # 3. Sync Slash Commands with Discord
        # Syncing on every boot is fine for development but slow for production
        await self.tree.sync()

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")


async def main():
    configure_logging()
    settings = Settings.load()

    bot = HexmasterBot(settings)
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())