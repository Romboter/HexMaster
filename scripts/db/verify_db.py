# Copyright (c) 2024-2025 Gary Kuepper
# Licensed under the MIT License.

import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def check_schema():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not found in .env or environment")
        return

    engine = create_async_engine(db_url)
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'regions'")
        )
        columns = [row[0] for row in result]
        print(f"Columns in 'regions' table: {columns}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_schema())
