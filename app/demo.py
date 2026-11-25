from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.booking import BookingService
from app.conversation import ConversationService
from app.db import Base
from app.models import Booking
from app.seed import seed_demo_data
from app.utils import format_local


async def main() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        await seed_demo_data(session)

    script = [
        "Vorrei un tavolo per 4 persone domani alle 20:30",
        "Mario Rossi",
        "sì",
    ]

    async with session_factory() as session:
        chat = ConversationService(session)
        print("=" * 66)
        print("  ARTUSI ĦABIBOT · demo de reservas (LLM mock, SQLite en memoria)")
        print("=" * 66)
        for message in script:
            print(f"\nTú   › {message}")
            response = await chat.handle("demo-session", message)
            print(f"Bot  › {response.reply}")
            if response.booking:
                booking = response.booking
                print("\n  ┌─ RICEVUTA ─────────────────────────────────────┐")
                print(f"  │ Código     {booking.id[:8].upper():<36}│")
                print(f"  │ Ospite     {booking.customer_name:<36}│")
                print(f"  │ Persone    {booking.party_size:<36}│")
                print(f"  │ Tavolo     {booking.table:<36}│")
                print(f"  │ Quando     {format_local(booking.start_at, 'Europe/Rome'):<36}│")
                print("  └────────────────────────────────────────────────┘")

        print("\n" + "-" * 66)
        print("  QUADERNO DI SALA · prenotazioni confermate")
        print("-" * 66)
        bookings = await BookingService(session).list_bookings()
        for item in bookings:
            print(
                f"  {format_local(item.start_at, item.restaurant.timezone)}"
                f"  · {item.customer_name}  · {item.party_size}p"
                f"  · tavolo {item.table.name}  · {item.id[:8].upper()}"
            )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
