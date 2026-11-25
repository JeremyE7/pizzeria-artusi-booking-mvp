from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.booking import BookingService, SlotUnavailable, ValidationError
from app.config import settings
from app.utils import to_db_utc

TZ = ZoneInfo(settings.timezone)
NOW = datetime.now(TZ)
DAY = (NOW + timedelta(days=2)).date()


async def _first_slot(service: BookingService, party_size: int = 4):
    restaurant = await service.get_restaurant()
    slots = await service.availability(DAY, party_size, restaurant=restaurant)
    assert slots, "the seeded restaurant should have availability two days out"
    return restaurant, slots[0]


async def test_idempotent_booking_returns_the_same_receipt(session):
    service = BookingService(session)
    restaurant, slot = await _first_slot(service)

    booking = await service.create_booking(
        restaurant_id=restaurant.id,
        table_id=slot.table_id,
        customer_name="Mario Rossi",
        party_size=4,
        start_at=slot.start_at,
        idempotency_key="demo-retry-1",
    )
    again = await service.create_booking(
        restaurant_id=restaurant.id,
        table_id=slot.table_id,
        customer_name="Mario Rossi",
        party_size=4,
        start_at=slot.start_at,
        idempotency_key="demo-retry-1",
    )

    assert booking.id == again.id
    assert booking.start_at == to_db_utc(slot.start_at)
    assert booking.status == "confirmed"


async def test_double_booking_the_same_table_is_rejected(session):
    service = BookingService(session)
    restaurant, slot = await _first_slot(service)

    await service.create_booking(
        restaurant_id=restaurant.id,
        table_id=slot.table_id,
        customer_name="Mario Rossi",
        party_size=4,
        start_at=slot.start_at,
        idempotency_key="demo-overlap-1",
    )

    with pytest.raises(SlotUnavailable):
        await service.create_booking(
            restaurant_id=restaurant.id,
            table_id=slot.table_id,
            customer_name="Anna Bianchi",
            party_size=4,
            start_at=slot.start_at,
            idempotency_key="demo-overlap-2",
        )


async def test_capacity_is_validated(session):
    service = BookingService(session)
    restaurant, slot = await _first_slot(service)

    with pytest.raises(ValidationError):
        await service.create_booking(
            restaurant_id=restaurant.id,
            table_id=None,
            customer_name="Gruppo grande",
            party_size=30,
            start_at=slot.start_at,
            idempotency_key="demo-capacity",
        )


async def test_cancelling_frees_the_slot(session):
    service = BookingService(session)
    restaurant, slot = await _first_slot(service)

    booking = await service.create_booking(
        restaurant_id=restaurant.id,
        table_id=slot.table_id,
        customer_name="Mario Rossi",
        party_size=4,
        start_at=slot.start_at,
        idempotency_key="demo-cancel-1",
    )
    await service.cancel_booking(booking.id, "test")

    slots_after = await service.availability(DAY, 4, restaurant=restaurant)
    assert any(
        item.table_id == slot.table_id and item.start_at == slot.start_at for item in slots_after
    )


async def test_admin_listing_includes_join_data(session):
    service = BookingService(session)
    restaurant, slot = await _first_slot(service)
    booking = await service.create_booking(
        restaurant_id=restaurant.id,
        table_id=slot.table_id,
        customer_name="Mario Rossi",
        party_size=4,
        start_at=slot.start_at,
        idempotency_key="demo-list-1",
    )

    bookings = await service.list_bookings(day=DAY)
    listed = next(item for item in bookings if item.id == booking.id)
    assert listed.restaurant.name == "Pizzería Artusi"
    assert listed.table.name == slot.table_name
