async def test_stats_require_authentication(client, festival):
    r = await client.get(f"/api/v1/stats/overview?edition_id={festival['e26'].id}")
    assert r.status_code == 401


async def test_overview_endpoint(auth_client, festival):
    r = await auth_client.get(f"/api/v1/stats/overview?edition_id={festival['e26'].id}")
    assert r.status_code == 200
    assert r.json()["drinks"] == 13


async def test_by_product_endpoint(auth_client, festival):
    r = await auth_client.get(f"/api/v1/stats/by-product?edition_id={festival['e26'].id}")
    assert [row["slug"] for row in r.json()] == ["jupiler", "cava", "water"]


async def test_by_hour_uses_the_edition_timezone_without_being_told(auth_client, festival):
    r = await auth_client.get(f"/api/v1/stats/by-hour?edition_id={festival['e26'].id}")
    assert [row["hour_local"] for row in r.json()] == [20, 21]


async def test_compare_endpoint(auth_client, festival):
    r = await auth_client.get(
        f"/api/v1/stats/compare?edition_a={festival['e25'].id}&edition_b={festival['e26'].id}"
    )
    rows = {row["slug"]: row for row in r.json()}
    assert rows["jupiler"]["delta"] == 2


async def test_procurement_endpoint_accepts_parameters(auth_client, festival):
    r = await auth_client.get(
        f"/api/v1/stats/procurement?edition_id={festival['e26'].id}&safety_pct=50"
    )
    rows = {row["slug"]: row for row in r.json()}
    assert rows["jupiler"]["advised"] == 9


async def test_unknown_edition_returns_404(auth_client):
    r = await auth_client.get("/api/v1/stats/overview?edition_id=nope")
    assert r.status_code == 404


async def test_csv_export(auth_client, festival):
    r = await auth_client.get(f"/api/v1/export/by-product.csv?edition_id={festival['e26'].id}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("slug,name")
    assert "jupiler" in lines[1]


async def test_procurement_csv_export(auth_client, festival):
    r = await auth_client.get(f"/api/v1/export/procurement.csv?edition_id={festival['e26'].id}")
    assert r.status_code == 200
    assert "units_to_order" in r.text.splitlines()[0]


async def test_unknown_report_is_404(auth_client, festival):
    r = await auth_client.get(f"/api/v1/export/nonsense.csv?edition_id={festival['e26'].id}")
    assert r.status_code == 404


async def test_hourly_split_endpoint_defaults_to_drinks(auth_client, festival):
    r = await auth_client.get(f"/api/v1/stats/by-hour-split?edition_id={festival['e26'].id}")
    assert r.status_code == 200
    assert r.json()["group_by"] == "product"
    assert r.json()["metric"] == "qty"


async def test_hourly_split_endpoint_accepts_category_and_metric(auth_client, festival):
    r = await auth_client.get(
        f"/api/v1/stats/by-hour-split?edition_id={festival['e26'].id}"
        "&group_by=category&metric=revenue_eur"
    )
    assert r.status_code == 200
    assert r.json()["group_by"] == "category"
    assert r.json()["metric"] == "revenue_eur"


async def test_hourly_split_rejects_a_metric_it_does_not_have(auth_client, festival):
    """A typo must fail loudly rather than silently falling back to counts."""
    r = await auth_client.get(
        f"/api/v1/stats/by-hour-split?edition_id={festival['e26'].id}&metric=nonsense"
    )
    assert r.status_code == 422
