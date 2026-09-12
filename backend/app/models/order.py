from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import MongoModel

OrderStatus = Literal["confirmed", "voided"]
# A staff drink is recorded but never charged, and never counted as revenue.
OrderKind = Literal["sale", "staff"]


class OrderItem(BaseModel):
    product_id: str
    slug: str
    name: str  # snapshotted at sale time
    qty: int = Field(ge=1)
    unit_price_coupons: int = Field(ge=0)  # snapshotted at sale time


class VoidActor(BaseModel):
    type: Literal["staff", "user"]
    id: str


class VoidInfo(BaseModel):
    at: datetime
    by: VoidActor
    reason: str | None = None  # required for an organiser void


class OrderIn(BaseModel):
    """What a tablet sends. Deliberately excludes device_id and total_coupons."""

    model_config = ConfigDict(extra="forbid")

    id: str
    edition_id: str
    bar_id: str
    staff_id: str
    items: list[OrderItem]
    created_at: datetime
    status: OrderStatus = "confirmed"
    kind: OrderKind = "sale"
    void: VoidInfo | None = None


class Order(MongoModel):
    edition_id: str
    bar_id: str
    staff_id: str
    device_id: str
    items: list[OrderItem]
    total_coupons: int = Field(ge=0)
    created_at: datetime
    received_at: datetime
    status: OrderStatus = "confirmed"
    kind: OrderKind = "sale"
    void: VoidInfo | None = None


class StockoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    product_id: str
    out_at: datetime
    back_at: datetime | None = None


class Stockout(MongoModel):
    edition_id: str
    bar_id: str
    product_id: str
    slug: str
    out_at: datetime
    back_at: datetime | None = None
