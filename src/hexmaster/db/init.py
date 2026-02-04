from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from .base import Base
from . import models  # noqa: F401
from .schema_sync import sync_schema


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        # 1. Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
        
        # 2. Add missing columns to existing tables
        await sync_schema(conn)