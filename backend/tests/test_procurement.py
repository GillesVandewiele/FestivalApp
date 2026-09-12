from datetime import UTC, datetime

from app.models.order import Stockout
from app.services import procurement


async def test_advice_rounds_up_to_whole_purchase_units(db, festival):
    """You cannot buy 7 bottles from a case of 24."""
    rows = {r["slug"]: r for r in await procurement.advise(db, festival["e26"].id)}

    jupiler = rows["jupiler"]
    assert jupiler["sold"] == 6
    assert jupiler["advised"] == 7  # 6 x 1.10 = 6.6, rounded up
    assert jupiler["unit_size"] == 24
    assert jupiler["units_to_order"] == 1  # ceil(7 / 24)
    assert jupiler["purchase_unit"] == "bak"


async def test_the_safety_buffer_is_applied(db, festival):
    rows = {r["slug"]: r for r in await procurement.advise(db, festival["e26"].id, safety_pct=50.0)}
    assert rows["jupiler"]["advised"] == 9  # 6 x 1.50


async def test_expected_growth_compounds_with_safety(db, festival):
    rows = {
        r["slug"]: r
        for r in await procurement.advise(db, festival["e26"].id, growth_pct=100.0, safety_pct=0.0)
    }
    assert rows["jupiler"]["advised"] == 12  # 6 x 2.00


async def test_a_stockout_raises_the_safety_buffer(db, festival):
    """A product that ran out did not sell what people wanted, it sold what was left.
    Advising from that number under-buys the same product every year."""
    await db.stockouts.insert_one(
        Stockout(
            edition_id=festival["e26"].id,
            bar_id=festival["main"].id,
            product_id=festival["jup"].id,
            slug="jupiler",
            out_at=datetime(2026, 7, 1, 22, 0, tzinfo=UTC),
        ).to_mongo()
    )

    rows = {r["slug"]: r for r in await procurement.advise(db, festival["e26"].id)}

    assert rows["jupiler"]["had_stockout"] is True
    assert rows["jupiler"]["safety_pct"] == 25.0
    assert rows["jupiler"]["advised"] == 8  # 6 x 1.25 = 7.5, rounded up
    assert rows["cava"]["had_stockout"] is False
    assert rows["cava"]["safety_pct"] == 10.0


async def test_cost_is_reported_per_purchase_unit(db, festival):
    rows = {r["slug"]: r for r in await procurement.advise(db, festival["e26"].id)}
    # 1 bak of 24 at 0.60 each
    assert rows["jupiler"]["cost_eur"] == 14.4
    assert rows["jupiler"]["cost_known"] is True


async def test_a_product_without_a_purchase_unit_still_gets_advice(db, festival):
    """Water has no crate size configured. The advice is still useful; only the unit
    count is unknown."""
    rows = {r["slug"]: r for r in await procurement.advise(db, festival["e26"].id)}

    water = rows["water"]
    assert water["advised"] == 3  # 2 x 1.10 = 2.2, rounded up
    assert water["units_to_order"] is None
    assert water["cost_known"] is False
    assert water["cost_eur"] is None


async def test_observed_growth_is_used_when_a_previous_edition_is_given(db, festival):
    """Jupiler went 4 -> 6, so +50%. With no safety, advice is 6 x 1.5 = 9."""
    rows = {
        r["slug"]: r
        for r in await procurement.advise(
            db, festival["e26"].id, compare_to=festival["e25"].id, safety_pct=0.0
        )
    }
    assert rows["jupiler"]["growth_pct"] == 50.0
    assert rows["jupiler"]["advised"] == 9


async def test_the_rounding_surplus_is_reported(db, festival):
    """Whole packs only, so you always buy more than advised. That overshoot is
    stock you are stuck with, because a partial bak cannot go back."""
    rows = {r["slug"]: r for r in await procurement.advise(db, festival["e26"].id)}

    jupiler = rows["jupiler"]
    assert jupiler["advised"] == 7
    assert jupiler["units_to_order"] == 1
    assert jupiler["total_units"] == 24  # 1 bak of 24
    assert jupiler["surplus_units"] == 17  # 24 - 7


async def test_surplus_is_unknown_without_a_purchase_unit(db, festival):
    rows = {r["slug"]: r for r in await procurement.advise(db, festival["e26"].id)}

    assert rows["water"]["total_units"] is None
    assert rows["water"]["surplus_units"] is None
