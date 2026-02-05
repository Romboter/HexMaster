# src/hexmaster/config.py
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


from dotenv import load_dotenv

# load_dotenv() will automatically find the nearest .env file
load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    discord_token: str
    ocr_url: str
    warapi_base_url: str

    @staticmethod
    def load() -> "Settings":
        # No need to manually search and load anymore as load_dotenv() handles it.
        # But we can keep the searched paths for error reporting if needed.
        searched = [Path.cwd() / ".env"]

        database_url = os.getenv("DATABASE_URL")
        discord_token = os.getenv("DISCORD_TOKEN")
        ocr_url = os.getenv("OCR_URL", "http://localhost:8000")
        warapi_base_url = os.getenv("WARAPI_BASE_URL", "https://war-service-live.foxholeservices.com/api")

        missing = [
            name
            for name, value in (
                ("DATABASE_URL", database_url),
                ("DISCORD_TOKEN", discord_token),
                ("OCR_URL", ocr_url),
                ("WARAPI_BASE_URL", warapi_base_url)
            )
            if not value
        ]
        if missing:
            missing_list = ", ".join(missing)

            # De-dupe while keeping order
            deduped = list(dict.fromkeys(searched))
            looked_in = "\n".join(f"- {p}" for p in deduped)

            raise RuntimeError(
                f"Missing required configuration: {missing_list}.\n"
                "Expected them in environment variables or in a .env file.\n"
                "Searched for .env at:\n"
                f"{looked_in}\n\n"
                "Example .env:\n"
                'DATABASE_URL="<your async SQLAlchemy URL>"\n'
                'DISCORD_TOKEN="<your discord bot token>"\n'
                'WARAPI_BASE_URL="https://war-service-live.foxholeservices.com/api"\n'
            )

        return Settings(
            database_url=database_url,
            discord_token=discord_token,
            ocr_url=ocr_url,
            warapi_base_url=warapi_base_url
        )
