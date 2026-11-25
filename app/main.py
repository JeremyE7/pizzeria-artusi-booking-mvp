from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.booking import BookingError, BookingService, NotFound, booking_to_out
from app.config import settings
from app.conversation import ConversationService
from app.db import Base, SessionLocal, engine
from app.intent import build_parser
from app.models import Booking, Restaurant  # noqa: F401 — registers metadata
from app.schemas import (
    AvailabilitySlot,
    BookingOut,
    CancelRequest,
    ChatRequest,
    ChatResponse,
)
from app.seed import seed_demo_data
from app.utils import from_db_utc

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def create_app(engine_=engine, session_factory=SessionLocal) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with engine_.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            await seed_demo_data(session)
        yield

    app = FastAPI(
        title="Artusi Ħabibot — Booking MVP",
        description="Asistente de reservas para restaurantes: chat, disponibilidad e idempotencia.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.session_factory = session_factory
    app.state.parser = build_parser()

    async def get_session(request: Request):
        async with request.app.state.session_factory() as session:
            yield session

    @app.get("/", response_class=HTMLResponse)
    async def chat_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="chat.html",
            context={"timezone": settings.timezone},
        )

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "artusi-booking-mvp",
            "llm": settings.llm_provider,
            "timezone": settings.timezone,
        }

    @app.post("/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest, session: AsyncSession = Depends(get_session)):
        service = ConversationService(session, parser=app.state.parser)
        return await service.handle(payload.session_id, payload.message)

    @app.get("/api/bookings", response_model=list[BookingOut])
    async def list_bookings(
        day: date | None = Query(default=None),
        restaurant_id: int | None = Query(default=None),
        session: AsyncSession = Depends(get_session),
    ):
        service = BookingService(session)
        try:
            bookings = await service.list_bookings(day=day, restaurant_id=restaurant_id)
        except NotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return [booking_to_out(booking) for booking in bookings]

    @app.get("/api/availability", response_model=list[AvailabilitySlot])
    async def availability(
        day: date = Query(...),
        party_size: int = Query(..., ge=1, le=30),
        restaurant_id: int | None = Query(default=None),
        session: AsyncSession = Depends(get_session),
    ):
        service = BookingService(session)
        try:
            restaurant = await service.get_restaurant(restaurant_id=restaurant_id)
            slots = await service.availability(day, party_size, restaurant=restaurant)
        except (NotFound, BookingError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return [
            AvailabilitySlot(
                start_at=slot.start_at,
                end_at=slot.end_at,
                table_id=slot.table_id,
                table_name=slot.table_name,
                capacity=slot.capacity,
            )
            for slot in slots
        ]

    @app.post("/api/bookings/{booking_id}/cancel", response_model=BookingOut)
    async def cancel_booking(
        booking_id: str,
        payload: CancelRequest | None = None,
        session: AsyncSession = Depends(get_session),
    ):
        service = BookingService(session)
        try:
            booking = await service.cancel_booking(
                booking_id, payload.reason if payload else None
            )
        except NotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return booking_to_out(booking)

    @app.get("/api/reminders/due", response_model=list[BookingOut])
    async def due_reminders(session: AsyncSession = Depends(get_session)):
        service = BookingService(session)
        bookings = await service.due_reminders()
        return [booking_to_out(booking) for booking in bookings]

    @app.get("/admin", response_class=HTMLResponse)
    async def admin(
        request: Request,
        day: str | None = Query(default=None),
        session: AsyncSession = Depends(get_session),
    ):
        selected_day: date | None = None
        if day:
            try:
                selected_day = date.fromisoformat(day)
            except ValueError:
                selected_day = None

        service = BookingService(session)
        try:
            bookings = await service.list_bookings(day=selected_day)
        except NotFound:
            bookings = []

        now_utc = datetime.now(timezone.utc)
        rows = []
        covers = 0
        for booking in bookings:
            local_start = from_db_utc(booking.start_at)
            if local_start is None:
                continue
            local = local_start.astimezone(ZoneInfo(booking.restaurant.timezone))
            covers += booking.party_size
            rows.append(
                {
                    "id": booking.id,
                    "short_id": booking.id[:8].upper(),
                    "customer": booking.customer_name,
                    "party": booking.party_size,
                    "table": booking.table.name,
                    "restaurant": booking.restaurant.name,
                    "date": local.strftime("%d/%m/%Y"),
                    "time": local.strftime("%H:%M"),
                    "is_future": local_start >= now_utc,
                }
            )

        future_count = sum(1 for row in rows if row["is_future"])
        next_row = next((row for row in rows if row["is_future"]), None)

        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context={
                "rows": rows,
                "covers": covers,
                "future_count": future_count,
                "next_row": next_row,
                "selected_day": selected_day.isoformat() if selected_day else "",
                "today": date.today().isoformat(),
                "timezone": settings.timezone,
            },
        )

    @app.post("/admin/bookings/{booking_id}/cancel")
    async def admin_cancel(
        booking_id: str,
        day: str | None = Form(default=None),
        session: AsyncSession = Depends(get_session),
    ):
        service = BookingService(session)
        try:
            await service.cancel_booking(booking_id, "Cancelada desde el panel de sala")
        except NotFound:
            pass
        target = "/admin" + (f"?day={day}" if day else "")
        return RedirectResponse(url=target, status_code=303)

    return app


app = create_app()
