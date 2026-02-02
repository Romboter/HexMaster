# src/hexmaster/config.py
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _load_dotenv(dotenv_path: Path) -> None:
    """
    Minimal .env loader:
    - supports KEY=VALUE
    - ignores blank lines and comments starting with #
    - strips surrounding single/double quotes from values
    - does not overwrite already-set environment variables
    """
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')

        if key and key not in os.environ:
            os.environ[key] = value


def _find_dotenv(start: Path) -> Path | None:
    """
    Find the nearest .env by walking upward from `start` (file or directory).
    Returns the first match, or None if not found.
    """
    start_dir = start if start.is_dir() else start.parent

    for directory in (start_dir, *start_dir.parents):
        candidate = directory / ".env"
        if candidate.exists():
            return candidate
    return None


@dataclass(frozen=True)
class Settings:
    database_url: str
    discord_token: str
    ocr_url: str  # 1. Add this field here

    @staticmethod
    def load() -> "Settings":
        searched: list[Path] = []

        # 1) Try current working directory (what you already relied on)
        cwd_env = Path.cwd() / ".env"
        searched.append(cwd_env)
        _load_dotenv(cwd_env)

        # 2) Also try walking upward from this module's location (robust across run modes)
        module_env = _find_dotenv(Path(__file__).resolve())
        if module_env is not None:
            searched.append(module_env)
            _load_dotenv(module_env)

        database_url = os.getenv("DATABASE_URL")
        discord_token = os.getenv("DISCORD_TOKEN")
        ocr_url = os.getenv("OCR_URL", "http://localhost:8000")  # 2. Extract it to a variable

        missing = [
            name
            for name, value in (
                ("DATABASE_URL", database_url),
                ("DISCORD_TOKEN", discord_token),
                ("OCR_URL", ocr_url)  # 3. Optional: add to validation
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
            )

        return Settings(
            database_url=database_url,
            discord_token=discord_token,
            ocr_url=ocr_url,  # Default to localhost if not set

        )
