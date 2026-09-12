"""A fixed two-edition dataset. Every expected number in test_stats.py is derived
by hand from this, which is what makes those tests golden."""

from datetime import UTC, datetime

import pytest_asyncio

from app.models.catalog import Bar, Edition, Product, PurchaseUnit, Staff
from app.models.order import Order, OrderItem


def _order(edition, bar, staff, items, when, status="confirmed"):
    return Order(
        edition_id=edition.id,
        bar_id=bar.id,
        staff_id=staff.id,
        device_id="dev1",
        items=items,
        total_coupons=sum(i.qty * i.unit_price_coupons for i in items),
        created_at=when,
        received_at=when,
        status=status,
        void=(
            {"at": when, "by": {"type": "staff", "id": staff.id}, "reason": None}
            if status == "voided"
            else None
        ),
    )


@pytest_asyncio.fixture
async def festival(db):
    """2026: 2 bars, 3 products, 2 staff, 5 orders (one voided).
    2025: same slugs, different quantities, for year-over-year."""
    e26 = Edition(
        name="Festival 2026",
        year=2026,
        coupon_value_eur=2.50,
        starts_at=datetime(2026, 7, 1, tzinfo=UTC),
        ends_at=datetime(2026, 7, 2, tzinfo=UTC),
    )
    e25 = Edition(
        name="Festival 2025",
        year=2025,
        coupon_value_eur=2.00,
        starts_at=datetime(2025, 7, 1, tzinfo=UTC),
        ends_at=datetime(2025, 7, 2, tzinfo=UTC),
    )
    main = Bar(edition_id=e26.id, name="Hoofdpodium")
    cocktail = Bar(edition_id=e26.id, name="Cocktailbar")
    bar25 = Bar(edition_id=e25.id, name="Hoofdpodium")

    jup = Product(
        edition_id=e26.id,
        slug="jupiler",
        name="Jupiler",
        category="bier",
        price_coupons=1,
        cost_price_eur=0.60,
        purchase_unit=PurchaseUnit(name="bak", size=24),
    )
    cava = Product(
        edition_id=e26.id,
        slug="cava",
        name="Cava",
        category="wijn",
        price_coupons=3,
        cost_price_eur=2.40,
        purchase_unit=PurchaseUnit(name="doos", size=6),
    )
    # No cost price: invoices have not arrived. Margin must degrade, not crash.
    water = Product(edition_id=e26.id, slug="water", name="Water", category="fris", price_coupons=1)
    jup25 = Product(
        edition_id=e25.id,
        slug="jupiler",
        name="Jupiler",
        category="bier",
        price_coupons=1,
        cost_price_eur=0.55,
    )
    cava25 = Product(
        edition_id=e25.id,
        slug="cava",
        name="Cava",
        category="wijn",
        price_coupons=3,
        cost_price_eur=2.20,
    )

    lotte = Staff(edition_id=e26.id, name="Lotte")
    jonas = Staff(edition_id=e26.id, name="Jonas")
    staff25 = Staff(edition_id=e25.id, name="Oud")

    def item(p, qty):
        return OrderItem(
            product_id=p.id, slug=p.slug, name=p.name, qty=qty, unit_price_coupons=p.price_coupons
        )

    # Europe/Brussels is UTC+2 in July, so 18:00 UTC is 20:00 local.
    orders = [
        _order(
            e26,
            main,
            lotte,
            [item(jup, 3), item(water, 2)],
            datetime(2026, 7, 1, 18, 0, tzinfo=UTC),
        ),
        _order(e26, main, lotte, [item(jup, 2)], datetime(2026, 7, 1, 18, 30, tzinfo=UTC)),
        _order(e26, cocktail, jonas, [item(cava, 4)], datetime(2026, 7, 1, 19, 0, tzinfo=UTC)),
        _order(
            e26,
            cocktail,
            jonas,
            [item(jup, 1), item(cava, 1)],
            datetime(2026, 7, 1, 19, 15, tzinfo=UTC),
        ),
        # VOIDED: must not appear in any total.
        _order(
            e26,
            main,
            lotte,
            [item(jup, 99)],
            datetime(2026, 7, 1, 20, 0, tzinfo=UTC),
            status="voided",
        ),
    ]
    orders25 = [
        _order(
            e25,
            bar25,
            staff25,
            [item(jup25, 4), item(cava25, 2)],
            datetime(2025, 7, 1, 18, 0, tzinfo=UTC),
        ),
    ]

    await db.editions.insert_many([e26.to_mongo(), e25.to_mongo()])
    await db.bars.insert_many([main.to_mongo(), cocktail.to_mongo(), bar25.to_mongo()])
    await db.products.insert_many([p.to_mongo() for p in (jup, cava, water, jup25, cava25)])
    await db.staff.insert_many([lotte.to_mongo(), jonas.to_mongo(), staff25.to_mongo()])
    await db.orders.insert_many([o.to_mongo() for o in orders + orders25])

    return {
        "e26": e26,
        "e25": e25,
        "main": main,
        "cocktail": cocktail,
        "jup": jup,
        "cava": cava,
        "water": water,
        "lotte": lotte,
        "jonas": jonas,
    }
