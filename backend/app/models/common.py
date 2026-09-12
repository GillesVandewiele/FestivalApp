from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def new_id() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class MongoModel(BaseModel):
    """Base for documents. `id` maps to Mongo's `_id`."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(default_factory=new_id, alias="_id")

    def to_mongo(self) -> dict:
        return self.model_dump(by_alias=True)
