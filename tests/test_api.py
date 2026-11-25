from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

TZ = ZoneInfo("Europe/Rome")


@pytest.mark.asyncio
async def test_health_and_pages(client):
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    home = await client.get("/")
    assert home.status_code == 200
    assert "Artusi" in home.text

    admin = await client.get("/admin")
    assert admin.status_code == 200
    assert "Comandas" in admin.text


@pytest.mark.asyncio
async def test_chat_api_creates_booking_and_admin_sees_it(client):
    first = await client.post(
        "/chat",
        json={
            "session_id": "api-session-1",
            "message": "Vorrei un tavolo per 4 persone domani alle 20:30",
        },
    )
    assert first.status_code == 200
    assert first.json()["state"] == "asking_name"

    second = await client.post(
        "/chat",
        json={"session_id": "api-session-1", "message": "Mario Rossi"},
    )
    assert second.status_code == 200
    assert second.json()["state"] == "confirming"

    third = await client.post(
        "/chat",
        json={"session_id": "api-session-1", "message": "sì"},
    )
    assert third.status_code == 200
    payload = third.json()
    assert payload["state"] == "confirmed"
    booking_id = payload["booking"]["id"]

    bookings = await client.get("/api/bookings")
    assert bookings.status_code == 200
    assert any(item["id"] == booking_id for item in bookings.json())

    admin = await client.get("/admin")
    assert admin.status_code == 200
    assert booking_id[:8].upper() in admin.text


@pytest.mark.asyncio
async def test_availability_and_cancel_api(client):
    day = (datetime.now(TZ) + timedelta(days=2)).date().isoformat()
    availability = await client.get(
        "/api/availability", params={"day": day, "party_size": 4}
    )
    assert availability.status_code == 200
    slots = availability.json()
    assert slots

    create = await client.post(
        "/chat",
        json={
            "session_id": "api-session-2",
            "message": "Vorrei un tavolo per 4 persone dopodomani alle 20:30",
        },
    )
    assert create.status_code == 200
    await client.post(
        "/chat", json={"session_id": "api-session-2", "message": "Anna Bianchi"}
    )
    confirmed = await client.post(
        "/chat", json={"session_id": "api-session-2", "message": "sì"}
    )
    booking_id = confirmed.json()["booking"]["id"]

    cancelled = await client.post(
        f"/api/bookings/{booking_id}/cancel", json={"reason": "test"}
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_admin_cancel_form_redirects_and_hides_booking(client):
    day = (datetime.now(TZ) + timedelta(days=3)).date().isoformat()
    await client.post(
        "/chat",
        json={
            "session_id": "api-session-3",
            "message": f"Vorrei un tavolo per 2 persone il {day} alle 20:00",
        },
    )
    await client.post(
        "/chat", json={"session_id": "api-session-3", "message": "Giulia Verdi"}
    )
    confirmed = await client.post(
        "/chat", json={"session_id": "api-session-3", "message": "sì"}
    )
    booking_id = confirmed.json()["booking"]["id"]

    response = await client.post(
        f"/admin/bookings/{booking_id}/cancel",
        data={"day": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303

    bookings = await client.get("/api/bookings")
    assert all(item["id"] != booking_id for item in bookings.json())


@pytest.mark.asyncio
async def test_reminders_endpoint(client):
    response = await client.get("/api/reminders/due")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_admin_and_booking_api_can_be_password_protected(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "demo_basic_auth", "demo:secret")

    assert (await client.get("/")).status_code == 200
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/admin")).status_code == 401
    assert (await client.get("/api/bookings")).status_code == 401

    authorized = await client.get("/admin", auth=("demo", "secret"))
    assert authorized.status_code == 200
    assert "Comandas" in authorized.text
