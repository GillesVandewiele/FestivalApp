import pytest_asyncio


@pytest_asyncio.fixture
async def enrolled(auth_client):
    r = await auth_client.post(
        "/api/v1/admin/devices/enroll",
        json={"edition_id": "e1", "bar_id": "b1", "label": "Tablet bar 1"},
    )
    assert r.status_code == 201
    return r.json()


async def test_enrolment_returns_a_plaintext_token_once(enrolled):
    assert enrolled["token"]
    assert len(enrolled["token"]) >= 32


async def test_the_token_is_never_stored_in_plaintext(enrolled, db):
    doc = await db.devices.find_one({"_id": enrolled["id"]})
    assert doc["token_hash"] != enrolled["token"]
    assert enrolled["token"] not in str(doc)


async def test_listing_devices_never_leaks_tokens(auth_client, enrolled):
    listed = (await auth_client.get("/api/v1/admin/devices")).json()
    assert len(listed) == 1
    assert "token" not in listed[0]
    assert "token_hash" not in listed[0]


async def test_enrolment_requires_authentication(client):
    r = await client.post(
        "/api/v1/admin/devices/enroll",
        json={"edition_id": "e1", "bar_id": "b1", "label": "x"},
    )
    assert r.status_code == 401


async def test_a_valid_device_token_authenticates(client, enrolled):
    r = await client.get("/api/v1/time", headers={"Authorization": f"Bearer {enrolled['token']}"})
    assert r.status_code == 200


async def test_an_unknown_device_token_is_rejected(client):
    r = await client.get("/api/v1/time", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


async def test_a_missing_token_is_rejected(client):
    assert (await client.get("/api/v1/time")).status_code == 401


async def test_a_revoked_device_is_rejected(client, auth_client, enrolled):
    r = await auth_client.post(f"/api/v1/admin/devices/{enrolled['id']}/revoke")
    assert r.status_code == 204

    r = await client.get("/api/v1/time", headers={"Authorization": f"Bearer {enrolled['token']}"})
    assert r.status_code == 401
