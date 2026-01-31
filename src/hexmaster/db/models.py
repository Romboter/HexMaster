from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)

    # Optional “world grid” fields (present in sample_data/Regions.csv)
    q: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    r: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_to_origin: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    towns: Mapped[list["Town"]] = relationship(back_populates="region")


class Town(Base):
    __tablename__ = "towns"
    __table_args__ = (
        # If you later discover Town names aren’t globally unique, swap this for
        # UniqueConstraint("region_id", "name")
        UniqueConstraint("name", name="uq_towns_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False, index=True)
    region: Mapped[Region] = relationship(back_populates="towns")

    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # Map coordinates (0..1-ish from your sample)
    x: Mapped[float | None] = mapped_column(Float, nullable=True)
    y: Mapped[float | None] = mapped_column(Float, nullable=True)

    marker_type: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Global hex coords from your sample
    global_q: Mapped[float | None] = mapped_column(Float, nullable=True)
    global_r: Mapped[float | None] = mapped_column(Float, nullable=True)

    # e.g. “Storage Depot”
    town_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)