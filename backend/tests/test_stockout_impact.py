"""Estimating what a drink would have sold if it had not run out.

The method is a share projection: the product's share of everything sold before it
ran out, applied to everything sold while it was gone. Simple enough to explain to
whoever signs the purchase order, which is the point.
"""

from datetime import UTC, datetime, timedelta

import pytest_asyncio

from app.models.order import Order, OrderItem, Stockout
from app.services import procurement, stats

START = datetime(2026, 7, 1, 18, 0, tzinfo=UTC)


def _order(festival, product, qty, minutes):
    when = START + timedelta(minutes=minutes)
    return Order(
        edition_id=festival["e26"].id,
        bar_id=festival["main"].id,
        staff_id=festival["lotte"].id,
        device_id="d",
        items=[
            OrderItem(
                product_id=product.id,
                slug=product.slug,
                name=product.name,
                qty=qty,
                unit_price_coupons=product.price_coupons,
            )
        ],
        total_coupons=qty * product.price_coupons,
        created_at=when,
        received_at=when,
    ).to_mongo()


@pytest_asyncio.fixture
async def ran_dry(db, festival):
    """Jupiler is half of everything for two hours, then runs out and the bar keeps
    selling 100 other drinks."""
    await db.orders.delete_many({"edition_id": festival["e26"].id})

    orders = []
    for m in range(0, 120, 10):
        orders.append(_order(festival, festival["jup"], 10, m))  # 120 jupiler
        orders.append(_order(festival, festival["cava"], 10, m))  # 120 cava
    # Jupiler runs out at +120. Another 200 cava sell before closing.
    for m in range(120, 240, 10):
        orders.append(_order(festival, festival["cava"], 20, m))
    await db.orders.insert_many(orders)

    await db.stockouts.insert_one(
        Stockout(
            edition_id=festival["e26"].id,
            bar_id=festival["main"].id,
            product_id=festival["jup"].id,
            slug="jupiler",
            out_at=START + timedelta(minutes=120),
        ).to_mongo()
    )
    return festival


async def test_it_estimates_what_would_have_sold(db, ran_dry):
    [row] = await stats.stockout_impact(db, ran_dry["e26"].id)

    assert row["slug"] == "jupiler"
    assert row["sold_before"] == 120
    assert row["share_before_pct"] == 50.0  # 120 of 240
    assert row["drinks_during_outage"] == 240  # cava only, 20 every 10 min
    assert row["estimated_lost"] == 120  # 50% of 240
    assert row["reliable"] is True


async def test_it_records_how_long_the_drink_was_gone(db, ran_dry):
    [row] = await stats.stockout_impact(db, ran_dry["e26"].id)
    assert row["hours_out"] == 1.8  # 120 min in to the last order at 230 min
    assert row["back_at"] is None  # never came back


async def test_it_refuses_to_guess_from_almost_no_data(db, festival):
    """A drink that ran out in the first ten minutes has no share worth projecting,
    and a fabricated number in a purchase order is worse than an honest gap."""
    await db.orders.delete_many({"edition_id": festival["e26"].id})
    await db.orders.insert_many(
        [_order(festival, festival["jup"], 1, 0), _order(festival, festival["cava"], 50, 60)]
    )
    await db.stockouts.insert_one(
        Stockout(
            edition_id=festival["e26"].id,
            bar_id=festival["main"].id,
            product_id=festival["jup"].id,
            slug="jupiler",
            out_at=START + timedelta(minutes=10),
        ).to_mongo()
    )

    [row] = await stats.stockout_impact(db, festival["e26"].id)

    assert row["reliable"] is False
    assert row["estimated_lost"] is None


async def test_a_closed_window_only_counts_the_time_it_was_gone(db, festival):
    await db.orders.delete_many({"edition_id": festival["e26"].id})
    orders = [_order(festival, festival["jup"], 10, m) for m in range(0, 120, 10)]
    orders += [_order(festival, festival["cava"], 10, m) for m in range(0, 240, 10)]
    await db.orders.insert_many(orders)
    await db.stockouts.insert_one(
        Stockout(
            edition_id=festival["e26"].id,
            bar_id=festival["main"].id,
            product_id=festival["jup"].id,
            slug="jupiler",
            out_at=START + timedelta(minutes=120),
            back_at=START + timedelta(minutes=180),
        ).to_mongo()
    )

    [row] = await stats.stockout_impact(db, festival["e26"].id)

    assert row["hours_out"] == 1.0
    assert row["drinks_during_outage"] == 60  # only the hour it was gone


async def test_the_advice_buys_for_the_estimated_demand_not_the_sales(db, ran_dry):
    """120 sold plus 120 estimated lost, then the normal 10% buffer."""
    rows = {r["slug"]: r for r in await procurement.advise(db, ran_dry["e26"].id)}

    jupiler = rows["jupiler"]
    assert jupiler["sold"] == 120
    assert jupiler["estimated_lost"] == 120
    assert jupiler["demand_base"] == 240
    assert jupiler["basis"] == "measured"
    assert jupiler["advised"] == 264  # 240 x 1.10


async def test_the_advice_falls_back_to_a_flat_buffer_when_it_cannot_measure(db, festival):
    await db.stockouts.insert_one(
        Stockout(
            edition_id=festival["e26"].id,
            bar_id=festival["main"].id,
            product_id=festival["jup"].id,
            slug="jupiler",
            out_at=datetime(2026, 7, 1, 18, 5, tzinfo=UTC),
        ).to_mongo()
    )

    rows = {r["slug"]: r for r in await procurement.advise(db, festival["e26"].id)}

    assert rows["jupiler"]["basis"] == "buffer"
    assert rows["jupiler"]["safety_pct"] == 25.0


async def test_a_product_that_never_ran_out_is_unaffected(db, festival):
    rows = {r["slug"]: r for r in await procurement.advise(db, festival["e26"].id)}

    assert rows["cava"]["basis"] == "sold"
    assert rows["cava"]["estimated_lost"] is None


async def test_a_stray_order_outside_the_festival_cannot_stretch_the_window(db, ran_dry):
    """One order with a wrong date would otherwise make the outage look like weeks."""

    await db.orders.insert_one(
        _order(ran_dry, ran_dry["cava"], 1, 60 * 24 * 60)  # two months later
    )

    [row] = await stats.stockout_impact(db, ran_dry["e26"].id)

    assert row["hours_out"] < 24
    assert row["estimated_lost"] == 120  # unchanged by the stray order


async def test_a_window_nobody_sold_through_is_not_reported(db, festival):
    """Marked out and back a minute later, with no sales in between. Nothing was
    missed, so there is nothing to report."""

    await db.stockouts.insert_one(
        Stockout(
            edition_id=festival["e26"].id,
            bar_id=festival["main"].id,
            product_id=festival["jup"].id,
            slug="jupiler",
            out_at=datetime(2026, 7, 1, 21, 30, tzinfo=UTC),
            back_at=datetime(2026, 7, 1, 21, 31, tzinfo=UTC),
        ).to_mongo()
    )

    assert await stats.stockout_impact(db, festival["e26"].id) == []
