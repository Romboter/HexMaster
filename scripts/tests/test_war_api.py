# Copyright (c) 2024-2025 Gary Kuepper
# Licensed under the MIT License.

import asyncio

from hexmaster.services.war_service import WarService


async def test_war_service():
    service = WarService()
    print("Fetching current war number...")
    war_number = await service.get_current_war_number()
    print(f"Current War Number: {war_number}")

    # Test caching
    print("Fetching again (should be cached)...")
    war_number_cached = await service.get_current_war_number()
    print(f"Current War Number (cached): {war_number_cached}")


if __name__ == "__main__":
    asyncio.run(test_war_service())
