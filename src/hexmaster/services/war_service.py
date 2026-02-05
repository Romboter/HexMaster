import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Optional


class WarService:
    """
    Service for interacting with the Foxhole WarAPI.
    Provides cached access to war information and real-time map data.
    """
    def __init__(self, base_url: str):
        self.base_url = base_url
        self._current_war_number: Optional[int] = None
        self._last_fetch: Optional[datetime] = None
        self._cache_duration = timedelta(hours=1)
        self._lock = asyncio.Lock()

    async def get_maps(self) -> List[str]:
        """
        Fetches the list of active maps (hexes) from the WarAPI.
        """
        url = f"{self.base_url}/worldconquest/maps"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"WarAPI returned status {resp.status}: {error_text}")
                return await resp.json()

    async def get_war_status(self) -> dict:
        """
        Fetches the current war status (number, start time, etc.).
        """
        url = f"{self.base_url}/worldconquest/war"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"WarAPI returned status {resp.status}: {error_text}")
                return await resp.json()

    async def get_current_war_number(self) -> Optional[int]:
        """
        Fetches the current war number, using cache if available.
        """
        async with self._lock:
            now = datetime.now()
            if self._current_war_number is not None and self._last_fetch is not None:
                if now - self._last_fetch < self._cache_duration:
                    return self._current_war_number

            try:
                data = await self.get_war_status()
                self._current_war_number = data.get("warNumber")
                self._last_fetch = now
                return self._current_war_number
            except Exception as e:
                print(f"Error fetching war info: {e}")

            # Return cached value even if expired if fetch fails, or None
            return self._current_war_number
