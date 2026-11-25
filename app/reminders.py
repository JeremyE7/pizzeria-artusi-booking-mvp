from __future__ import annotations

import asyncio

from app.booking import BookingService
from app.db import SessionLocal
from app.utils import format_local


async def main() -> None:
    async with SessionLocal() as session:
        bookings = await BookingService(session).due_reminders()
        if not bookings:
            print("No hay recordatorios en la ventana de 23–25 horas.")
            return
        for booking in bookings:
            print(
                "[mock reminder] "
                f"{booking.customer_name} · {booking.party_size} personas · "
                f"{format_local(booking.start_at, booking.restaurant.timezone)} · "
                f"mesa {booking.table.name} · {booking.restaurant.name}"
            )
            print(
                f"  → Hola {booking.customer_name}, te esperamos mañana a las "
                f"{format_local(booking.start_at, booking.restaurant.timezone)[-5:]}. "
                f"Reserva {booking.id[:8].upper()}."
            )


if __name__ == "__main__":
    asyncio.run(main())
