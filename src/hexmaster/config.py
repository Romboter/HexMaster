# src/hexmaster/config.py
from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str
    discord_token: str

    @staticmethod
    def load() -> "Settings":
        return Settings(
            database_url=os.environ["DATABASE_URL"],
            discord_token=os.environ["DISCORD_TOKEN"],
        )