async def test_security_headers_are_present(client):
    r = await client.get("/api/v1/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"


async def test_repeated_failed_logins_are_rate_limited(client, make_user):
    await make_user("org@example.com", "hunter2hunter2")
    codes = []
    for _ in range(12):
        r = await client.post(
            "/api/v1/auth/login", json={"email": "org@example.com", "password": "wrong"}
        )
        codes.append(r.status_code)
    assert 429 in codes, "brute-forcing the login must eventually be throttled"


async def test_health_is_not_rate_limited(client):
    for _ in range(30):
        assert (await client.get("/api/v1/health")).status_code == 200


async def test_cors_allowlist_does_not_include_a_wildcard(app):
    from fastapi.middleware.cors import CORSMiddleware

    cors = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert cors, "CORS middleware must be installed"
    assert "*" not in cors[0].kwargs["allow_origins"]
