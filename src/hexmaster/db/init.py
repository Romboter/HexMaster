from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from .base import Base
from . import models  # noqa: F401  (ensures models are imported/registered)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)