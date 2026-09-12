from datetime import UTC, datetime

import pytest_asyncio

from app.models.catalog import Bar, Edition, Product, Staff


@pytest_asyncio.fixture
async def festival(db, auth_client):
    edition = Edition(
        name="Festival 2026",
        year=2026,
        coupon_value_eur=2.50,
        starts_at=datetime(2026, 7, 1, tzinfo=UTC),
        ends_at=datetime(2026, 7, 3, tzinfo=UTC),
    )
    main_bar = Bar(edition_id=edition.id, name="Hoofdpodium")
    cocktail_bar = Bar(edition_id=edition.id, name="Cocktailbar")

    jupiler = Product(
        edition_id=edition.id,
        slug="jupiler",
        name="Jupiler",
        category="bier",
        price_coupons=1,
        available_at=[main_bar.id, cocktail_bar.id],
    )
    gin = Product(
        edition_id=edition.id,
        slug="gin-tonic",
        name="Gin-Tonic",
        category="cocktail",
        price_coupons=4,
        available_at=[cocktail_bar.id],
    )
    lotte = Staff(edition_id=edition.id, name="Lotte")

    await db.editions.insert_one(edition.to_mongo())
    await db.bars.insert_many([main_bar.to_mongo(), cocktail_bar.to_mongo()])
    await db.products.insert_many([jupiler.to_mongo(), gin.to_mongo()])
    await db.staff.insert_one(lotte.to_mongo())

    r = await auth_client.post(
        "/api/v1/admin/devices/enroll",
        json={"edition_id": edition.id, "bar_id": main_bar.id, "label": "Tablet 1"},
    )
    return {"edition": edition, "main_bar": main_bar, "device": r.json()}


def _auth(festival) -> dict:
    return {"Authorization": f"Bearer {festival['device']['token']}"}


async def test_time_returns_utc(client, festival):
    r = await client.get("/api/v1/time", headers=_auth(festival))
    assert r.status_code == 200
    parsed = datetime.fromisoformat(r.json()["server_time"])
    assert parsed.tzinfo is not None
    assert abs((datetime.now(UTC) - parsed).total_seconds()) < 5


async def test_bootstrap_returns_the_devices_edition_and_bar(client, festival):
    r = await client.get("/api/v1/bootstrap", headers=_auth(festival))
    assert r.status_code == 200
    body = r.json()
    assert body["edition"]["name"] == "Festival 2026"
    assert body["bar"]["name"] == "Hoofdpodium"


async def test_bootstrap_only_returns_products_sold_at_this_bar(client, festival):
    """A main-stage tablet must not show cocktail-only products."""
    body = (await client.get("/api/v1/bootstrap", headers=_auth(festival))).json()
    assert [p["slug"] for p in body["products"]] == ["jupiler"]


async def test_bootstrap_returns_staff_and_server_time(client, festival):
    body = (await client.get("/api/v1/bootstrap", headers=_auth(festival))).json()
    assert [s["name"] for s in body["staff"]] == ["Lotte"]
    assert body["server_time"]


async def test_bootstrap_requires_a_device_token(client, festival):
    assert (await client.get("/api/v1/bootstrap")).status_code == 401
