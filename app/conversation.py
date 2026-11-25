from __future__ import annotations

import re
from datetime import date, datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.booking import (
    BookingError,
    BookingService,
    NotFound,
    SlotUnavailable,
    booking_to_out,
    local_time_of,
)
from app.config import settings
from app.intent import MockIntentParser, normalize
from app.models import Conversation
from app.schemas import ChatResponse

TZ = ZoneInfo(settings.timezone)

YES_WORDS = {
    "si",
    "sì",
    "yes",
    "yep",
    "ok",
    "okay",
    "confermo",
    "confirmo",
    "va bene",
    "perfetto",
    "certo",
    "dale",
    "confirm",
}
NO_WORDS = {"no", "nope", "non", "annulla", "cancel", "cancella"}

LANG_HINTS: dict[str, tuple[str, ...]] = {
    "it": (
        "vorrei",
        "prenotare",
        "prenotazione",
        "tavolo",
        "domani",
        "dopodomani",
        "stasera",
        "persone",
        "grazie",
        "confermo",
        "sera",
        "pranzo",
        "cena",
        "alle",
    ),
    "en": (
        "book",
        "booking",
        "table",
        "tomorrow",
        "tonight",
        "people",
        "thanks",
        "confirm",
        "evening",
        "lunch",
        "dinner",
        "at",
    ),
    "es": (
        "reservar",
        "reserva",
        "mesa",
        "manana",
        "mañana",
        "personas",
        "gracias",
        "confirmo",
        "noche",
        "almuerzo",
        "cena",
        "para",
    ),
}

COPY: dict[str, dict[str, str]] = {
    "it": {
        "party_size": "Per quante persone?",
        "date": "Per quale giorno? (es. domani, 25/11)",
        "time": "A che ora? (es. 20:30)",
        "name": "A che nome segno la prenotazione?",
        "change": "Va bene. Dimmi cosa vuoi cambiare: data, ora o numero di persone.",
        "confirm": "Perfetto: {party} persone il {date} alle {time}, a nome {name}. Confermi?",
        "confirmed": "Prenotazione confermata. Codice {code}. Ti aspettiamo da {restaurant}, tavolo {table}.",
        "no_availability": "A quell'ora non ho disponibilità. Gli orari più vicini sono: {slots}. Quale preferisci?",
        "slot_taken": "Quel tavolo è appena stato preso. Vuoi provare un altro orario?",
        "unknown": "Non sono sicuro di aver capito. Vuoi prenotare un tavolo? Dimmi per quante persone e quando.",
        "cancelled": "Prenotazione {code} annullata.",
        "cancel_ask": "Per annullare, inviami il codice della prenotazione.",
        "not_found": "Non trovo quella prenotazione. Controlla il codice.",
        "availability": "Ecco i primi orari disponibili: {slots}. Dimmi quale preferisci.",
        "past": "Quell'orario è già passato. Scegli un altro orario.",
        "error": "Non riesco a confermare la prenotazione. Riprova tra poco.",
        "welcome": "Ciao. Posso prenotare un tavolo per te. Dimmi per quante persone, che giorno e a che ora.",
    },
    "en": {
        "party_size": "For how many people?",
        "date": "Which day? (e.g. tomorrow, 25/11)",
        "time": "What time? (e.g. 20:30)",
        "name": "Under what name should I book it?",
        "change": "No problem. Tell me what to change: date, time or party size.",
        "confirm": "Great: {party} people on {date} at {time}, under {name}. Shall I confirm?",
        "confirmed": "Booking confirmed. Code {code}. We'll see you at {restaurant}, table {table}.",
        "no_availability": "I don't have availability at that time. The closest options are: {slots}. Which one works?",
        "slot_taken": "That table was just taken. Would you like to try another time?",
        "unknown": "I'm not sure I understood. Would you like to book a table? Tell me how many people and when.",
        "cancelled": "Booking {code} cancelled.",
        "cancel_ask": "To cancel, send me the booking code.",
        "not_found": "I can't find that booking. Please check the code.",
        "availability": "These are the first available times: {slots}. Tell me which one you prefer.",
        "past": "That time is already in the past. Please choose another time.",
        "error": "I couldn't confirm the booking. Please try again shortly.",
        "welcome": "Hi. I can book a table for you. Tell me how many people, which day and what time.",
    },
    "es": {
        "party_size": "¿Para cuántas personas?",
        "date": "¿Para qué día? (ej. mañana, 25/11)",
        "time": "¿A qué hora? (ej. 20:30)",
        "name": "¿A nombre de quién?",
        "change": "Perfecto. Dime qué quieres cambiar: fecha, hora o número de personas.",
        "confirm": "Perfecto: {party} personas el {date} a las {time}, a nombre de {name}. ¿Confirmas?",
        "confirmed": "Reserva confirmada. Código {code}. Te esperamos en {restaurant}, mesa {table}.",
        "no_availability": "A esa hora no tengo disponibilidad. Los horarios más cercanos son: {slots}. ¿Cuál prefieres?",
        "slot_taken": "Esa mesa acaba de ocuparse. ¿Quieres probar otra hora?",
        "unknown": "No estoy seguro de haber entendido. ¿Quieres reservar una mesa? Dime para cuántas personas y cuándo.",
        "cancelled": "Reserva {code} anulada.",
        "cancel_ask": "Para anular, envíame el código de la reserva.",
        "not_found": "No encuentro esa reserva. Revisa el código.",
        "availability": "Estos son los primeros horarios disponibles: {slots}. Dime cuál prefieres.",
        "past": "Esa hora ya pasó. Elige otra hora.",
        "error": "No pude confirmar la reserva. Inténtalo de nuevo en un momento.",
        "welcome": "Hola. Puedo reservarte una mesa. Dime para cuántas personas, qué día y a qué hora.",
    },
}


def detect_language(text: str) -> str:
    low = normalize(text)
    scores: dict[str, int] = {}
    for lang, words in LANG_HINTS.items():
        scores[lang] = sum(1 for word in words if re.search(rf"\b{re.escape(word)}\b", low))
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "es"


def _clean_words(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", normalize(text))
    return re.sub(r"\s+", " ", cleaned).strip()


def is_yes(text: str) -> bool:
    clean = _clean_words(text)
    return clean in YES_WORDS or any(clean.startswith(f"{word} ") for word in YES_WORDS)


def is_no(text: str) -> bool:
    clean = _clean_words(text)
    return clean in NO_WORDS or any(clean.startswith(f"{word} ") for word in NO_WORDS)


def copy_for(lang: str) -> dict[str, str]:
    return COPY.get(lang, COPY["it"])


class ConversationService:
    def __init__(
        self,
        session: AsyncSession,
        parser: MockIntentParser | None = None,
        now_provider=None,
    ):
        self.session = session
        self.parser = parser or MockIntentParser()
        self.booking = BookingService(session)
        self.now_provider = now_provider or (lambda: datetime.now(TZ))

    async def handle(self, session_id: str, message: str) -> ChatResponse:
        now = self.now_provider()
        conv = await self.session.get(Conversation, session_id)
        if conv is None:
            conv = Conversation(session_id=session_id, state="idle", data={})
            self.session.add(conv)
            await self.session.flush()

        data = dict(conv.data or {})
        text = " ".join(message.split()).strip()
        low = normalize(text)
        lang = data.get("lang") or detect_language(text)
        data["lang"] = lang
        t = copy_for(lang)

        # A finished conversation can be reopened. Repeating "yes" returns the same receipt.
        if conv.state == "confirmed" and is_yes(low) and data.get("last_booking_id"):
            booking = await self.booking.get_booking(data["last_booking_id"])
            return ChatResponse(
                session_id=session_id,
                reply=t["confirmed"].format(
                    code=booking.id,
                    restaurant=booking.restaurant.name,
                    table=booking.table.name,
                ),
                state=conv.state,
                booking=booking_to_out(booking),
            )
        if conv.state in {"confirmed", "cancelled"}:
            last_booking_id = data.get("last_booking_id")
            conv.state = "idle"
            data = {"lang": lang}
            if last_booking_id:
                # Keep it so a follow-up "annulla" can cancel the last booking.
                data["last_booking_id"] = last_booking_id

        if conv.state == "confirming":
            if is_yes(low):
                return await self._confirm(conv, data, lang, session_id)
            if is_no(low):
                conv.state = "collecting"
                data.pop("proposed", None)
                data.pop("idempotency_key", None)
                conv.data = data
                await self.session.commit()
                return ChatResponse(session_id=session_id, reply=t["change"], state=conv.state)

        if conv.state == "asking_name":
            if is_no(low):
                conv.state = "collecting"
                data.pop("proposed", None)
                data.pop("idempotency_key", None)
                conv.data = data
                await self.session.commit()
                return ChatResponse(session_id=session_id, reply=t["change"], state=conv.state)
            data["customer_name"] = text[:120]
            conv.state = "collecting"

        intent = await self.parser.parse(text, now)

        if intent.action == "cancel":
            return await self._handle_cancel(conv, data, lang, session_id, text)

        if intent.action == "availability":
            return await self._handle_availability(conv, data, lang, session_id, now)

        if intent.party_size is not None:
            data["party_size"] = intent.party_size
        if intent.date is not None:
            data["date"] = intent.date.isoformat()
        if intent.time is not None:
            data["time"] = intent.time.strftime("%H:%M")
        if intent.customer_name:
            data["customer_name"] = intent.customer_name
        if intent.restaurant_name:
            data["restaurant_name"] = intent.restaurant_name

        # Short replies ("4", "20:30") are common when the bot asks one field at a time.
        self._fill_short_reply(data, low)

        missing = [field for field in ("party_size", "date", "time") if not data.get(field)]
        if missing:
            conv.state = "collecting"
            conv.data = data
            await self.session.commit()
            return ChatResponse(
                session_id=session_id,
                reply=t[missing[0]],
                state=conv.state,
                missing=missing,
            )

        try:
            day = date.fromisoformat(data["date"])
            wanted = dt_time.fromisoformat(data["time"])
        except ValueError:
            data.pop("date", None)
            data.pop("time", None)
            conv.state = "collecting"
            conv.data = data
            await self.session.commit()
            return ChatResponse(
                session_id=session_id,
                reply=t["date"],
                state=conv.state,
                missing=["date", "time"],
            )

        restaurant = await self.booking.get_restaurant(name=data.get("restaurant_name"))
        local_now = now.astimezone(ZoneInfo(restaurant.timezone))
        if day < local_now.date() or (day == local_now.date() and wanted <= local_now.time()):
            data.pop("time", None)
            conv.state = "collecting"
            conv.data = data
            await self.session.commit()
            return ChatResponse(session_id=session_id, reply=t["past"], state=conv.state, missing=["time"])

        party_size = int(data["party_size"])
        slots = await self.booking.availability(day, party_size, restaurant=restaurant)
        slots = [slot for slot in slots if slot.start_at > now]
        exact = [slot for slot in slots if local_time_of(slot, restaurant.timezone) == wanted]

        if not exact:
            alternatives = await self._alternatives(restaurant, day, party_size, now)
            if alternatives:
                data["time"] = None
                data["suggested"] = True
                conv.state = "collecting"
                conv.data = data
                await self.session.commit()
                return ChatResponse(
                    session_id=session_id,
                    reply=t["no_availability"].format(
                        slots=self._format_suggestions(alternatives, restaurant.timezone)
                    ),
                    state=conv.state,
                    missing=["time"],
                )
            data.pop("date", None)
            data.pop("time", None)
            conv.state = "collecting"
            conv.data = data
            await self.session.commit()
            return ChatResponse(
                session_id=session_id,
                reply=t["no_availability"].format(slots="—"),
                state=conv.state,
                missing=["date", "time"],
            )

        slot = exact[0]
        data["restaurant_id"] = restaurant.id
        data["proposed"] = {
            "table_id": slot.table_id,
            "start_at": slot.start_at.isoformat(),
            "end_at": slot.end_at.isoformat(),
        }
        data["idempotency_key"] = (
            f"{session_id}:{slot.table_id}:{slot.start_at.isoformat()}:{party_size}"
        )

        if not data.get("customer_name"):
            conv.state = "asking_name"
            conv.data = data
            await self.session.commit()
            return ChatResponse(
                session_id=session_id,
                reply=t["name"],
                state=conv.state,
                missing=["customer_name"],
            )

        conv.state = "confirming"
        data["suggested"] = False
        conv.data = data
        await self.session.commit()
        local_start = slot.start_at.astimezone(ZoneInfo(restaurant.timezone))
        return ChatResponse(
            session_id=session_id,
            reply=t["confirm"].format(
                party=party_size,
                date=local_start.strftime("%d/%m/%Y"),
                time=local_start.strftime("%H:%M"),
                name=data["customer_name"],
            ),
            state=conv.state,
        )

    async def _confirm(
        self, conv: Conversation, data: dict, lang: str, session_id: str
    ) -> ChatResponse:
        t = copy_for(lang)
        proposed = data.get("proposed")
        if not proposed:
            conv.state = "collecting"
            conv.data = data
            await self.session.commit()
            return ChatResponse(session_id=session_id, reply=t["time"], state=conv.state)

        try:
            booking = await self.booking.create_booking(
                restaurant_id=int(data["restaurant_id"]),
                table_id=int(proposed["table_id"]),
                customer_name=data["customer_name"],
                party_size=int(data["party_size"]),
                start_at=datetime.fromisoformat(proposed["start_at"]),
                idempotency_key=data["idempotency_key"],
            )
        except SlotUnavailable:
            conv.state = "collecting"
            data.pop("proposed", None)
            data.pop("idempotency_key", None)
            data["time"] = None
            conv.data = data
            await self.session.commit()
            return ChatResponse(session_id=session_id, reply=t["slot_taken"], state=conv.state)
        except (BookingError, KeyError, ValueError):
            conv.state = "collecting"
            conv.data = data
            await self.session.commit()
            return ChatResponse(session_id=session_id, reply=t["error"], state=conv.state)

        conv.state = "confirmed"
        conv.data = {"lang": lang, "last_booking_id": booking.id}
        await self.session.commit()
        return ChatResponse(
            session_id=session_id,
            reply=t["confirmed"].format(
                code=booking.id,
                restaurant=booking.restaurant.name,
                table=booking.table.name,
            ),
            state=conv.state,
            booking=booking_to_out(booking),
        )

    async def _handle_cancel(
        self, conv: Conversation, data: dict, lang: str, session_id: str, text: str
    ) -> ChatResponse:
        t = copy_for(lang)
        match = re.search(
            r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
            text,
            re.IGNORECASE,
        )
        booking_id = match.group(1) if match else data.get("last_booking_id")
        if not booking_id:
            conv.data = data
            await self.session.commit()
            return ChatResponse(session_id=session_id, reply=t["cancel_ask"], state=conv.state)
        try:
            booking = await self.booking.cancel_booking(booking_id)
        except NotFound:
            conv.data = data
            await self.session.commit()
            return ChatResponse(session_id=session_id, reply=t["not_found"], state=conv.state)

        conv.state = "cancelled"
        conv.data = {"lang": lang, "last_booking_id": booking.id}
        await self.session.commit()
        return ChatResponse(
            session_id=session_id,
            reply=t["cancelled"].format(code=booking.id),
            state=conv.state,
            booking=booking_to_out(booking),
        )

    async def _handle_availability(
        self, conv: Conversation, data: dict, lang: str, session_id: str, now: datetime
    ) -> ChatResponse:
        t = copy_for(lang)
        missing = [field for field in ("party_size", "date") if not data.get(field)]
        if missing:
            conv.state = "collecting"
            conv.data = data
            await self.session.commit()
            return ChatResponse(
                session_id=session_id,
                reply=t[missing[0]],
                state=conv.state,
                missing=missing,
            )

        try:
            day = date.fromisoformat(data["date"])
        except ValueError:
            data.pop("date", None)
            conv.state = "collecting"
            conv.data = data
            await self.session.commit()
            return ChatResponse(session_id=session_id, reply=t["date"], state=conv.state, missing=["date"])

        restaurant = await self.booking.get_restaurant(name=data.get("restaurant_name"))
        slots = await self.booking.availability(day, int(data["party_size"]), restaurant=restaurant)
        slots = [slot for slot in slots if slot.start_at > now]
        alternatives = self._unique_slots(slots)
        if not alternatives:
            alternatives = await self._alternatives(restaurant, day, int(data["party_size"]), now)

        if not alternatives:
            data.pop("date", None)
            conv.state = "collecting"
            conv.data = data
            await self.session.commit()
            return ChatResponse(
                session_id=session_id,
                reply=t["no_availability"].format(slots="—"),
                state=conv.state,
                missing=["date"],
            )

        conv.state = "collecting"
        data["suggested"] = True
        conv.data = data
        await self.session.commit()
        return ChatResponse(
            session_id=session_id,
            reply=t["availability"].format(
                slots=self._format_suggestions(alternatives, restaurant.timezone)
            ),
            state=conv.state,
        )

    def _fill_short_reply(self, data: dict, low: str) -> None:
        missing = [field for field in ("party_size", "date", "time") if not data.get(field)]
        if not missing:
            return
        field = missing[0]
        if field == "party_size":
            match = re.fullmatch(r"(\d{1,2})", low)
            if match:
                value = int(match.group(1))
                if 1 <= value <= 30:
                    data["party_size"] = value
                    return
            for word, value in {
                "uno": 1,
                "one": 1,
                "un": 1,
                "due": 2,
                "two": 2,
                "dos": 2,
                "tre": 3,
                "three": 3,
                "tres": 3,
                "quattro": 4,
                "four": 4,
                "cuatro": 4,
                "cinque": 5,
                "five": 5,
                "cinco": 5,
                "sei": 6,
                "six": 6,
                "seis": 6,
                "sette": 7,
                "seven": 7,
                "siete": 7,
                "otto": 8,
                "eight": 8,
                "ocho": 8,
                "nove": 9,
                "nine": 9,
                "nueve": 9,
                "dieci": 10,
                "ten": 10,
                "diez": 10,
            }.items():
                if low == word:
                    data["party_size"] = value
                    return
        if field == "time":
            match = re.fullmatch(r"(\d{1,2})(?:[:.](\d{2}))?", low)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2) or 0)
                if 6 <= hour <= 11:
                    hour += 12
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    data["time"] = f"{hour:02d}:{minute:02d}"

    async def _alternatives(
        self,
        restaurant,
        start_day: date,
        party_size: int,
        now: datetime,
        days: int = 4,
        limit: int = 5,
    ):
        results = []
        for offset in range(days):
            day = start_day + timedelta(days=offset)
            slots = await self.booking.availability(day, party_size, restaurant=restaurant)
            slots = [slot for slot in slots if slot.start_at > now]
            results.extend(self._unique_slots(slots))
            if len(results) >= limit:
                break
        return results[:limit]

    @staticmethod
    def _unique_slots(slots) -> list:
        seen: set[datetime] = set()
        unique = []
        for slot in slots:
            if slot.start_at in seen:
                continue
            seen.add(slot.start_at)
            unique.append(slot)
        return unique

    @staticmethod
    def _format_suggestions(slots, tz_name: str) -> str:
        parts = []
        for slot in slots:
            local = slot.start_at.astimezone(ZoneInfo(tz_name))
            parts.append(local.strftime("%d/%m %H:%M"))
        return " · ".join(parts)
