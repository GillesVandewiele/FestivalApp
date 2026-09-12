from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.catalog import Edition, Product, PurchaseUnit
from app.models.order import Order, OrderIn, OrderItem


def test_edition_requires_a_coupon_value():
    e = Edition(
        name="Festival 2026",
        year=2026,
        coupon_value_eur=2.50,
        starts_at=datetime(2026, 7, 1, tzinfo=UTC),
        ends_at=datetime(2026, 7, 3, tzinfo=UTC),
    )
    assert e.coupon_value_eur == 2.50
    assert e.timezone == "Europe/Brussels"
    assert e.id


def test_product_slug_must_be_lowercase_kebab():
    p = Product(
        edition_id="e1", slug="gin-tonic", name="Gin-Tonic", category="cocktail", price_coupons=4
    )
    assert p.slug == "gin-tonic"

    with pytest.raises(ValidationError):
        Product(edition_id="e1", slug="Gin Tonic", name="x", category="cocktail", price_coupons=4)


def test_product_cost_price_is_optional_until_invoices_arrive():
    """Cost is entered after the festival; margin reports must tolerate its absence."""
    p = Product(edition_id="e1", slug="water", name="Water", category="fris", price_coupons=1)
    assert p.cost_price_eur is None
    assert p.purchase_unit is None


def test_product_accepts_a_purchase_unit():
    p = Product(
        edition_id="e1",
        slug="jupiler",
        name="Jupiler",
        category="bier",
        price_coupons=1,
        cost_price_eur=0.62,
        purchase_unit=PurchaseUnit(name="bak", size=24),
    )
    assert p.purchase_unit.size == 24


def test_negative_price_is_rejected():
    with pytest.raises(ValidationError):
        Product(edition_id="e1", slug="x", name="x", category="bier", price_coupons=-1)


def test_order_item_requires_a_positive_quantity():
    with pytest.raises(ValidationError):
        OrderItem(product_id="p1", slug="jupiler", name="Jupiler", qty=0, unit_price_coupons=1)


def test_order_defaults_to_confirmed_with_no_void_block():
    o = Order(
        id="uuid-1",
        edition_id="e1",
        bar_id="b1",
        staff_id="s1",
        device_id="d1",
        items=[],
        total_coupons=0,
        created_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
    )
    assert o.status == "confirmed"
    assert o.void is None


def test_order_in_does_not_accept_a_device_id():
    """device_id is taken from the authenticated device, never from the payload."""
    assert "device_id" not in OrderIn.model_fields


def test_order_in_does_not_accept_a_total():
    """total_coupons is recomputed server-side, never trusted."""
    assert "total_coupons" not in OrderIn.model_fields
