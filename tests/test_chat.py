from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.conversation import ConversationService

TZ = ZoneInfo("Europe/Rome")
NOW = datetime(2026, 11, 25, 10, 0, tzinfo=TZ)


def service(session) -> ConversationService:
    return ConversationService(session, now_provider=lambda: NOW)


@pytest.mark.asyncio
async def test_full_italian_flow_and_idempotent_confirmation(session):
    chat = service(session)

    first = await chat.handle(
        "sess-it-1", "Vorrei un tavolo per 4 persone domani alle 20:30"
    )
    assert first.state == "asking_name"
    assert "nome" in first.reply.lower()

    second = await chat.handle("sess-it-1", "Mario Rossi")
    assert second.state == "confirming"
    assert "Confermi" in second.reply

    third = await chat.handle("sess-it-1", "sì, confermo")
    assert third.state == "confirmed"
    assert third.booking is not None
    assert third.booking.customer_name == "Mario Rossi"
    assert "Prenotazione confermata" in third.reply

    # Retrying the confirmation must return the same receipt, not create a second booking.
    fourth = await chat.handle("sess-it-1", "sì")
    assert fourth.booking is not None
    assert fourth.booking.id == third.booking.id

    # "annulla" alone can cancel the last confirmed booking.
    cancelled = await chat.handle("sess-it-1", "annulla")
    assert cancelled.state == "cancelled"
    assert cancelled.booking is not None
    assert cancelled.booking.id == third.booking.id
    assert cancelled.booking.status == "cancelled"


@pytest.mark.asyncio
async def test_one_field_at_a_time_flow(session):
    chat = service(session)

    assert "how many" in (await chat.handle("sess-en-1", "I want to book a table")).reply.lower()
    assert "day" in (await chat.handle("sess-en-1", "4")).reply.lower()
    assert "time" in (await chat.handle("sess-en-1", "tomorrow")).reply.lower()
    assert "name" in (await chat.handle("sess-en-1", "20:30")).reply.lower()

    confirming = await chat.handle("sess-en-1", "Jeremy")
    assert confirming.state == "confirming"
    assert "Shall I confirm" in confirming.reply

    confirmed = await chat.handle("sess-en-1", "yes")
    assert confirmed.state == "confirmed"
    assert confirmed.booking is not None
    assert confirmed.booking.customer_name == "Jeremy"


@pytest.mark.asyncio
async def test_spanish_flow_uses_spanish_copy(session):
    chat = service(session)

    reply = await chat.handle(
        "sess-es-1", "Reservar una mesa para 4 mañana a las 20:30"
    )
    assert "nombre" in reply.reply.lower()

    confirming = await chat.handle("sess-es-1", "Ana")
    assert "Confirmas" in confirming.reply

    confirmed = await chat.handle("sess-es-1", "sí")
    assert confirmed.state == "confirmed"
    assert confirmed.booking is not None


@pytest.mark.asyncio
async def test_cancellation_by_code(session):
    chat = service(session)

    await chat.handle("sess-cancel-1", "Vorrei un tavolo per 4 persone domani alle 20:30")
    await chat.handle("sess-cancel-1", "Mario Rossi")
    confirmed = await chat.handle("sess-cancel-1", "sì")
    assert confirmed.booking is not None

    cancelled = await chat.handle(
        "sess-cancel-1", f"Vorrei annullare la prenotazione {confirmed.booking.id}"
    )
    assert cancelled.state == "cancelled"
    assert cancelled.booking is not None
    assert cancelled.booking.status == "cancelled"
