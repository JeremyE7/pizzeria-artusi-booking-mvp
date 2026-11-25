from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from datetime import time as time_type

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1000)


class BookingOut(BaseModel):
    id: str
    restaurant: str
    table: str
    customer_name: str
    party_size: int
    start_at: datetime
    end_at: datetime
    status: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    state: str
    missing: list[str] = Field(default_factory=list)
    booking: BookingOut | None = None


class AvailabilitySlot(BaseModel):
    start_at: datetime
    end_at: datetime
    table_id: int
    table_name: str
    capacity: int


class CancelRequest(BaseModel):
    reason: str | None = None


class Intent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: str = "unknown"
    party_size: int | None = None
    date: date_type | None = None
    time: time_type | None = None
    customer_name: str | None = None
    restaurant_name: str | None = None
    confidence: float = 0.0
