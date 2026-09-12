from datetime import datetime

from pydantic import BaseModel, Field

from .common import MongoModel

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]*$"


class Edition(MongoModel):
    name: str
    year: int
    starts_at: datetime
    ends_at: datetime
    timezone: str = "Europe/Brussels"
    coupon_value_eur: float = Field(ge=0)
    is_active: bool = True


class Category(MongoModel):
    """A drink category. Owns its colour, because a user-created category has no
    entry in the POS stylesheet to look one up in."""

    edition_id: str
    slug: str = Field(pattern=SLUG_PATTERN)
    name: str
    colour: str = Field(pattern=r"^#[0-9a-f]{6}$")
    sort_order: int = 0


class Bar(MongoModel):
    edition_id: str
    name: str
    sort_order: int = 0
    active: bool = True


class PurchaseUnit(BaseModel):
    name: str
    size: int = Field(ge=1)


class Product(MongoModel):
    edition_id: str
    slug: str = Field(pattern=SLUG_PATTERN)
    name: str
    category: str
    price_coupons: int = Field(ge=0)

    # Accounting attributes, often only known after the festival.
    cost_price_eur: float | None = Field(default=None, ge=0)
    purchase_unit: PurchaseUnit | None = None
    purchased_qty: int | None = Field(default=None, ge=0)
    leftover_qty: int | None = Field(default=None, ge=0)

    available_at: list[str] = Field(default_factory=list)
    sort_order: int = 0
    active: bool = True


class Staff(MongoModel):
    edition_id: str
    name: str
    active: bool = True
