from datetime import UTC, datetime
from uuid import uuid4

import pytest_asyncio

from app.models.catalog import Bar, Edition, Product, Staff


@pytest_asyncio.fixture
async def setup(db, auth_client):
    edition = Edition(
        name="F26",
        year=2026,
        coupon_value_eur=2.5,
        starts_at=datetime(2026, 7, 1, tzinfo=UTC),
        ends_at=datetime(2026, 7, 3, tzinfo=UTC),
    )
    bar = Bar(edition_id=edition.id, name="Hoofdpodium")
    product = Product(
        edition_id=edition.id,
        slug="jupiler",
        name="Jupiler",
        category="bier",
        price_coupons=1,
        available_at=[bar.id],
    )
    staff = Staff(edition_id=edition.id, name="Lotte")
    await db.editions.insert_one(edition.to_mongo())
    await db.bars.insert_one(bar.to_mongo())
    await db.products.insert_one(product.to_mongo())
    await db.staff.insert_one(staff.to_mongo())
    device = (
        await auth_client.post(
            "/api/v1/admin/devices/enroll",
            json={"edition_id": edition.id, "bar_id": bar.id, "label": "T1"},
        )
    ).json()
    return {"edition": edition, "bar": bar, "product": product, "staff": staff, "device": device}


def _auth(setup):
    return {"Authorization": f"Bearer {setup['device']['token']}"}


async def test_a_stockout_is_recorded_with_the_product_slug(client, setup, db):
    sid = str(uuid4())
    r = await client.post(
        "/api/v1/sync/stockouts",
        headers=_auth(setup),
        json={
            "stockouts": [
                {
                    "id": sid,
                    "product_id": setup["product"].id,
                    "out_at": datetime.now(UTC).isoformat(),
                }
            ]
        },
    )

    assert r.status_code == 200
    doc = await db.stockouts.find_one({"_id": sid})
    assert doc["slug"] == "jupiler"  # denormalised for year-over-year joins
    assert doc["bar_id"] == setup["bar"].id
    assert doc["back_at"] is None


async def test_marking_a_product_back_in_stock_updates_the_same_record(client, setup, db):
    sid = str(uuid4())
    out_at = datetime.now(UTC).isoformat()
    await client.post(
        "/api/v1/sync/stockouts",
        headers=_auth(setup),
        json={"stockouts": [{"id": sid, "product_id": setup["product"].id, "out_at": out_at}]},
    )

    back = datetime.now(UTC).isoformat()
    await client.post(
        "/api/v1/sync/stockouts",
        headers=_auth(setup),
        json={
            "stockouts": [
                {
                    "id": sid,
                    "product_id": setup["product"].id,
                    "out_at": out_at,
                    "back_at": back,
                }
            ]
        },
    )

    assert await db.stockouts.count_documents({}) == 1
    assert (await db.stockouts.find_one({"_id": sid}))["back_at"] is not None


async def test_a_stockout_for_an_unknown_product_is_rejected(client, setup):
    r = await client.post(
        "/api/v1/sync/stockouts",
        headers=_auth(setup),
        json={
            "stockouts": [
                {"id": str(uuid4()), "product_id": "nope", "out_at": datetime.now(UTC).isoformat()}
            ]
        },
    )
    assert r.json()["accepted"] == []


async def test_stockout_sync_requires_a_device_token(client, setup):
    r = await client.post("/api/v1/sync/stockouts", json={"stockouts": []})
    assert r.status_code == 401


async def test_an_organiser_can_void_an_order_with_a_reason(client, auth_client, setup, db):
    oid = str(uuid4())
    await client.post(
        "/api/v1/sync/orders",
        headers=_auth(setup),
        json={
            "orders": [
                {
                    "id": oid,
                    "edition_id": setup["edition"].id,
                    "bar_id": setup["bar"].id,
                    "staff_id": setup["staff"].id,
                    "items": [
                        {
                            "product_id": setup["product"].id,
                            "slug": "jupiler",
                            "name": "Jupiler",
                            "qty": 1,
                            "unit_price_coupons": 1,
                        }
                    ],
                    "created_at": datetime.now(UTC).isoformat(),
                    "status": "confirmed",
                }
            ]
        },
    )

    r = await auth_client.post(
        f"/api/v1/admin/orders/{oid}/void", json={"reason": "duplicate entry"}
    )

    assert r.status_code == 200
    doc = await db.orders.find_one({"_id": oid})
    assert doc["status"] == "voided"
    assert doc["void"]["by"]["type"] == "user"
    assert doc["void"]["reason"] == "duplicate entry"


async def test_an_organiser_void_requires_a_reason(auth_client, setup):
    r = await auth_client.post("/api/v1/admin/orders/whatever/void", json={})
    assert r.status_code == 422


async def test_voiding_an_unknown_order_is_404(auth_client):
    r = await auth_client.post("/api/v1/admin/orders/nope/void", json={"reason": "x"})
    assert r.status_code == 404
