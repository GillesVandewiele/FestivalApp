EDITION = {
    "name": "Festival 2026",
    "year": 2026,
    "starts_at": "2026-07-01T14:00:00Z",
    "ends_at": "2026-07-03T02:00:00Z",
    "coupon_value_eur": 2.50,
}


async def _edition(auth_client) -> str:
    return (await auth_client.post("/api/v1/admin/editions", json=EDITION)).json()["id"]


async def test_categories_can_be_created_and_listed(auth_client):
    eid = await _edition(auth_client)
    body = {"edition_id": eid, "slug": "bier", "name": "Bier", "colour": "#e8a33d", "sort_order": 0}

    r = await auth_client.post("/api/v1/admin/categories", json=body)

    assert r.status_code == 201
    listed = (await auth_client.get(f"/api/v1/admin/categories?edition_id={eid}")).json()
    assert [c["name"] for c in listed] == ["Bier"]


async def test_a_category_colour_must_be_a_hex_value(auth_client):
    """The colour reaches a stylesheet, so an arbitrary string cannot be allowed in."""
    eid = await _edition(auth_client)
    r = await auth_client.post(
        "/api/v1/admin/categories",
        json={"edition_id": eid, "slug": "bier", "name": "Bier", "colour": "rood"},
    )
    assert r.status_code == 422


async def test_categories_can_be_renamed_and_recoloured(auth_client):
    eid = await _edition(auth_client)
    cid = (
        await auth_client.post(
            "/api/v1/admin/categories",
            json={"edition_id": eid, "slug": "bier", "name": "Bier", "colour": "#e8a33d"},
        )
    ).json()["id"]

    r = await auth_client.patch(
        f"/api/v1/admin/categories/{cid}", json={"name": "Bieren", "colour": "#2a78d6"}
    )

    assert r.status_code == 200
    assert r.json()["name"] == "Bieren"
    assert r.json()["colour"] == "#2a78d6"


async def test_a_category_can_be_deleted_when_nothing_uses_it(auth_client):
    eid = await _edition(auth_client)
    cid = (
        await auth_client.post(
            "/api/v1/admin/categories",
            json={"edition_id": eid, "slug": "warm", "name": "Warme dranken", "colour": "#a9764a"},
        )
    ).json()["id"]

    assert (await auth_client.delete(f"/api/v1/admin/categories/{cid}")).status_code == 204


async def test_deleting_a_category_in_use_is_refused_and_names_the_products(auth_client):
    """Silently reassigning would move drinks into a category nobody chose."""
    eid = await _edition(auth_client)
    cid = (
        await auth_client.post(
            "/api/v1/admin/categories",
            json={"edition_id": eid, "slug": "bier", "name": "Bier", "colour": "#e8a33d"},
        )
    ).json()["id"]
    await auth_client.post(
        "/api/v1/admin/products",
        json={
            "edition_id": eid,
            "slug": "jupiler",
            "name": "Jupiler",
            "category": "bier",
            "price_coupons": 1,
        },
    )

    r = await auth_client.delete(f"/api/v1/admin/categories/{cid}")

    assert r.status_code == 409
    assert "Jupiler" in r.json()["detail"]


async def test_categories_require_authentication(anon_client):
    assert (await anon_client.get("/api/v1/admin/categories")).status_code == 401
