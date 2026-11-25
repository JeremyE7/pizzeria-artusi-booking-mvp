from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import Booking, DiningTable, Restaurant
from app.schemas import BookingOut
from app.utils import (
    day_bounds_utc,
    ensure_utc,
    from_db_utc,
    to_db_utc,
    utc_to_local,
)


class BookingError(Exception):
    pass


class ValidationError(BookingError):
    pass


class SlotUnavailable(BookingError):
    pass


class NotFound(BookingError):
    pass


@dataclass(frozen=True)
class Slot:
    start_at: datetime
    end_at: datetime
    table_id: int
    table_name: str
    capacity: int


class BookingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_restaurant(
        self, name: str | None = None, restaurant_id: int | None = None
    ) -> Restaurant:
        stmt = select(Restaurant).options(selectinload(Restaurant.tables))
        if restaurant_id is not None:
            stmt = stmt.where(Restaurant.id == restaurant_id)
        elif name:
            stmt = stmt.where(Restaurant.name.ilike(f"%{name}%"))
        restaurant = await self.session.scalar(stmt.limit(1))
        if restaurant is None:
            raise NotFound("Restaurante no encontrado")
        return restaurant

    async def _bookings_for_day(self, restaurant: Restaurant, day: date) -> list[Booking]:
        start, end = day_bounds_utc(day, restaurant.timezone)
        stmt = select(Booking).where(
            Booking.restaurant_id == restaurant.id,
            Booking.status == "confirmed",
            Booking.start_at < to_db_utc(end),
            Booking.end_at > to_db_utc(start),
        )
        return list((await self.session.scalars(stmt)).all())

    async def availability(
        self,
        day: date,
        party_size: int,
        restaurant: Restaurant | None = None,
        restaurant_id: int | None = None,
    ) -> list[Slot]:
        restaurant = restaurant or await self.get_restaurant(restaurant_id=restaurant_id)
        if party_size < 1:
            raise ValidationError("El tamaño del grupo debe ser mayor que cero")
        tables = [t for t in restaurant.tables if t.capacity >= party_size]
        if not tables:
            return []

        duration = timedelta(minutes=settings.booking_duration_minutes)
        bookings = await self._bookings_for_day(restaurant, day)
        by_table: dict[int, list[tuple[datetime, datetime]]] = defaultdict(list)
        for booking in bookings:
            by_table[booking.table_id].append((booking.start_at, booking.end_at))

        tz = ZoneInfo(restaurant.timezone)
        cursor = datetime.combine(day, restaurant.opening_time, tzinfo=tz)
        close = datetime.combine(day, restaurant.closing_time, tzinfo=tz)
        slots: list[Slot] = []

        while cursor + duration <= close:
            start_utc = ensure_utc(cursor)
            end_utc = start_utc + duration
            start_db = to_db_utc(start_utc)
            end_db = to_db_utc(end_utc)
            for table in sorted(tables, key=lambda item: (item.capacity, item.id)):
                occupied = by_table.get(table.id, [])
                if any(start_db < existing_end and end_db > existing_start for existing_start, existing_end in occupied):
                    continue
                slots.append(
                    Slot(
                        start_at=start_utc,
                        end_at=end_utc,
                        table_id=table.id,
                        table_name=table.name,
                        capacity=table.capacity,
                    )
                )
            cursor += timedelta(minutes=restaurant.slot_minutes)

        return slots

    async def create_booking(
        self,
        *,
        restaurant_id: int,
        customer_name: str,
        party_size: int,
        start_at: datetime,
        idempotency_key: str,
        table_id: int | None = None,
        customer_phone: str | None = None,
        notes: str | None = None,
    ) -> Booking:
        existing = await self.session.scalar(
            select(Booking).where(Booking.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing

        restaurant = await self.get_restaurant(restaurant_id=restaurant_id)
        if party_size < 1:
            raise ValidationError("El tamaño del grupo debe ser mayor que cero")

        start = ensure_utc(start_at)
        end = start + timedelta(minutes=settings.booking_duration_minutes)
        tz = ZoneInfo(restaurant.timezone)
        local_start = start.astimezone(tz)
        local_end = end.astimezone(tz)
        now_local = datetime.now(timezone.utc).astimezone(tz)

        if local_start < now_local:
            raise ValidationError("No se puede reservar en el pasado")
        if local_end.date() != local_start.date():
            raise ValidationError("La reserva debe terminar el mismo día")
        if not (restaurant.opening_time <= local_start.time() < restaurant.closing_time):
            raise ValidationError("La hora está fuera del horario del restaurante")
        if local_end.time() > restaurant.closing_time:
            raise ValidationError("La reserva termina fuera del horario del restaurante")

        opening_minutes = restaurant.opening_time.hour * 60 + restaurant.opening_time.minute
        local_minutes = local_start.hour * 60 + local_start.minute
        if (local_minutes - opening_minutes) % restaurant.slot_minutes != 0:
            raise ValidationError("La hora no coincide con la grilla de reservas")

        candidates = [t for t in restaurant.tables if t.capacity >= party_size]
        if table_id is not None:
            candidates = [t for t in candidates if t.id == table_id]
        if not candidates:
            raise ValidationError("No hay mesa para ese tamaño de grupo")

        # Re-check the chosen table, and pick the smallest free table when none was given.
        table: DiningTable | None = None
        for candidate in sorted(candidates, key=lambda item: (item.capacity, item.id)):
            overlap = await self.session.scalar(
                select(Booking).where(
                    Booking.table_id == candidate.id,
                    Booking.status == "confirmed",
                    Booking.start_at < to_db_utc(end),
                    Booking.end_at > to_db_utc(start),
                )
            )
            if overlap is None:
                table = candidate
                break
        if table is None:
            raise SlotUnavailable("Ese horario ya no está disponible")

        booking = Booking(
            id=str(uuid4()),
            restaurant_id=restaurant.id,
            table_id=table.id,
            customer_name=customer_name.strip()[:120],
            customer_phone=customer_phone,
            party_size=party_size,
            start_at=to_db_utc(start),
            end_at=to_db_utc(end),
            status="confirmed",
            idempotency_key=idempotency_key,
            notes=notes,
        )
        self.session.add(booking)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.session.scalar(
                select(Booking).where(Booking.idempotency_key == idempotency_key)
            )
            if existing is not None:
                return existing
            raise SlotUnavailable("No se pudo confirmar la reserva, intenta de nuevo")

        return await self.get_booking(booking.id)

    async def get_booking(self, booking_id: str) -> Booking:
        stmt = (
            select(Booking)
            .options(selectinload(Booking.restaurant), selectinload(Booking.table))
            .where(Booking.id == booking_id)
        )
        booking = await self.session.scalar(stmt)
        if booking is None:
            raise NotFound("Reserva no encontrada")
        return booking

    async def list_bookings(self, day: date | None = None, restaurant_id: int | None = None) -> list[Booking]:
        stmt = (
            select(Booking)
            .options(selectinload(Booking.restaurant), selectinload(Booking.table))
            .where(Booking.status == "confirmed")
        )
        if restaurant_id is not None:
            stmt = stmt.where(Booking.restaurant_id == restaurant_id)
        if day is not None:
            restaurant = await self.get_restaurant(restaurant_id=restaurant_id)
            start, end = day_bounds_utc(day, restaurant.timezone)
            stmt = stmt.where(Booking.start_at < to_db_utc(end), Booking.start_at >= to_db_utc(start))
        stmt = stmt.order_by(Booking.start_at, Booking.table_id)
        return list((await self.session.scalars(stmt)).all())

    async def cancel_booking(self, booking_id: str, reason: str | None = None) -> Booking:
        booking = await self.get_booking(booking_id)
        if booking.status != "cancelled":
            booking.status = "cancelled"
            if reason:
                booking.notes = f"{booking.notes or ''}\nCancelada: {reason}".strip()
            await self.session.commit()
        return await self.get_booking(booking_id)

    async def due_reminders(self, now: datetime | None = None) -> list[Booking]:
        now_utc = ensure_utc(now or datetime.now(timezone.utc))
        window_start = to_db_utc(now_utc + timedelta(hours=23))
        window_end = to_db_utc(now_utc + timedelta(hours=25))
        stmt = (
            select(Booking)
            .options(selectinload(Booking.restaurant), selectinload(Booking.table))
            .where(
                Booking.status == "confirmed",
                Booking.start_at >= window_start,
                Booking.start_at <= window_end,
            )
            .order_by(Booking.start_at)
        )
        return list((await self.session.scalars(stmt)).all())


def booking_to_out(booking: Booking) -> BookingOut:
    timezone_name = booking.restaurant.timezone if booking.restaurant else settings.timezone
    return BookingOut(
        id=booking.id,
        restaurant=booking.restaurant.name if booking.restaurant else "",
        table=booking.table.name if booking.table else "",
        customer_name=booking.customer_name,
        party_size=booking.party_size,
        start_at=from_db_utc(booking.start_at) or datetime.now(timezone.utc),
        end_at=from_db_utc(booking.end_at) or datetime.now(timezone.utc),
        status=booking.status,
    )


def local_time_of(slot: Slot, tz_name: str) -> time:
    return utc_to_local(slot.start_at, tz_name).time().replace(second=0, microsecond=0)
