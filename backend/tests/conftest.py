import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

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
