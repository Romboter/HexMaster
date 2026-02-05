import aiohttp
from typing import List


class WarService:
    """
    Service for interacting with the Foxhole WarAPI.
    """
    def __init__(self, base_url: str):
        self.base_url = base_url

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
