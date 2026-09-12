EDITION = {
    "name": "Festival 2026",
    "year": 2026,
    "starts_at": "2026-07-01T14:00:00Z",
    "ends_at": "2026-07-03T02:00:00Z",
    "coupon_value_eur": 2.50,
}


async def test_catalog_requires_authentication(client):
    assert (await client.get("/api/v1/admin/editions")).status_code == 401
    assert (await client.post("/api/v1/admin/editions", json=EDITION)).status_code == 401


async def test_create_and_list_an_edition(auth_client):
    r = await auth_client.post("/api/v1/admin/editions", json=EDITION)
    assert r.status_code == 201
    created = r.json()
    assert created["name"] == "Festival 2026"
    assert created["id"]

    listed = (await auth_client.get("/api/v1/admin/editions")).json()
    assert [e["id"] for e in listed] == [created["id"]]


async def test_update_an_edition(auth_client):
    eid = (await auth_client.post("/api/v1/admin/editions", json=EDITION)).json()["id"]

    r = await auth_client.patch(f"/api/v1/admin/editions/{eid}", json={"coupon_value_eur": 3.00})

    assert r.status_code == 200
    assert r.json()["coupon_value_eur"] == 3.00
    assert r.json()["name"] == "Festival 2026"


async def test_delete_an_edition(auth_client):
    eid = (await auth_client.post("/api/v1/admin/editions", json=EDITION)).json()["id"]
    assert (await auth_client.delete(f"/api/v1/admin/editions/{eid}")).status_code == 204
    assert (await auth_client.get("/api/v1/admin/editions")).json() == []


async def test_updating_something_that_does_not_exist_is_404(auth_client):
    r = await auth_client.patch("/api/v1/admin/editions/nope", json={"year": 2027})
    assert r.status_code == 404


async def test_duplicate_product_slug_in_one_edition_is_rejected(auth_client):
    eid = (await auth_client.post("/api/v1/admin/editions", json=EDITION)).json()["id"]
    product = {
        "edition_id": eid,
        "slug": "jupiler",
        "name": "Jupiler",
        "category": "bier",
        "price_coupons": 1,
    }

    assert (await auth_client.post("/api/v1/admin/products", json=product)).status_code == 201
    r = await auth_client.post("/api/v1/admin/products", json=product)
    assert r.status_code == 409


async def test_products_can_be_filtered_by_edition(auth_client):
    a = (await auth_client.post("/api/v1/admin/editions", json=EDITION)).json()["id"]
    b = (
        await auth_client.post(
            "/api/v1/admin/editions", json={**EDITION, "name": "Festival 2027", "year": 2027}
        )
    ).json()["id"]
    for eid, slug in ((a, "jupiler"), (b, "cava")):
        await auth_client.post(
            "/api/v1/admin/products",
            json={
                "edition_id": eid,
                "slug": slug,
                "name": slug,
                "category": "x",
                "price_coupons": 1,
            },
        )

    listed = (await auth_client.get(f"/api/v1/admin/products?edition_id={a}")).json()
    assert [p["slug"] for p in listed] == ["jupiler"]


async def test_invalid_slug_is_rejected(auth_client):
    eid = (await auth_client.post("/api/v1/admin/editions", json=EDITION)).json()["id"]
    r = await auth_client.post(
        "/api/v1/admin/products",
        json={
            "edition_id": eid,
            "slug": "Gin Tonic",
            "name": "x",
            "category": "y",
            "price_coupons": 1,
        },
    )
    assert r.status_code == 422
