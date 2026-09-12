"""Golden tests. A wrong total looks perfectly plausible, so these assert exact
numbers derived by hand from the fixture rather than recomputing the pipeline."""

from app.services import stats

TZ = "Europe/Brussels"


async def test_overview_excludes_voided_orders(db, festival):
    """The voided order carries 99 drinks. If it leaks, every number is wrong."""
    result = await stats.overview(db, festival["e26"].id)

    assert result["orders"] == 4
    assert result["drinks"] == 13  # 3+2 +2 +4 +1+1
    assert result["coupons"] == 23  # (3x1 + 2x1) + 2x1 + 4x3 + (1x1 + 1x3)
    assert result["revenue_eur"] == 57.5  # 23 x 2.50
    assert result["voided_orders"] == 1


async def test_overview_reports_margin_and_what_it_leaves_out(db, festival):
    """Water has no cost price, so it contributes revenue but no margin. The
    figure must say so rather than quietly counting water as pure profit."""
    result = await stats.overview(db, festival["e26"].id)

    # jupiler 15.00 - 3.60 = 11.40, cava 37.50 - 12.00 = 25.50
    assert result["margin_eur"] == 36.9
    assert result["cost_eur"] == 15.6
    assert result["cost_missing"] == 1


async def test_overview_margin_is_unknown_when_no_product_has_a_cost(db, festival):
    await db.products.update_many(
        {"edition_id": festival["e26"].id}, {"$set": {"cost_price_eur": None}}
    )

    result = await stats.overview(db, festival["e26"].id)

    assert result["margin_eur"] is None
    assert result["cost_eur"] is None
    assert result["cost_missing"] == 3


async def test_by_product_computes_margin(db, festival):
    rows = {r["slug"]: r for r in await stats.by_product(db, festival["e26"].id)}

    jupiler = rows["jupiler"]
    assert jupiler["qty"] == 6  # 3 + 2 + 1
    assert jupiler["coupons"] == 6
    assert jupiler["revenue_eur"] == 15.0  # 6 x 2.50
    assert jupiler["cost_eur"] == 3.6  # 6 x 0.60
    assert jupiler["margin_eur"] == 11.4
    assert jupiler["cost_known"] is True

    cava = rows["cava"]
    assert cava["qty"] == 5
    assert cava["coupons"] == 15
    assert cava["revenue_eur"] == 37.5
    assert cava["cost_eur"] == 12.0  # 5 x 2.40
    assert cava["margin_eur"] == 25.5


async def test_by_product_handles_a_missing_cost_price(db, festival):
    """Invoices arrive after the festival. An unpriced product must not read as
    100% margin, which would be a lie a purchasing decision could rest on."""
    rows = {r["slug"]: r for r in await stats.by_product(db, festival["e26"].id)}

    water = rows["water"]
    assert water["qty"] == 2
    assert water["revenue_eur"] == 5.0
    assert water["cost_known"] is False
    assert water["cost_eur"] is None
    assert water["margin_eur"] is None


async def test_by_product_is_sorted_by_quantity(db, festival):
    rows = await stats.by_product(db, festival["e26"].id)
    assert [r["slug"] for r in rows] == ["jupiler", "cava", "water"]


async def test_by_bar(db, festival):
    rows = {r["name"]: r for r in await stats.by_bar(db, festival["e26"].id)}

    assert rows["Hoofdpodium"]["qty"] == 7  # 3+2 +2
    assert rows["Hoofdpodium"]["coupons"] == 7
    assert rows["Cocktailbar"]["qty"] == 6  # 4 +1+1
    assert rows["Cocktailbar"]["coupons"] == 16  # 4x3 + (1x1 + 1x3)


async def test_by_staff_counts_voids_separately(db, festival):
    rows = {r["name"]: r for r in await stats.by_staff(db, festival["e26"].id)}

    assert rows["Lotte"]["orders"] == 2
    assert rows["Lotte"]["qty"] == 7
    assert rows["Lotte"]["voided"] == 1  # a signal worth seeing, not hidden
    assert rows["Jonas"]["orders"] == 2
    assert rows["Jonas"]["voided"] == 0


async def test_by_hour_uses_the_edition_timezone(db, festival):
    """18:00 UTC is 20:00 in Brussels in July. Bucketing in UTC would put the whole
    evening in the wrong hours, and hourly demand is a headline number."""
    rows = await stats.by_hour(db, festival["e26"].id, TZ)

    assert [r["hour_local"] for r in rows] == [20, 21]
    assert rows[0]["qty"] == 7  # 3+2 and 2, both 20:00 local
    assert rows[1]["qty"] == 6  # 4 and 1+1, both 21:00 local


async def test_peak_per_bar(db, festival):
    rows = {r["name"]: r for r in await stats.peak_per_bar(db, festival["e26"].id, TZ)}

    assert rows["Hoofdpodium"]["peak_hour"] == 20
    assert rows["Hoofdpodium"]["peak_qty"] == 7
    assert rows["Cocktailbar"]["peak_hour"] == 21
    assert rows["Cocktailbar"]["peak_qty"] == 6


async def test_compare_matches_on_slug(db, festival):
    """Products are edition-scoped documents, so comparison can only work on slug."""
    rows = {r["slug"]: r for r in await stats.compare(db, festival["e25"].id, festival["e26"].id)}

    assert rows["jupiler"]["qty_a"] == 4
    assert rows["jupiler"]["qty_b"] == 6
    assert rows["jupiler"]["delta"] == 2
    assert rows["jupiler"]["pct"] == 50.0

    assert rows["cava"]["qty_a"] == 2
    assert rows["cava"]["qty_b"] == 5


async def test_compare_includes_products_sold_in_only_one_edition(db, festival):
    """Water is new in 2026. Dropping it would hide a product that needs buying."""
    rows = {r["slug"]: r for r in await stats.compare(db, festival["e25"].id, festival["e26"].id)}

    assert rows["water"]["qty_a"] == 0
    assert rows["water"]["qty_b"] == 2
    assert rows["water"]["pct"] is None  # growth from zero is undefined, not infinite


async def test_product_coupons_sum_to_the_overview_total(db, festival):
    """A cross-check between two independent pipelines. When the hand-derived
    numbers above and the aggregation disagree, this says which one to trust."""
    total = await stats.overview(db, festival["e26"].id)
    per_product = await stats.by_product(db, festival["e26"].id)

    assert sum(r["coupons"] for r in per_product) == total["coupons"]
    assert sum(r["qty"] for r in per_product) == total["drinks"]


async def test_bar_coupons_sum_to_the_overview_total(db, festival):
    total = await stats.overview(db, festival["e26"].id)
    per_bar = await stats.by_bar(db, festival["e26"].id)

    assert sum(r["coupons"] for r in per_bar) == total["coupons"]


async def test_hours_are_ordered_as_the_night_was_lived(db, festival):
    """A festival running past midnight has hours like 22, 23, 0, 1. Sorting those
    numerically claims the evening started at midnight."""
    from app.services.stats import _chronological

    overnight = [
        {"hour_local": 0, "qty": 5, "coupons": 5},
        {"hour_local": 1, "qty": 3, "coupons": 3},
        {"hour_local": 22, "qty": 9, "coupons": 9},
        {"hour_local": 23, "qty": 7, "coupons": 7},
    ]
    assert [r["hour_local"] for r in _chronological(overnight)] == [22, 23, 0, 1]


async def test_an_afternoon_only_edition_is_left_alone(db, festival):
    from app.services.stats import _chronological

    daytime = [
        {"hour_local": 14, "qty": 1, "coupons": 1},
        {"hour_local": 15, "qty": 2, "coupons": 2},
        {"hour_local": 16, "qty": 3, "coupons": 3},
    ]
    assert [r["hour_local"] for r in _chronological(daytime)] == [14, 15, 16]


async def test_a_single_hour_is_left_alone(db, festival):
    from app.services.stats import _chronological

    assert _chronological([{"hour_local": 3, "qty": 1, "coupons": 1}]) == [
        {"hour_local": 3, "qty": 1, "coupons": 1}
    ]
