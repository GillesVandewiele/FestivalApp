"""Staff drinks are recorded but never charged.

Every one of these guards the same thing: a free drink must not appear anywhere as
revenue. Getting this wrong inflates every figure the purchasing decision rests on.
"""

from datetime import UTC, datetime

import pytest_asyncio

from app.models.order import Order, OrderItem
from app.services import stats


@pytest_asyncio.fixture
async def with_staff_drinks(db, festival):
    """Four Jupiler taken by Lotte, free."""
    jup = festival["jup"]
    order = Order(
        edition_id=festival["e26"].id,
        bar_id=festival["main"].id,
        staff_id=festival["lotte"].id,
        device_id="dev1",
        items=[
            OrderItem(
                product_id=jup.id, slug="jupiler", name="Jupiler", qty=4, unit_price_coupons=1
            )
        ],
        total_coupons=4,
        created_at=datetime(2026, 7, 1, 18, 0, tzinfo=UTC),
        received_at=datetime(2026, 7, 1, 18, 0, tzinfo=UTC),
        kind="staff",
    )
    await db.orders.insert_one(order.to_mongo())
    return festival


async def test_staff_drinks_do_not_count_as_revenue(db, with_staff_drinks):
    result = await stats.overview(db, with_staff_drinks["e26"].id)

    # Unchanged from the sales-only fixture: 13 drinks, 23 coupons.
    assert result["drinks"] == 13
    assert result["coupons"] == 23
    assert result["revenue_eur"] == 57.5


async def test_staff_drinks_do_not_appear_per_product(db, with_staff_drinks):
    rows = {r["slug"]: r for r in await stats.by_product(db, with_staff_drinks["e26"].id)}
    assert rows["jupiler"]["qty"] == 6  # not 10


async def test_staff_drinks_do_not_appear_per_bar_or_per_staff(db, with_staff_drinks):
    bars = {r["name"]: r for r in await stats.by_bar(db, with_staff_drinks["e26"].id)}
    assert bars["Hoofdpodium"]["qty"] == 7

    staff = {r["name"]: r for r in await stats.by_staff(db, with_staff_drinks["e26"].id)}
    assert staff["Lotte"]["qty"] == 7


async def test_staff_drinks_do_not_appear_per_hour(db, with_staff_drinks):
    rows = await stats.by_hour(db, with_staff_drinks["e26"].id, "Europe/Brussels")
    assert rows[0]["qty"] == 7


async def test_staff_drinks_do_not_reach_the_purchasing_advice(db, with_staff_drinks):
    from app.services import procurement

    rows = {r["slug"]: r for r in await procurement.advise(db, with_staff_drinks["e26"].id)}
    assert rows["jupiler"]["sold"] == 6


async def test_the_staff_report_shows_what_they_took(db, with_staff_drinks):
    result = await stats.staff_consumption(db, with_staff_drinks["e26"].id)

    assert result["drinks"] == 4
    assert result["coupons"] == 4
    assert result["value_eur"] == 10.0  # 4 coupons at 2.50, had they been sold
    assert result["per_product"][0]["name"] == "Jupiler"
    assert result["per_staff"][0]["name"] == "Lotte"
    assert result["per_staff"][0]["drinks"] == 4


async def test_the_staff_report_is_empty_when_nobody_took_anything(db, festival):
    result = await stats.staff_consumption(db, festival["e26"].id)

    assert result["drinks"] == 0
    assert result["value_eur"] == 0
    assert result["per_product"] == []
