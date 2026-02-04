import asyncio
import os
from pathlib import Path

import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import create_async_engine

from hexmaster.config import Settings
from hexmaster.logging import configure_logging
from hexmaster.db.init import init_db
from hexmaster.db.seed_reference import seed_towns_from_csv, seed_catalog_from_csv, seed_priority_from_csv

from hexmaster.db.repositories.stockpile_repository import StockpileRepository
from hexmaster.services.ocr_service import OCRService


class HexmasterBot(commands.Bot):
    def __init__(self, settings: Settings):
        # Default intents are enough for Slash Commands
        intents = discord.Intents.default()
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.settings = settings
        self.engine = create_async_engine(settings.database_url)

        # Dependency Injection: Initialize once, use everywhere
        self.repo = StockpileRepository(self.engine)
        self.ocr_service = OCRService(settings.ocr_url)
#
    async def setup_hook(self):
        # 1. Ensure DB schema is created (Replaces manual SQL files)
        await init_db(self.engine)

        # 2.
        data_dir = Path("sample_data")
        await seed_towns_from_csv(self.engine, data_dir / "Towns.csv")
        await seed_catalog_from_csv(self.engine, data_dir / "catalog.csv")
        await seed_priority_from_csv(self.engine, data_dir / "Priority.csv")

        # 3.
        await self.load_extension("hexmaster.bot.cogs.stockpile_cog")
        await self.load_extension("hexmaster.bot.cogs.health")


        # 4. Syncing on every boot is fine for development but slow for production
        # ✅ DEV: sync to one guild (fast), and wipe stale guild commands first
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)  # 👈 This is the missing link!
            await self.tree.sync(guild=guild)
            print(f"✅ Synced commands to guild {guild_id}")
        else:
            # Fallback: global (slow + can cause the “dupe” situation during dev)
            await self.tree.sync()
            print("✅ Synced commands globally")

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