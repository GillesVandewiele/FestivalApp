"""The stacked hourly chart, in each of its three metrics.

Quantity and revenue are always computable because the coupon price is snapshotted
onto every order line. Margin is not, so the drinks without a cost price have to be
left out rather than drawn as zero.
"""

from app.services import stats

TZ = "Europe/Brussels"


async def test_quantity_split_by_drink(db, festival):
    result = await stats.by_hour_split(db, festival["e26"].id, TZ)

    assert result["hours"] == [20, 21]
    series = {s["name"]: s["data"] for s in result["series"]}
    # 20:00 local: 3 jupiler + 2 water, then 2 jupiler. 21:00: 4 cava, then 1+1.
    assert series["Jupiler"] == [5, 1]
    assert series["Cava"] == [0, 5]
    assert series["Water"] == [2, 0]


async def test_revenue_split_needs_no_cost_price(db, festival):
    """Revenue comes from the snapshotted coupon price, so every drink can be stacked."""
    result = await stats.by_hour_split(db, festival["e26"].id, TZ, metric="revenue_eur")

    series = {s["name"]: s["data"] for s in result["series"]}
    assert series["Jupiler"] == [12.5, 2.5]  # 5 and 1 coupons at 2.50
    assert series["Water"] == [5.0, 0.0]  # water has no cost price and still appears
    assert result["excluded"] == []


async def test_margin_split_leaves_out_drinks_without_a_cost_price(db, festival):
    """Water has no cost price. A zero-height segment would read as "sold nothing",
    which is a different claim from "we cannot work this out"."""
    result = await stats.by_hour_split(db, festival["e26"].id, TZ, metric="margin_eur")

    names = {s["name"] for s in result["series"]}
    assert "Water" not in names
    assert result["excluded"] == ["Water"]

    series = {s["name"]: s["data"] for s in result["series"]}
    # Jupiler at 20:00: 5 sold, 5 coupons -> 12.50 revenue, 5 x 0.60 cost -> 9.50
    assert series["Jupiler"] == [9.5, 1.9]


async def test_the_metric_is_reported_back(db, festival):
    result = await stats.by_hour_split(db, festival["e26"].id, TZ, metric="revenue_eur")
    assert result["metric"] == "revenue_eur"


async def test_series_never_exceed_the_palette(db, festival):
    """Seven named drinks plus Overig. There is no ninth colour to reach for."""
    result = await stats.by_hour_split(db, festival["e26"].id, TZ, top=2)

    names = [s["name"] for s in result["series"]]
    assert len(names) <= 8
    assert names[-1] == "Overig"


async def test_the_overig_bucket_carries_what_it_should(db, festival):
    result = await stats.by_hour_split(db, festival["e26"].id, TZ, top=2)

    series = {s["name"]: s["data"] for s in result["series"]}
    # Top two by quantity are jupiler (6) and cava (5); water (2) folds into Overig.
    assert series["Overig"] == [2, 0]


async def test_staff_drinks_stay_out_of_the_split(db, festival):
    from datetime import UTC, datetime

    from app.models.order import Order, OrderItem

    await db.orders.insert_one(
        Order(
            edition_id=festival["e26"].id,
            bar_id=festival["main"].id,
            staff_id=festival["lotte"].id,
            device_id="d",
            items=[
                OrderItem(
                    product_id=festival["jup"].id,
                    slug="jupiler",
                    name="Jupiler",
                    qty=50,
                    unit_price_coupons=1,
                )
            ],
            total_coupons=50,
            created_at=datetime(2026, 7, 1, 18, 0, tzinfo=UTC),
            received_at=datetime(2026, 7, 1, 18, 0, tzinfo=UTC),
            kind="staff",
        ).to_mongo()
    )

    result = await stats.by_hour_split(db, festival["e26"].id, TZ)

    series = {s["name"]: s["data"] for s in result["series"]}
    assert series["Jupiler"] == [5, 1]  # unchanged


async def test_grouping_by_category_is_coarser_than_by_drink(db, festival):
    """Three drinks, but only two categories once bier and wijn are separated out."""
    from app.models.catalog import Category

    await db.categories.insert_many(
        [
            Category(
                edition_id=festival["e26"].id, slug=slug, name=name, colour="#3987e5"
            ).to_mongo()
            for slug, name in (("bier", "Bier"), ("wijn", "Wijn"), ("fris", "Frisdrank"))
        ]
    )

    result = await stats.by_hour_split(db, festival["e26"].id, TZ, group_by="category")

    series = {s["name"]: s["data"] for s in result["series"]}
    assert set(series) == {"Bier", "Wijn", "Frisdrank"}
    assert series["Bier"] == [5, 1]  # jupiler only
    assert series["Wijn"] == [0, 5]  # cava only
    assert series["Frisdrank"] == [2, 0]  # water only
    assert result["group_by"] == "category"


async def test_a_category_totals_the_drinks_inside_it(db, festival):
    """Two beers must add up into one Bier segment rather than appearing twice."""
    from datetime import UTC, datetime

    from app.models.catalog import Category, Product
    from app.models.order import Order, OrderItem

    await db.categories.insert_one(
        Category(
            edition_id=festival["e26"].id, slug="bier", name="Bier", colour="#c98500"
        ).to_mongo()
    )
    duvel = Product(
        edition_id=festival["e26"].id,
        slug="duvel",
        name="Duvel",
        category="bier",
        price_coupons=2,
        cost_price_eur=1.3,
    )
    await db.products.insert_one(duvel.to_mongo())
    await db.orders.insert_one(
        Order(
            edition_id=festival["e26"].id,
            bar_id=festival["main"].id,
            staff_id=festival["lotte"].id,
            device_id="d",
            items=[
                OrderItem(
                    product_id=duvel.id, slug="duvel", name="Duvel", qty=3, unit_price_coupons=2
                )
            ],
            total_coupons=6,
            created_at=datetime(2026, 7, 1, 18, 0, tzinfo=UTC),
            received_at=datetime(2026, 7, 1, 18, 0, tzinfo=UTC),
        ).to_mongo()
    )

    result = await stats.by_hour_split(db, festival["e26"].id, TZ, group_by="category")

    series = {s["name"]: s["data"] for s in result["series"]}
    assert series["Bier"] == [8, 1]  # 5 jupiler + 3 duvel at 20:00


async def test_a_deleted_category_still_shows_which_one_it_was(db, festival):
    """Deleting a category must not make its drinks disappear from the chart, and
    naming the orphaned slug is more useful than lumping them into "Overige"."""
    result = await stats.by_hour_split(db, festival["e26"].id, TZ, group_by="category")

    # No Category documents in this fixture, so the products' raw slugs show through.
    assert {s["name"] for s in result["series"]} == {"bier", "wijn", "fris"}


async def test_a_product_with_no_category_at_all_falls_into_overige(db, festival):
    await db.products.update_one({"slug": "water"}, {"$set": {"category": ""}})

    result = await stats.by_hour_split(db, festival["e26"].id, TZ, group_by="category")

    assert "Overige" in {s["name"] for s in result["series"]}
