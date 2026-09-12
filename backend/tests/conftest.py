import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import Settings
from app.main import create_app
from app.middleware import limiter
from app.models.identity import User
from app.security import hash_password

REPO_ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def mongo_uri() -> str:
    """A real MongoDB. Uses CI's service container if present, else spawns one."""
    if uri := os.environ.get("MONGO_TEST_URI"):
        yield uri
        return

    mongod = subprocess.run(  # noqa: S603
        [str(REPO_ROOT / "scripts" / "dev-mongo.sh")],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    port = _free_port()
    dbpath = tempfile.mkdtemp(prefix="festival-mongo-")
    proc = subprocess.Popen(  # noqa: S603
        [mongod, "--dbpath", dbpath, "--port", str(port), "--bind_ip", "127.0.0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)
    else:
        proc.kill()
        raise RuntimeError("mongod failed to start")

    yield f"mongodb://127.0.0.1:{port}"
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture
async def db(mongo_uri: str):
    """A clean database per test."""
    client = AsyncIOMotorClient(mongo_uri)
    name = "festival_test"
    await client.drop_database(name)
    yield client[name]
    await client.drop_database(name)
    client.close()


@pytest.fixture
def settings(mongo_uri: str) -> "Settings":
    return Settings(
        _env_file=None,
        mongo_uri=mongo_uri,
        mongo_db="festival_test",
        jwt_secret="j" * 48,
        device_token_pepper="p" * 48,
        cors_origins=["https://pos.test"],
        cookie_secure=True,
    )


@pytest_asyncio.fixture
async def app(settings, db):
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest_asyncio.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver.local") as c:
        yield c


@pytest.fixture
def make_user(db):
    async def _make(email: str, password: str, role: str = "organizer") -> "User":
        user = User(email=email, password_hash=hash_password(password), role=role)
        await db.users.insert_one(user.to_mongo())
        return user

    return _make


@pytest_asyncio.fixture
async def auth_client(client, make_user):
    await make_user("organiser@example.com", "hunter2hunter2")
    await client.post(
        "/api/v1/auth/login",
        json={"email": "organiser@example.com", "password": "hunter2hunter2"},
    )
    return client


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """The limiter is a module-level singleton, so its counters leak between tests.

    Without this, the eleventh login in a suite run gets a 429 and every later test
    that needs a session fails with a confusing 401.
    """
    limiter.reset()
    yield
    limiter.reset()


pytest_plugins = ["tests.conftest_stats"]
