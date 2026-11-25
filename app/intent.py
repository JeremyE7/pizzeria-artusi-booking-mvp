from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, time, timedelta

import httpx

from app.config import settings
from app.schemas import Intent


def strip_accents(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", strip_accents(value).lower()).strip()


WORD_NUMBERS = {
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
}

WEEKDAYS = {
    "lunedi": 0,
    "martedi": 1,
    "mercoledi": 2,
    "giovedi": 3,
    "venerdi": 4,
    "sabato": 5,
    "domenica": 6,
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "domingo": 6,
}

RELATIVE_DAYS = {
    "oggi": 0,
    "today": 0,
    "hoy": 0,
    "stasera": 0,
    "tonight": 0,
    "esta noche": 0,
    "domani": 1,
    "tomorrow": 1,
    "manana": 1,
    "dopodomani": 2,
    "day after tomorrow": 2,
    "pasado manana": 2,
}


class MockIntentParser:
    """Deterministic multilingual parser used in the demo and tests."""

    async def parse(self, message: str, now: datetime) -> Intent:
        low = normalize(message)
        action = "unknown"
        if re.search(r"\b(cancel|annull\w*|disdic\w*|delete)\b", low):
            action = "cancel"
        elif re.search(r"\b(disponib\w*|availability|tavoli liberi|free table|mesa libre|orari)\b", low):
            action = "availability"
        elif re.search(r"\b(prenot\w*|book|reserv\w*|tavolo|table|mesa)\b", low):
            action = "book"

        party_size = self._party_size(low)
        requested_date = self._date(low, now)
        requested_time = self._time(low)
        customer_name = self._name(message)
        restaurant_name = None
        if "artusi" in low or "ħabibot" in low:
            restaurant_name = "Artusi Ħabibot"
        elif "trattoria demo" in low:
            restaurant_name = "Trattoria Demo"

        if action == "unknown" and any((party_size, requested_date, requested_time)):
            action = "book"

        confidence = 0.25
        if action == "book":
            confidence = 0.9 if party_size and requested_date and requested_time else 0.6
        elif action in {"cancel", "availability"}:
            confidence = 0.75

        return Intent(
            action=action,
            party_size=party_size,
            date=requested_date,
            time=requested_time,
            customer_name=customer_name,
            restaurant_name=restaurant_name,
            confidence=confidence,
        )

    def _party_size(self, low: str) -> int | None:
        patterns = [
            r"(?:per|for|para)\s+(\d{1,2})",
            r"(\d{1,2})\s*(?:persone|people|personas|pax|guests|comensales)",
        ]
        for pattern in patterns:
            match = re.search(pattern, low)
            if match:
                value = int(match.group(1))
                if 1 <= value <= 30:
                    return value
        for pattern in [
            r"(?:per|for|para)\s+([a-z]+)",
            r"([a-z]+)\s+(?:persone|people|personas)",
        ]:
            match = re.search(pattern, low)
            if match and match.group(1) in WORD_NUMBERS:
                return WORD_NUMBERS[match.group(1)]
        return None

    def _date(self, low: str, now: datetime) -> date | None:
        today = now.date()

        match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", low)
        if match:
            try:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError:
                pass

        match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", low)
        if match:
            day, month = int(match.group(1)), int(match.group(2))
            year = int(match.group(3)) if match.group(3) else today.year
            if year < 100:
                year += 2000
            try:
                parsed = date(year, month, day)
                if parsed < today:
                    parsed = date(year + 1, month, day)
                return parsed
            except ValueError:
                pass

        for phrase, offset in sorted(
            RELATIVE_DAYS.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if re.search(rf"\b{re.escape(phrase)}\b", low):
                return today + timedelta(days=offset)

        for name, weekday in WEEKDAYS.items():
            if re.search(rf"\b{name}\b", low):
                delta = (weekday - today.weekday()) % 7
                if delta == 0:
                    delta = 7
                return today + timedelta(days=delta)
        return None

    def _time(self, low: str) -> time | None:
        if re.search(r"\b(mezzogiorno|noon|mediodia)\b", low):
            return time(12, 0)
        if re.search(r"\b(mezzanotte|midnight)\b", low):
            return time(0, 0)

        hour: int | None = None
        minute = 0

        match = re.search(r"\b(\d{1,2})[:.](\d{2})\b", low)
        if match:
            hour, minute = int(match.group(1)), int(match.group(2))
        else:
            match = re.search(r"\b(\d{1,2})\s*(am|pm)\b", low)
            if match:
                hour = int(match.group(1)) % 12
                if match.group(2) == "pm":
                    hour += 12
            else:
                match = re.search(r"\b(?:alle|at|a las)\s+(\d{1,2})(?::(\d{2}))?\b", low)
                if match:
                    hour = int(match.group(1))
                    minute = int(match.group(2) or 0)
                    if hour < 12:
                        if re.search(r"\b(pm|sera|evening|notte|noche)\b", low):
                            hour += 12
                        elif re.search(r"\b(am|mattina|morning|pranzo|lunch|mediodia)\b", low):
                            pass
                        elif 6 <= hour <= 11:
                            hour += 12

        if hour is None:
            if re.search(r"\b(pranzo|lunch|almuerzo)\b", low):
                return time(13, 0)
            if re.search(r"\b(cena|dinner|cena)\b", low):
                return time(20, 0)
            return None

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return time(hour, minute)

    def _name(self, message: str) -> str | None:
        pattern = re.compile(
            r"(?:a nome di|mi chiamo|my name is|me llamo|sono)\s+([A-Za-zÀ-ÿ' -]{2,60})",
            re.IGNORECASE,
        )
        match = pattern.search(message)
        if not match:
            return None
        name = re.sub(r"\s+", " ", match.group(1)).strip(" .,!?:;")
        for stop in [" e ", " and ", " y ", " per ", " for ", " para "]:
            if stop in f" {name.lower()} ":
                name = re.split(stop, f" {name} ")[0].strip()
        return name.title() if name else None


class OpenRouterIntentParser:
    """Optional real LLM adapter. Falls back to the deterministic parser."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.fallback = MockIntentParser()

    async def parse(self, message: str, now: datetime) -> Intent:
        system = (
            "You extract restaurant booking intents. Return only JSON with keys: "
            "action (book|cancel|availability|unknown), party_size (int|null), "
            "date (YYYY-MM-DD|null), time (HH:MM|null), customer_name (string|null), "
            "restaurant_name (string|null), confidence (0..1). "
            f"Today is {now.date().isoformat()} in {settings.timezone}. "
            "Resolve relative dates like tomorrow/tonight. Do not invent fields."
        )
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "temperature": 0,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": message},
                        ],
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return Intent.model_validate(json.loads(content))
        except Exception:
            return await self.fallback.parse(message, now)


def build_parser() -> MockIntentParser | OpenRouterIntentParser:
    if settings.llm_provider == "openrouter" and settings.openrouter_api_key:
        return OpenRouterIntentParser(settings.openrouter_api_key, settings.openrouter_model)
    return MockIntentParser()
