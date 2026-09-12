from datetime import UTC, datetime
from uuid import uuid4

import pytest_asyncio

from app.models.catalog import Bar, Edition, Product, Staff


@pytest_asyncio.fixture
async def setup(db, auth_client):
    edition = Edition(
        name="Festival 2026",
        year=2026,
        coupon_value_eur=2.50,
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


def _order(setup, **overrides) -> dict:
    base = {
        "id": str(uuid4()),
        "edition_id": setup["edition"].id,
        "bar_id": setup["bar"].id,
        "staff_id": setup["staff"].id,
        "items": [
            {
                "product_id": setup["product"].id,
                "slug": "jupiler",
                "name": "Jupiler",
                "qty": 3,
                "unit_price_coupons": 1,
            }
        ],
        "created_at": datetime.now(UTC).isoformat(),
        "status": "confirmed",
    }
    return base | overrides


def _auth(setup) -> dict:
    return {"Authorization": f"Bearer {setup['device']['token']}"}


def _void_block(setup) -> dict:
    return {
        "at": datetime.now(UTC).isoformat(),
        "by": {"type": "staff", "id": setup["staff"].id},
        "reason": None,
    }


async def _post(client, setup, *orders):
    return await client.post(
        "/api/v1/sync/orders", json={"orders": list(orders)}, headers=_auth(setup)
    )


async def test_a_single_order_is_stored(client, setup, db):
    order = _order(setup)
    r = await _post(client, setup, order)

    assert r.status_code == 200
    assert r.json()["accepted"] == [order["id"]]

    doc = await db.orders.find_one({"_id": order["id"]})
    assert doc["status"] == "confirmed"
    assert doc["items"][0]["qty"] == 3


async def test_the_total_is_recomputed_server_side(client, setup, db):
    """3 x 1 coupon = 3. The client never gets to assert the total."""
    order = _order(setup)
    await _post(client, setup, order)
    doc = await db.orders.find_one({"_id": order["id"]})
    assert doc["total_coupons"] == 3


async def test_the_device_id_comes_from_the_token_not_the_payload(client, setup, db):
    order = _order(setup)
    await _post(client, setup, order)
    doc = await db.orders.find_one({"_id": order["id"]})
    assert doc["device_id"] == setup["device"]["id"]


async def test_resubmitting_the_same_order_does_not_duplicate_it(client, setup, db):
    """The core offline guarantee: retries over a flaky link are free."""
    order = _order(setup)
    await _post(client, setup, order)
    await _post(client, setup, order)
    await _post(client, setup, order)

    assert await db.orders.count_documents({"_id": order["id"]}) == 1
    assert await db.orders.count_documents({}) == 1


async def test_received_at_is_not_overwritten_by_a_retry(client, setup, db):
    order = _order(setup)
    await _post(client, setup, order)
    first = (await db.orders.find_one({"_id": order["id"]}))["received_at"]
    await _post(client, setup, order)
    assert (await db.orders.find_one({"_id": order["id"]}))["received_at"] == first


async def test_an_order_voided_before_it_ever_synced_arrives_voided(client, setup, db):
    order = _order(setup, status="voided", void=_void_block(setup))
    await _post(client, setup, order)

    doc = await db.orders.find_one({"_id": order["id"]})
    assert doc["status"] == "voided"
    assert doc["void"]["by"]["type"] == "staff"


async def test_voiding_an_already_synced_order_works(client, setup, db):
    order = _order(setup)
    await _post(client, setup, order)

    await _post(client, setup, order | {"status": "voided", "void": _void_block(setup)})

    assert (await db.orders.find_one({"_id": order["id"]}))["status"] == "voided"


async def test_a_voided_order_can_never_be_resurrected(client, setup, db):
    """A stale tablet replaying an old queue must not undo a void."""
    order = _order(setup)
    await _post(client, setup, order)
    await _post(client, setup, order | {"status": "voided", "void": _void_block(setup)})

    r = await _post(client, setup, order)  # the stale "confirmed" copy

    assert r.json()["results"][order["id"]] == "ignored"
    assert (await db.orders.find_one({"_id": order["id"]}))["status"] == "voided"


async def test_a_batch_of_orders_is_accepted(client, setup, db):
    orders = [_order(setup) for _ in range(5)]
    r = await _post(client, setup, *orders)

    assert len(r.json()["accepted"]) == 5
    assert await db.orders.count_documents({}) == 5


async def test_one_bad_order_does_not_reject_the_whole_batch(client, setup, db):
    """A tablet must never be stuck unable to drain its queue."""
    good = _order(setup)
    bad = _order(setup, items=[])
    r = await _post(client, setup, good, bad)

    assert good["id"] in r.json()["accepted"]
    assert r.json()["results"][bad["id"]] == "rejected"
    assert await db.orders.count_documents({}) == 1


async def test_sync_requires_a_device_token(client, setup):
    r = await client.post("/api/v1/sync/orders", json={"orders": [_order(setup)]})
    assert r.status_code == 401
