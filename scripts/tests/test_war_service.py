# Copyright (c) 2024-2025 Gary Kuepper
# Licensed under the MIT License.

import asyncio

from hexmaster.config import Settings
from hexmaster.services.war_service import WarService


async def test_war_service():
    print("Loading settings...")
    settings = Settings.load()
    print(f"Using WarAPI Base URL: {settings.warapi_base_url}")

    service = WarService(settings.warapi_base_url)

    print("\n1. Testing get_maps()...")
    try:
        maps = await service.get_maps()
        print(f"✅ Success! Found {len(maps)} maps.")
        print(f"First 3 maps: {maps[:3]}")
    except Exception as e:
        print(f"❌ Failed get_maps(): {e}")

    print("\n2. Testing get_war_status()...")
    try:
        war = await service.get_war_status()
        print(f"✅ Success! War Number: {war.get('warNumber')}")
    except Exception as e:
        print(f"❌ Failed get_war_status(): {e}")


if __name__ == "__main__":
    asyncio.run(test_war_service())
