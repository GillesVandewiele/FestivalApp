async def test_login_sets_an_httponly_cookie(client, make_user):
    await make_user("org@example.com", "hunter2hunter2")

    r = await client.post(
        "/api/v1/auth/login", json={"email": "org@example.com", "password": "hunter2hunter2"}
    )

    assert r.status_code == 200
    set_cookie = r.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=strict" in set_cookie


async def test_login_with_a_wrong_password_is_rejected(client, make_user):
    await make_user("org@example.com", "hunter2hunter2")
    r = await client.post(
        "/api/v1/auth/login", json={"email": "org@example.com", "password": "wrong"}
    )
    assert r.status_code == 401


async def test_login_for_an_unknown_email_is_rejected(client):
    r = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )
    assert r.status_code == 401


async def test_wrong_password_and_unknown_email_are_indistinguishable(client, make_user):
    """Otherwise the error message enumerates valid organiser accounts."""
    await make_user("org@example.com", "hunter2hunter2")
    a = await client.post(
        "/api/v1/auth/login", json={"email": "org@example.com", "password": "wrong"}
    )
    b = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
    )
    assert a.json() == b.json()


async def test_me_requires_authentication(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_returns_the_logged_in_user(client, make_user):
    await make_user("org@example.com", "hunter2hunter2")
    await client.post(
        "/api/v1/auth/login", json={"email": "org@example.com", "password": "hunter2hunter2"}
    )

    r = await client.get("/api/v1/auth/me")

    assert r.status_code == 200
    assert r.json()["email"] == "org@example.com"
    assert "password_hash" not in r.json()


async def test_logout_clears_the_session(client, make_user):
    await make_user("org@example.com", "hunter2hunter2")
    await client.post(
        "/api/v1/auth/login", json={"email": "org@example.com", "password": "hunter2hunter2"}
    )
    await client.post("/api/v1/auth/logout")

    assert (await client.get("/api/v1/auth/me")).status_code == 401
