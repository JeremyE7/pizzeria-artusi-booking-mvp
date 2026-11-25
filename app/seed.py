from __future__ import annotations

from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DiningTable, Restaurant


async def seed_demo_data(session: AsyncSession) -> Restaurant:
    existing = await session.scalar(select(Restaurant).limit(1))
    if existing:
        return existing

    artusi = Restaurant(
        name="Pizzería Artusi",
        timezone="Europe/Rome",
        opening_time=time(12, 0),
        closing_time=time(23, 0),
        slot_minutes=30,
    )
    artusi.tables = [
        DiningTable(name="T1", capacity=2),
        DiningTable(name="T2", capacity=2),
        DiningTable(name="T3", capacity=4),
        DiningTable(name="T4", capacity=4),
        DiningTable(name="T5", capacity=6),
        DiningTable(name="T6", capacity=8),
    ]

    demo = Restaurant(
        name="Pizzería Demo",
        timezone="Europe/Rome",
        opening_time=time(12, 0),
        closing_time=time(22, 30),
        slot_minutes=30,
    )
    demo.tables = [
        DiningTable(name="A", capacity=2),
        DiningTable(name="B", capacity=4),
        DiningTable(name="C", capacity=6),
    ]

    session.add_all([artusi, demo])
    await session.commit()
    await session.refresh(artusi)
    return artusi
