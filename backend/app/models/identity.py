from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field

from .common import MongoModel, utcnow


class User(MongoModel):
    email: EmailStr
    password_hash: str
    role: Literal["organizer", "admin"] = "organizer"
    created_at: datetime = Field(default_factory=utcnow)


class Device(MongoModel):
    edition_id: str
    bar_id: str
    label: str
    token_hash: str
    enrolled_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None
