from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (Column, String, Integer, DateTime, Boolean,
                        ForeignKey, Text, Float)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class CatalogItem(Base):
    """Global reference for items found in the game."""
    __tablename__ = "catalog_items"

    codename: Mapped[str] = mapped_column(String(100), primary_key=True)
    displayname: Mapped[str] = mapped_column(String(255))

class Priority(Base):
    __tablename__ = 'priority'

    codename: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    qty_per_crate: Mapped[int] = mapped_column(Integer)
    min_for_base_crates: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    priority: Mapped[float] = mapped_column(Float)

class StockpileSnapshot(Base):
    """A single 'upload' or snapshot of a stockpile at a point in time."""
    __tablename__ = "stockpile_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[Optional[int]] = mapped_column(index=True)
    town: Mapped[str] = mapped_column(String(100), index=True)
    struct_type: Mapped[str] = mapped_column(String(100))
    stockpile_name: Mapped[str] = mapped_column(String(255))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationship to the items within this snapshot
    items: Mapped[List["SnapshotItem"]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan"
    )


class SnapshotItem(Base):
    """The individual item counts within a specific snapshot."""
    __tablename__ = "snapshot_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("stockpile_snapshots.id"))
    code_name: Mapped[str] = mapped_column(String(100))
    item_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    is_crated: Mapped[bool] = mapped_column(Boolean, default=False)
    per_crate: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[Optional[str]] = mapped_column(Text)

    snapshot: Mapped["StockpileSnapshot"] = relationship(back_populates="items")


class Town(Base):
    __tablename__ = "towns"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    region: Mapped[str] = mapped_column(String, index=True)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    marker_type: Mapped[str] = mapped_column(String)
