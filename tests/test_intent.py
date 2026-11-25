from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.intent import MockIntentParser

TZ = ZoneInfo("Europe/Rome")
NOW = datetime(2026, 11, 25, 10, 0, tzinfo=TZ)


@pytest.mark.asyncio
async def test_italian_booking_phrase():
    intent = await MockIntentParser().parse(
        "Vorrei prenotare un tavolo per 4 persone domani alle 20:30", NOW
    )

    assert intent.action == "book"
    assert intent.party_size == 4
    assert intent.date == date(2026, 11, 26)
    assert intent.time == time(20, 30)


@pytest.mark.asyncio
async def test_english_booking_phrase():
    intent = await MockIntentParser().parse("Book a table for two tomorrow at 8pm", NOW)

    assert intent.action == "book"
    assert intent.party_size == 2
    assert intent.date == date(2026, 11, 26)
    assert intent.time == time(20, 0)


@pytest.mark.asyncio
async def test_spanish_booking_phrase():
    intent = await MockIntentParser().parse(
        "Reservar una mesa para 4 mañana a las 20:30", NOW
    )

    assert intent.action == "book"
    assert intent.party_size == 4
    assert intent.date == date(2026, 11, 26)
    assert intent.time == time(20, 30)


@pytest.mark.asyncio
async def test_tonight_and_name():
    intent = await MockIntentParser().parse("Per stasera alle 21, a nome di Mario", NOW)

    assert intent.action == "book"
    assert intent.date == date(2026, 11, 25)
    assert intent.time == time(21, 0)
    assert intent.customer_name == "Mario"


@pytest.mark.asyncio
async def test_cancel_phrase():
    intent = await MockIntentParser().parse("Vorrei annullare la prenotazione", NOW)

    assert intent.action == "cancel"
