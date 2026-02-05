import aiohttp
import asyncio
from datetime import datetime, timedelta

class WarService:
    """Service to fetch and cache the current war information from Foxhole WarAPI."""
    WAR_API_URL = "https://war-service-live-2.foxholeservices.com/api/worldconquest/war"
    
    def __init__(self):
        self._current_war_number = None
        self._last_fetch = None
        self._cache_duration = timedelta(hours=1)
        self._lock = asyncio.Lock()

    async def get_current_war_number(self) -> int:
        """Fetches the current war number, using cache if available."""
        async with self._lock:
            now = datetime.now()
            if self._current_war_number is not None and self._last_fetch is not None:
                if now - self._last_fetch < self._cache_duration:
                    return self._current_war_number

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.WAR_API_URL, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            self._current_war_number = data.get("warNumber")
                            self._last_fetch = now
                            return self._current_war_number
                        else:
                            print(f"Error fetching war info: HTTP {response.status}")
            except Exception as e:
                print(f"Error fetching war info: {e}")

            # Return cached value even if expired if fetch fails, or None
            return self._current_war_number
