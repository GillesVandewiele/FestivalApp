# Foundation & Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A tested, deployable FastAPI backend holding the full festival data model, organiser authentication, tablet enrolment, and the idempotent offline-sync API.

**Architecture:** A single FastAPI service over MongoDB Atlas. Orders are an immutable event log keyed by a client-generated UUID, which makes offline sync idempotent — a tablet may retry any number of times without duplicating a sale. Two distinct authentication schemes coexist: cookie-based JWT sessions for organisers, and bearer device tokens for tablets. No business logic is pre-aggregated; statistics are computed on demand in a later plan.

**Tech Stack:** Python 3.12, FastAPI, Motor (async MongoDB), Pydantic v2, `uv`, argon2-cffi, PyJWT, slowapi, pytest + pytest-asyncio, MongoDB 8.0.

**Spec:** `docs/superpowers/specs/2026-09-12-festival-sales-app-design.md`

## How to work through this plan

The repository harness (`CLAUDE.md`, `.claude/rules/`, `Makefile`,
`.pre-commit-config.yaml`, `.gitleaks.toml`, `.claudeignore`) already exists. Read
`.claude/skills/using-festival-harness/SKILL.md` first; it maps each kind of task to the
rule that governs it.

- **One branch and one PR per task.** Branch from `origin/main`, named
  `task-N-<slug>`. Never commit to `main`
  ([`.claude/rules/base-branch.md`](../../../.claude/rules/base-branch.md)).
- The `git commit` steps below are the checkpoints **within** a task's branch. Push and
  open the PR at the end of the task, once its tests pass.
- CI must be green before merging. `make check` runs the same things locally.
- Write PR descriptions per
  [`.claude/rules/writing-for-humans.md`](../../../.claude/rules/writing-for-humans.md):
  no em-dashes, no marketing vocabulary.

```bash
git checkout origin/main -b task-3-database-indexes
# ... work, committing at each checkpoint ...
make check
git push -u origin task-3-database-indexes
gh pr create --fill
```

## Global Constraints

- **Python 3.12**; dependencies managed with `uv`, locked in `uv.lock` (committed).
- **The repository is public.** No secret, password, connection string, or pepper may ever appear in a committed file. `.env` is gitignored; `.env.example` holds placeholders only.
- **All IDs are strings.** Server-generated IDs are `uuid4().hex`; order IDs are client-generated UUIDv4 strings. No `ObjectId` crosses an API boundary.
- **All timestamps are timezone-aware UTC** `datetime` objects. Never naive.
- **`status` on an order is a one-way transition**: `confirmed → voided` is accepted; `voided → confirmed` must be rejected.
- **`device_id` on an incoming order is always overwritten** by the authenticated device's ID. Never trust the client's value.
- **`total_coupons` is always recomputed server-side** from the line items. Never trust the client's value.
- **Product `slug`** matches `^[a-z0-9][a-z0-9-]*$` and is unique per edition.
- Tests run against a **real MongoDB**, never a mock — the aggregations in later plans depend on genuine server behaviour.
- Every task ends with a commit. Commit messages use Conventional Commits.

---

### Task 1: Repository scaffold, local MongoDB, and CI

Sets up everything later tasks need: the Python project, a project-local MongoDB for tests (no Docker, no sudo), secret-scanning hooks, and a CI pipeline.

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_smoke.py`
- Create: `scripts/dev-mongo.sh`
- Create: `.github/workflows/ci.yml`
- Modify: `.gitignore`
- Already present (do not recreate): `.pre-commit-config.yaml`, `.gitleaks.toml`,
  `Makefile`, `.claudeignore`, `CLAUDE.md`, `.claude/`

**Interfaces:**
- Consumes: nothing.
- Produces: pytest fixtures `mongo_uri: str` (session-scoped) and `db: AsyncIOMotorDatabase` (function-scoped, dropped between tests).

- [ ] **Step 1: Create the Python project**

```bash
mkdir -p backend/app backend/tests scripts .github/workflows
touch backend/app/__init__.py backend/tests/__init__.py
```

`backend/pyproject.toml`:

```toml
[project]
name = "festival-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.118",
    "uvicorn[standard]>=0.34",
    "motor>=3.6",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "argon2-cffi>=23.1",
    "pyjwt>=2.10",
    "slowapi>=0.1.9",
    "python-multipart>=0.0.20",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.25",
    "httpx>=0.28",
    "ruff>=0.9",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "S"]
ignore = ["S101"]  # assert is fine in tests

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S105", "S106"]  # hardcoded test passwords are fine
```

- [ ] **Step 2: Write the MongoDB bootstrap script**

`scripts/dev-mongo.sh` — downloads a real `mongod` into a gitignored `.tools/`, so tests need neither Docker nor sudo.

```bash
#!/usr/bin/env bash
# Download and run a project-local MongoDB for tests. No Docker, no sudo.
set -euo pipefail

MONGO_VERSION="8.0.15"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/.tools"
MONGO_DIR="$TOOLS/mongodb-linux-x86_64-ubuntu2404-$MONGO_VERSION"
MONGOD="$MONGO_DIR/bin/mongod"

if [ ! -x "$MONGOD" ]; then
  echo "Downloading MongoDB $MONGO_VERSION..."
  mkdir -p "$TOOLS"
  curl -fsSL "https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2404-$MONGO_VERSION.tgz" \
    | tar -xz -C "$TOOLS"
fi

echo "$MONGOD"
```

```bash
chmod +x scripts/dev-mongo.sh
```

- [ ] **Step 3: Update .gitignore for the tools directory**

Append to `.gitignore`:

```
# ---- local test tooling ----
.tools/
```

- [ ] **Step 4: Write the test fixtures**

`backend/tests/conftest.py` — spawns a local `mongod` on a free port, or uses `MONGO_TEST_URI` when CI provides a service container.

```python
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
        return uri

    mongod = subprocess.run(
        [str(REPO_ROOT / "scripts" / "dev-mongo.sh")],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    port = _free_port()
    dbpath = tempfile.mkdtemp(prefix="festival-mongo-")
    proc = subprocess.Popen(
        [mongod, "--dbpath", dbpath, "--port", str(port), "--bind_ip", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    uri = f"mongodb://127.0.0.1:{port}"
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)
    else:
        proc.kill()
        raise RuntimeError("mongod failed to start")

    yield uri
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
```

- [ ] **Step 5: Write the failing smoke test**

`backend/tests/test_smoke.py`:

```python
async def test_mongodb_is_reachable(db):
    await db.ping_check.insert_one({"_id": "x", "ok": True})
    doc = await db.ping_check.find_one({"_id": "x"})
    assert doc["ok"] is True
```

- [ ] **Step 6: Run it to verify the whole harness works**

```bash
cd backend && uv sync && uv run pytest tests/test_smoke.py -v
```

Expected: PASS. The first run downloads MongoDB (~100 MB), so allow a minute.

- [ ] **Step 7: Install the pre-commit hooks**

`.pre-commit-config.yaml` and `.gitleaks.toml` are already in the repository. They run
`gitleaks`, plus `ruff check`, `ruff format --check` and `uv lock --check` through `uv`,
so the linter version always matches `uv.lock`.

`pre-commit` is currently broken on this machine (`cannot execute: required file not
found`), so reinstall it through `uv`:

```bash
uv tool install --force pre-commit
pre-commit install
pre-commit run --all-files
```

Expected: gitleaks passes; ruff may reformat files. Commit any reformatting.

- [ ] **Step 8: Write the CI workflow**

`.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      mongodb:
        image: mongo:8.0
        ports: ["27017:27017"]
    env:
      MONGO_TEST_URI: mongodb://127.0.0.1:27017
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.12"
      - run: uv sync --frozen
        working-directory: backend
      - run: uv lock --check
        working-directory: backend
      - run: uv run ruff check .
        working-directory: backend
      - run: uv run ruff format --check .
        working-directory: backend
      - run: uv run pytest --tb=short
        working-directory: backend

  secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 9: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app backend/tests \
        scripts/dev-mongo.sh .github/workflows/ci.yml .gitignore
git commit -m "chore: scaffold backend, local MongoDB harness, and CI"
git push
```

- [ ] **Step 10: Verify CI passes**

```bash
gh run watch
```

Expected: both jobs green. Do not proceed until they are.

---

### Task 2: Settings and configuration

Every secret enters through the environment. This task makes that structural rather than a convention people remember.

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/.env.example`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Settings` (pydantic-settings model) and `get_settings() -> Settings` (LRU-cached). Fields: `mongo_uri: str`, `mongo_db: str`, `jwt_secret: str`, `device_token_pepper: str`, `cors_origins: list[str]`, `access_token_ttl_minutes: int`, `cookie_secure: bool`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_config.py`:

```python
import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGO_DB", "festival")
    monkeypatch.setenv("JWT_SECRET", "s" * 32)
    monkeypatch.setenv("DEVICE_TOKEN_PEPPER", "p" * 32)
    monkeypatch.setenv("CORS_ORIGINS", '["https://pos.example.com"]')

    s = Settings()

    assert s.mongo_db == "festival"
    assert s.cors_origins == ["https://pos.example.com"]
    assert s.access_token_ttl_minutes == 720
    assert s.cookie_secure is True


def test_missing_secret_is_a_startup_error(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("DEVICE_TOKEN_PEPPER", "p" * 32)
    with pytest.raises(ValidationError):
        Settings()


def test_short_secrets_are_rejected(monkeypatch):
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("JWT_SECRET", "tooshort")
    monkeypatch.setenv("DEVICE_TOKEN_PEPPER", "p" * 32)
    with pytest.raises(ValidationError):
        Settings()
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && uv run pytest tests/test_config.py -v
```

Expected: FAIL, `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Implement**

`backend/app/config.py`:

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from the environment. Nothing is defaulted to a secret."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str
    mongo_db: str = "festival"

    jwt_secret: str = Field(min_length=32)
    device_token_pepper: str = Field(min_length=32)

    cors_origins: list[str] = Field(default_factory=list)
    access_token_ttl_minutes: int = 720
    cookie_secure: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run to verify it passes**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Write the example environment file**

`backend/.env.example` — placeholders only. Generate real values with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.

```bash
# Copy to .env and fill in. NEVER commit .env.
MONGO_URI=mongodb+srv://USER:PASSWORD@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_DB=festival

# Generate each with: python3 -c "import secrets; print(secrets.token_urlsafe(48))"
JWT_SECRET=replace-me-with-a-48-byte-random-string
DEVICE_TOKEN_PEPPER=replace-me-with-a-different-48-byte-random-string

CORS_ORIGINS=["https://pos.example.pages.dev","https://admin.example.pages.dev"]
ACCESS_TOKEN_TTL_MINUTES=720
COOKIE_SECURE=true
```

- [ ] **Step 6: Verify .env is actually ignored**

```bash
cd .. && cp backend/.env.example backend/.env && git status --porcelain backend/.env
```

Expected: **empty output**. If `.env` appears, stop and fix `.gitignore` before continuing.

- [ ] **Step 7: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py backend/.env.example
git commit -m "feat: environment-only settings with secret length validation"
```

---

### Task 3: Database connection and indexes

**Files:**
- Create: `backend/app/db.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Consumes: `get_settings()` from Task 2.
- Produces: `get_client(uri: str) -> AsyncIOMotorClient`, `ensure_indexes(db) -> None`, and the constant `COLLECTIONS: tuple[str, ...]`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_db.py`:

```python
from app.db import ensure_indexes


async def _index_keys(db, collection: str) -> set[tuple]:
    info = await db[collection].index_information()
    return {tuple(tuple(k) for k in spec["key"]) for spec in info.values()}


async def test_ensure_indexes_creates_order_indexes(db):
    await ensure_indexes(db)
    keys = await _index_keys(db, "orders")
    assert (("edition_id", 1), ("created_at", 1)) in keys
    assert (("edition_id", 1), ("status", 1), ("created_at", 1)) in keys
    assert (("edition_id", 1), ("bar_id", 1), ("created_at", 1)) in keys


async def test_product_slug_is_unique_per_edition(db):
    await ensure_indexes(db)
    await db.products.insert_one({"_id": "a", "edition_id": "e1", "slug": "jupiler"})
    from pymongo.errors import DuplicateKeyError
    import pytest

    with pytest.raises(DuplicateKeyError):
        await db.products.insert_one({"_id": "b", "edition_id": "e1", "slug": "jupiler"})


async def test_same_slug_allowed_in_a_different_edition(db):
    """Year-over-year comparison depends on slugs repeating across editions."""
    await ensure_indexes(db)
    await db.products.insert_one({"_id": "a", "edition_id": "e2026", "slug": "jupiler"})
    await db.products.insert_one({"_id": "b", "edition_id": "e2027", "slug": "jupiler"})
    assert await db.products.count_documents({"slug": "jupiler"}) == 2


async def test_ensure_indexes_is_idempotent(db):
    await ensure_indexes(db)
    await ensure_indexes(db)  # must not raise
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_db.py -v
```

Expected: FAIL, `ModuleNotFoundError: No module named 'app.db'`.

- [ ] **Step 3: Implement**

`backend/app/db.py`:

```python
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, IndexModel

COLLECTIONS: tuple[str, ...] = (
    "editions", "bars", "products", "staff",
    "orders", "stockouts", "users", "devices",
)


def get_client(uri: str) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(uri, tz_aware=True, uuidRepresentation="standard")


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Idempotent. Safe to run on every startup."""
    await db.orders.create_indexes([
        IndexModel([("edition_id", ASCENDING), ("created_at", ASCENDING)]),
        IndexModel([("edition_id", ASCENDING), ("status", ASCENDING),
                    ("created_at", ASCENDING)]),
        IndexModel([("edition_id", ASCENDING), ("bar_id", ASCENDING),
                    ("created_at", ASCENDING)]),
        IndexModel([("edition_id", ASCENDING), ("staff_id", ASCENDING)]),
    ])
    await db.products.create_indexes([
        IndexModel([("edition_id", ASCENDING), ("slug", ASCENDING)], unique=True),
        IndexModel([("slug", ASCENDING)]),
    ])
    await db.devices.create_indexes([
        IndexModel([("token_hash", ASCENDING)], unique=True),
    ])
    await db.users.create_indexes([
        IndexModel([("email", ASCENDING)], unique=True),
    ])
    await db.stockouts.create_indexes([
        IndexModel([("edition_id", ASCENDING), ("product_id", ASCENDING),
                    ("out_at", ASCENDING)]),
    ])
```

- [ ] **Step 4: Run to verify it passes**

```bash
uv run pytest tests/test_db.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/tests/test_db.py
git commit -m "feat: database connection and index definitions"
```

---

### Task 4: Security primitives

Password hashing, device-token hashing, and JWT issuance — isolated from any web framework so they can be tested directly.

**Files:**
- Create: `backend/app/security.py`
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Consumes: nothing (pepper and secret are passed in as arguments, never read from global state — this keeps the module pure and testable).
- Produces:
  - `hash_password(plain: str) -> str`
  - `verify_password(plain: str, hashed: str) -> bool`
  - `generate_device_token() -> str`
  - `hash_device_token(token: str, pepper: str) -> str`
  - `verify_device_token(token: str, token_hash: str, pepper: str) -> bool`
  - `create_access_token(subject: str, secret: str, ttl_minutes: int) -> str`
  - `decode_access_token(token: str, secret: str) -> str` (returns the subject; raises `InvalidTokenError`)

- [ ] **Step 1: Write the failing test**

`backend/tests/test_security.py`:

```python
import pytest
from jwt import ExpiredSignatureError, InvalidSignatureError

from app.security import (
    create_access_token,
    decode_access_token,
    generate_device_token,
    hash_device_token,
    hash_password,
    verify_device_token,
    verify_password,
)

PEPPER = "pepper" * 8


def test_password_round_trip():
    hashed = hash_password("correct horse")
    assert hashed != "correct horse"
    assert verify_password("correct horse", hashed)
    assert not verify_password("wrong horse", hashed)


def test_password_hashes_are_salted():
    """Two identical passwords must not produce the same hash."""
    assert hash_password("same") != hash_password("same")


def test_device_tokens_are_long_and_unique():
    a, b = generate_device_token(), generate_device_token()
    assert a != b
    assert len(a) >= 32


def test_device_token_round_trip():
    token = generate_device_token()
    h = hash_device_token(token, PEPPER)
    assert h != token
    assert verify_device_token(token, h, PEPPER)
    assert not verify_device_token("other-token", h, PEPPER)


def test_device_token_hash_depends_on_the_pepper():
    """A stolen database is useless without the pepper, which lives only in env."""
    token = generate_device_token()
    assert hash_device_token(token, PEPPER) != hash_device_token(token, "other" * 8)


def test_access_token_round_trip():
    token = create_access_token("user-1", "secret" * 8, ttl_minutes=60)
    assert decode_access_token(token, "secret" * 8) == "user-1"


def test_access_token_rejects_a_wrong_signature():
    token = create_access_token("user-1", "secret" * 8, ttl_minutes=60)
    with pytest.raises(InvalidSignatureError):
        decode_access_token(token, "different" * 8)


def test_expired_access_token_is_rejected():
    token = create_access_token("user-1", "secret" * 8, ttl_minutes=-1)
    with pytest.raises(ExpiredSignatureError):
        decode_access_token(token, "secret" * 8)
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_security.py -v
```

Expected: FAIL, `ModuleNotFoundError: No module named 'app.security'`.

- [ ] **Step 3: Implement**

`backend/app/security.py`:

```python
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def generate_device_token() -> str:
    return secrets.token_urlsafe(32)


def hash_device_token(token: str, pepper: str) -> str:
    """HMAC rather than argon2: this runs on every tablet request and must be fast.

    Device tokens are already high-entropy, so the slow-hash protection that
    passwords need (guarding weak human choices) buys nothing here.
    """
    return hmac.new(pepper.encode(), token.encode(), hashlib.sha256).hexdigest()


def verify_device_token(token: str, token_hash: str, pepper: str) -> bool:
    return hmac.compare_digest(hash_device_token(token, pepper), token_hash)


def create_access_token(subject: str, secret: str, ttl_minutes: int) -> str:
    now = datetime.now(UTC)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=ttl_minutes)}
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> str:
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    return payload["sub"]
```

- [ ] **Step 4: Run to verify it passes**

```bash
uv run pytest tests/test_security.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/security.py backend/tests/test_security.py
git commit -m "feat: password, device token, and JWT primitives"
```

---

### Task 5: Domain models

All eight collections as Pydantic v2 models. Declarative, but the validators encode real rules and get tested.

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/common.py`
- Create: `backend/app/models/catalog.py` (edition, bar, product, staff)
- Create: `backend/app/models/order.py` (order, order item, void info, stockout)
- Create: `backend/app/models/identity.py` (user, device)
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `common.py`: `new_id() -> str`, `utcnow() -> datetime`, `MongoModel` (base with `populate_by_name=True`, `_id` aliased to `id`)
  - `catalog.py`: `Edition`, `Bar`, `Product`, `PurchaseUnit`, `Staff`
  - `order.py`: `OrderItem`, `VoidInfo`, `VoidActor`, `Order`, `OrderIn`, `Stockout`, `StockoutIn`
  - `identity.py`: `User`, `Device`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_models.py`:

```python
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.catalog import Edition, Product, PurchaseUnit
from app.models.order import Order, OrderIn, OrderItem


def test_edition_requires_a_coupon_value():
    e = Edition(name="Festival 2026", year=2026, coupon_value_eur=2.50,
                starts_at=datetime(2026, 7, 1, tzinfo=UTC),
                ends_at=datetime(2026, 7, 3, tzinfo=UTC))
    assert e.coupon_value_eur == 2.50
    assert e.timezone == "Europe/Brussels"
    assert e.id  # auto-generated


def test_product_slug_must_be_lowercase_kebab():
    p = Product(edition_id="e1", slug="gin-tonic", name="Gin-Tonic",
                category="cocktail", price_coupons=4)
    assert p.slug == "gin-tonic"

    with pytest.raises(ValidationError):
        Product(edition_id="e1", slug="Gin Tonic", name="x",
                category="cocktail", price_coupons=4)


def test_product_cost_price_is_optional_until_invoices_arrive():
    """Cost is entered after the festival; margin reports must tolerate its absence."""
    p = Product(edition_id="e1", slug="water", name="Water",
                category="fris", price_coupons=1)
    assert p.cost_price_eur is None
    assert p.purchase_unit is None


def test_product_accepts_a_purchase_unit():
    p = Product(edition_id="e1", slug="jupiler", name="Jupiler", category="bier",
                price_coupons=1, cost_price_eur=0.62,
                purchase_unit=PurchaseUnit(name="bak", size=24))
    assert p.purchase_unit.size == 24


def test_negative_price_is_rejected():
    with pytest.raises(ValidationError):
        Product(edition_id="e1", slug="x", name="x", category="bier",
                price_coupons=-1)


def test_order_item_requires_a_positive_quantity():
    with pytest.raises(ValidationError):
        OrderItem(product_id="p1", slug="jupiler", name="Jupiler",
                  qty=0, unit_price_coupons=1)


def test_order_defaults_to_confirmed_with_no_void_block():
    o = Order(id="uuid-1", edition_id="e1", bar_id="b1", staff_id="s1",
              device_id="d1", items=[], total_coupons=0,
              created_at=datetime.now(UTC), received_at=datetime.now(UTC))
    assert o.status == "confirmed"
    assert o.void is None


def test_order_in_does_not_accept_a_device_id():
    """device_id is taken from the authenticated device, never from the payload."""
    assert "device_id" not in OrderIn.model_fields


def test_order_in_does_not_accept_a_total():
    """total_coupons is recomputed server-side, never trusted."""
    assert "total_coupons" not in OrderIn.model_fields
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_models.py -v
```

Expected: FAIL, `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Implement the shared base**

```bash
touch backend/app/models/__init__.py
```

`backend/app/models/common.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def new_id() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class MongoModel(BaseModel):
    """Base for documents. `id` maps to Mongo's `_id`."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(default_factory=new_id, alias="_id")

    def to_mongo(self) -> dict:
        return self.model_dump(by_alias=True)
```

- [ ] **Step 4: Implement the catalog models**

`backend/app/models/catalog.py`:

```python
from datetime import datetime

from pydantic import BaseModel, Field

from .common import MongoModel

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]*$"


class Edition(MongoModel):
    name: str
    year: int
    starts_at: datetime
    ends_at: datetime
    timezone: str = "Europe/Brussels"
    coupon_value_eur: float = Field(ge=0)
    is_active: bool = True


class Bar(MongoModel):
    edition_id: str
    name: str
    sort_order: int = 0
    active: bool = True


class PurchaseUnit(BaseModel):
    name: str
    size: int = Field(ge=1)


class Product(MongoModel):
    edition_id: str
    slug: str = Field(pattern=SLUG_PATTERN)
    name: str
    category: str
    price_coupons: int = Field(ge=0)

    # Accounting attributes, often only known after the festival.
    cost_price_eur: float | None = Field(default=None, ge=0)
    purchase_unit: PurchaseUnit | None = None
    purchased_qty: int | None = Field(default=None, ge=0)
    leftover_qty: int | None = Field(default=None, ge=0)

    available_at: list[str] = Field(default_factory=list)
    sort_order: int = 0
    active: bool = True


class Staff(MongoModel):
    edition_id: str
    name: str
    active: bool = True
```

- [ ] **Step 5: Implement the order models**

`backend/app/models/order.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .common import MongoModel

OrderStatus = Literal["confirmed", "voided"]


class OrderItem(BaseModel):
    product_id: str
    slug: str
    name: str                                   # snapshotted at sale time
    qty: int = Field(ge=1)
    unit_price_coupons: int = Field(ge=0)       # snapshotted at sale time


class VoidActor(BaseModel):
    type: Literal["staff", "user"]
    id: str


class VoidInfo(BaseModel):
    at: datetime
    by: VoidActor
    reason: str | None = None                   # required for an organiser void


class OrderIn(BaseModel):
    """What a tablet sends. Deliberately excludes device_id and total_coupons."""

    model_config = {"extra": "forbid"}

    id: str
    edition_id: str
    bar_id: str
    staff_id: str
    items: list[OrderItem]
    created_at: datetime
    status: OrderStatus = "confirmed"
    void: VoidInfo | None = None


class Order(MongoModel):
    edition_id: str
    bar_id: str
    staff_id: str
    device_id: str
    items: list[OrderItem]
    total_coupons: int = Field(ge=0)
    created_at: datetime
    received_at: datetime
    status: OrderStatus = "confirmed"
    void: VoidInfo | None = None


class StockoutIn(BaseModel):
    model_config = {"extra": "forbid"}

    id: str
    product_id: str
    out_at: datetime
    back_at: datetime | None = None


class Stockout(MongoModel):
    edition_id: str
    bar_id: str
    product_id: str
    slug: str
    out_at: datetime
    back_at: datetime | None = None
```

- [ ] **Step 6: Implement the identity models**

`backend/app/models/identity.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field

from .common import MongoModel, utcnow


class User(MongoModel):
    email: EmailStr
    password_hash: str
    role: Literal["organizer", "admin"] = "organizer"
    created_at: datetime = Field(default_factory=utcnow)


class Device(MongoModel):
    edition_id: str
    bar_id: str
    label: str
    token_hash: str
    enrolled_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None
```

`EmailStr` needs an extra dependency:

```bash
cd backend && uv add "pydantic[email]"
```

- [ ] **Step 7: Run to verify it passes**

```bash
uv run pytest tests/test_models.py -v
```

Expected: 9 passed.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models backend/tests/test_models.py backend/pyproject.toml backend/uv.lock
git commit -m "feat: domain models for all eight collections"
```

---

### Task 6: Application factory and organiser authentication

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/deps.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/auth.py`
- Test: `backend/tests/test_auth.py`
- Modify: `backend/tests/conftest.py` (add the `client` fixture)

**Interfaces:**
- Consumes: `Settings` (Task 2), `ensure_indexes` (Task 3), all of `security` (Task 4), `User` (Task 5).
- Produces:
  - `main.py`: `create_app(settings: Settings) -> FastAPI`
  - `deps.py`: `get_db(request) -> AsyncIOMotorDatabase`, `get_current_user(request, db) -> User`
  - `routers/auth.py`: router mounted at `/api/v1/auth` with `POST /login`, `POST /logout`, `GET /me`
  - conftest: fixtures `app`, `client` (an `httpx.AsyncClient`), and `make_user(email, password, role) -> User`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_auth.py`:

```python
async def test_login_sets_an_httponly_cookie(client, make_user):
    await make_user("org@example.com", "hunter2hunter2")

    r = await client.post("/api/v1/auth/login",
                          json={"email": "org@example.com", "password": "hunter2hunter2"})

    assert r.status_code == 200
    cookie = r.cookies.jar._cookies["testserver.local"]["/"]["session"]
    assert cookie.has_nonstandard_attr("HttpOnly")
    assert cookie.secure


async def test_login_with_a_wrong_password_is_rejected(client, make_user):
    await make_user("org@example.com", "hunter2hunter2")
    r = await client.post("/api/v1/auth/login",
                          json={"email": "org@example.com", "password": "wrong"})
    assert r.status_code == 401


async def test_login_for_an_unknown_email_is_rejected(client):
    r = await client.post("/api/v1/auth/login",
                          json={"email": "nobody@example.com", "password": "whatever"})
    assert r.status_code == 401


async def test_wrong_password_and_unknown_email_are_indistinguishable(client, make_user):
    """Otherwise the error message enumerates valid organiser accounts."""
    await make_user("org@example.com", "hunter2hunter2")
    a = await client.post("/api/v1/auth/login",
                          json={"email": "org@example.com", "password": "wrong"})
    b = await client.post("/api/v1/auth/login",
                          json={"email": "nobody@example.com", "password": "wrong"})
    assert a.json() == b.json()


async def test_me_requires_authentication(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_returns_the_logged_in_user(client, make_user):
    await make_user("org@example.com", "hunter2hunter2")
    await client.post("/api/v1/auth/login",
                      json={"email": "org@example.com", "password": "hunter2hunter2"})

    r = await client.get("/api/v1/auth/me")

    assert r.status_code == 200
    assert r.json()["email"] == "org@example.com"
    assert "password_hash" not in r.json()


async def test_logout_clears_the_session(client, make_user):
    await make_user("org@example.com", "hunter2hunter2")
    await client.post("/api/v1/auth/login",
                      json={"email": "org@example.com", "password": "hunter2hunter2"})
    await client.post("/api/v1/auth/logout")

    assert (await client.get("/api/v1/auth/me")).status_code == 401
```

- [ ] **Step 2: Add the app fixtures to conftest**

Append to `backend/tests/conftest.py`:

```python
import httpx
import pytest_asyncio

from app.config import Settings
from app.main import create_app
from app.models.identity import User
from app.security import hash_password


@pytest.fixture
def settings(mongo_uri: str) -> Settings:
    return Settings(
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
    async with httpx.AsyncClient(
        transport=transport, base_url="https://testserver.local"
    ) as c:
        yield c


@pytest.fixture
def make_user(db):
    async def _make(email: str, password: str, role: str = "organizer") -> User:
        user = User(email=email, password_hash=hash_password(password), role=role)
        await db.users.insert_one(user.to_mongo())
        return user

    return _make
```

- [ ] **Step 3: Run to verify it fails**

```bash
uv run pytest tests/test_auth.py -v
```

Expected: FAIL, `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 4: Implement the dependencies**

`backend/app/deps.py`:

```python
from fastapi import Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from .config import Settings
from .models.identity import User
from .security import decode_access_token

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
)


def get_settings_from_app(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.db


async def get_current_user(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings_from_app),
) -> User:
    token = request.cookies.get("session")
    if not token:
        raise CREDENTIALS_ERROR
    try:
        user_id = decode_access_token(token, settings.jwt_secret)
    except Exception as exc:
        raise CREDENTIALS_ERROR from exc

    doc = await db.users.find_one({"_id": user_id})
    if doc is None:
        raise CREDENTIALS_ERROR
    return User(**doc)
```

- [ ] **Step 5: Implement the auth router**

`backend/app/routers/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr

from ..config import Settings
from ..deps import get_current_user, get_db, get_settings_from_app
from ..models.identity import User
from ..security import create_access_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: str


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings_from_app),
) -> UserOut:
    doc = await db.users.find_one({"email": body.email})
    # One identical error for both cases, so the response cannot enumerate accounts.
    if doc is None or not verify_password(body.password, doc["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user = User(**doc)
    token = create_access_token(user.id, settings.jwt_secret,
                                settings.access_token_ttl_minutes)
    response.set_cookie(
        "session", token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.access_token_ttl_minutes * 60,
    )
    return UserOut(id=user.id, email=user.email, role=user.role)


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie("session", httponly=True, samesite="strict")
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(id=user.id, email=user.email, role=user.role)
```

- [ ] **Step 6: Implement the application factory**

```bash
touch backend/app/routers/__init__.py
```

`backend/app/main.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .db import ensure_indexes, get_client
from .routers import auth


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        client = get_client(settings.mongo_uri)
        app.state.settings = settings
        app.state.db = client[settings.mongo_db]
        await ensure_indexes(app.state.db)
        yield
        client.close()

    app = FastAPI(title="Festival Sales API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,   # explicit allowlist, never "*"
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(auth.router)

    @app.get("/api/v1/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app
```

- [ ] **Step 7: Run to verify it passes**

```bash
uv run pytest tests/test_auth.py -v
```

Expected: 7 passed.

- [ ] **Step 8: Run the whole suite**

```bash
uv run pytest -v
```

Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add backend/app/main.py backend/app/deps.py backend/app/routers \
        backend/tests/test_auth.py backend/tests/conftest.py
git commit -m "feat: app factory and organiser cookie authentication"
```

---

### Task 7: Admin catalog CRUD

Editions, bars, products and staff. All routes require an authenticated organiser.

**Files:**
- Create: `backend/app/routers/admin_catalog.py`
- Test: `backend/tests/test_admin_catalog.py`
- Modify: `backend/app/main.py` (mount the router)
- Modify: `backend/tests/conftest.py` (add `auth_client`)

**Interfaces:**
- Consumes: `get_current_user`, `get_db`, all catalog models.
- Produces: router at `/api/v1/admin` with, for each of `editions`, `bars`, `products`, `staff`: `GET /{plural}`, `POST /{plural}`, `PATCH /{plural}/{id}`, `DELETE /{plural}/{id}`. Also conftest fixture `auth_client` (a logged-in `httpx.AsyncClient`).

- [ ] **Step 1: Add the authenticated-client fixture**

Append to `backend/tests/conftest.py`:

```python
@pytest_asyncio.fixture
async def auth_client(client, make_user):
    await make_user("organiser@example.com", "hunter2hunter2")
    await client.post("/api/v1/auth/login",
                      json={"email": "organiser@example.com",
                            "password": "hunter2hunter2"})
    return client
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_admin_catalog.py`:

```python
EDITION = {
    "name": "Festival 2026", "year": 2026,
    "starts_at": "2026-07-01T14:00:00Z", "ends_at": "2026-07-03T02:00:00Z",
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

    r = await auth_client.patch(f"/api/v1/admin/editions/{eid}",
                                json={"coupon_value_eur": 3.00})

    assert r.status_code == 200
    assert r.json()["coupon_value_eur"] == 3.00
    assert r.json()["name"] == "Festival 2026"   # untouched fields survive


async def test_delete_an_edition(auth_client):
    eid = (await auth_client.post("/api/v1/admin/editions", json=EDITION)).json()["id"]
    assert (await auth_client.delete(f"/api/v1/admin/editions/{eid}")).status_code == 204
    assert (await auth_client.get("/api/v1/admin/editions")).json() == []


async def test_updating_something_that_does_not_exist_is_404(auth_client):
    r = await auth_client.patch("/api/v1/admin/editions/nope", json={"year": 2027})
    assert r.status_code == 404


async def test_duplicate_product_slug_in_one_edition_is_rejected(auth_client):
    eid = (await auth_client.post("/api/v1/admin/editions", json=EDITION)).json()["id"]
    product = {"edition_id": eid, "slug": "jupiler", "name": "Jupiler",
               "category": "bier", "price_coupons": 1}

    assert (await auth_client.post("/api/v1/admin/products", json=product)).status_code == 201
    r = await auth_client.post("/api/v1/admin/products", json=product)
    assert r.status_code == 409


async def test_products_can_be_filtered_by_edition(auth_client):
    a = (await auth_client.post("/api/v1/admin/editions", json=EDITION)).json()["id"]
    b = (await auth_client.post("/api/v1/admin/editions",
                                json={**EDITION, "name": "Festival 2027",
                                      "year": 2027})).json()["id"]
    for eid, slug in ((a, "jupiler"), (b, "cava")):
        await auth_client.post("/api/v1/admin/products",
                               json={"edition_id": eid, "slug": slug, "name": slug,
                                     "category": "x", "price_coupons": 1})

    listed = (await auth_client.get(f"/api/v1/admin/products?edition_id={a}")).json()
    assert [p["slug"] for p in listed] == ["jupiler"]


async def test_invalid_slug_is_rejected(auth_client):
    eid = (await auth_client.post("/api/v1/admin/editions", json=EDITION)).json()["id"]
    r = await auth_client.post("/api/v1/admin/products",
                               json={"edition_id": eid, "slug": "Gin Tonic",
                                     "name": "x", "category": "y", "price_coupons": 1})
    assert r.status_code == 422
```

- [ ] **Step 3: Run to verify it fails**

```bash
uv run pytest tests/test_admin_catalog.py -v
```

Expected: FAIL — 404s, because the router is not mounted.

- [ ] **Step 4: Implement the router**

`backend/app/routers/admin_catalog.py` — one generic factory, so four resources do not become four copies of the same code.

```python
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from ..deps import get_current_user, get_db
from ..models.catalog import Bar, Edition, Product, Staff
from ..models.common import MongoModel

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_user)],
)

RESOURCES: dict[str, tuple[str, type[MongoModel]]] = {
    "editions": ("editions", Edition),
    "bars": ("bars", Bar),
    "products": ("products", Product),
    "staff": ("staff", Staff),
}


def _serialise(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


def _register(plural: str, collection: str, model: type[MongoModel]) -> None:
    @router.get(f"/{plural}", name=f"list_{plural}")
    async def list_items(
        edition_id: str | None = Query(default=None),
        db: AsyncIOMotorDatabase = Depends(get_db),
    ) -> list[dict]:
        query = {"edition_id": edition_id} if edition_id else {}
        return [_serialise(d) async for d in db[collection].find(query)]

    @router.post(f"/{plural}", status_code=status.HTTP_201_CREATED, name=f"create_{plural}")
    async def create_item(
        body: model,  # type: ignore[valid-type]
        db: AsyncIOMotorDatabase = Depends(get_db),
    ) -> dict:
        try:
            await db[collection].insert_one(body.to_mongo())
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A {plural[:-1]} with this key already exists",
            ) from exc
        return _serialise(body.to_mongo())

    @router.patch(f"/{plural}/{{item_id}}", name=f"update_{plural}")
    async def update_item(
        item_id: str,
        body: dict[str, Any],
        db: AsyncIOMotorDatabase = Depends(get_db),
    ) -> dict:
        body.pop("_id", None)
        body.pop("id", None)
        doc = await db[collection].find_one_and_update(
            {"_id": item_id}, {"$set": body}, return_document=True
        )
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"{plural[:-1]} not found")
        return _serialise(doc)

    @router.delete(f"/{plural}/{{item_id}}", status_code=status.HTTP_204_NO_CONTENT,
                   name=f"delete_{plural}")
    async def delete_item(
        item_id: str,
        db: AsyncIOMotorDatabase = Depends(get_db),
    ) -> Response:
        result = await db[collection].delete_one({"_id": item_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"{plural[:-1]} not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)


for _plural, (_collection, _model) in RESOURCES.items():
    _register(_plural, _collection, _model)
```

`find_one_and_update` needs `return_document=ReturnDocument.AFTER`; the `True` above is the same value. Import it explicitly for clarity:

```python
from pymongo import ReturnDocument
```

and use `return_document=ReturnDocument.AFTER`.

- [ ] **Step 5: Mount the router**

In `backend/app/main.py`, change the import and the mount:

```python
from .routers import admin_catalog, auth
...
    app.include_router(auth.router)
    app.include_router(admin_catalog.router)
```

- [ ] **Step 6: Run to verify it passes**

```bash
uv run pytest tests/test_admin_catalog.py -v
```

Expected: 8 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/admin_catalog.py backend/app/main.py \
        backend/tests/test_admin_catalog.py backend/tests/conftest.py
git commit -m "feat: admin CRUD for editions, bars, products and staff"
```

---

### Task 8: Device enrolment and revocation

**Files:**
- Create: `backend/app/routers/admin_devices.py`
- Test: `backend/tests/test_devices.py`
- Modify: `backend/app/deps.py` (add `get_current_device`)
- Modify: `backend/app/main.py` (mount the router)

**Interfaces:**
- Consumes: `Device` model, device-token primitives, `get_current_user`.
- Produces:
  - `POST /api/v1/admin/devices/enroll` — body `{edition_id, bar_id, label}`, returns `{id, label, token}`. **The plaintext token is returned exactly once.**
  - `POST /api/v1/admin/devices/{id}/revoke` — 204.
  - `GET /api/v1/admin/devices` — list, never including tokens.
  - `deps.get_current_device(request, db, settings) -> Device` — reads `Authorization: Bearer <token>`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_devices.py`:

```python
import pytest


@pytest.fixture
async def enrolled(auth_client):
    r = await auth_client.post("/api/v1/admin/devices/enroll",
                               json={"edition_id": "e1", "bar_id": "b1",
                                     "label": "Tablet bar 1"})
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
    r = await client.post("/api/v1/admin/devices/enroll",
                          json={"edition_id": "e1", "bar_id": "b1", "label": "x"})
    assert r.status_code == 401


async def test_a_valid_device_token_authenticates(client, enrolled):
    r = await client.get("/api/v1/time",
                         headers={"Authorization": f"Bearer {enrolled['token']}"})
    assert r.status_code == 200


async def test_an_unknown_device_token_is_rejected(client):
    r = await client.get("/api/v1/time", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


async def test_a_missing_token_is_rejected(client):
    assert (await client.get("/api/v1/time")).status_code == 401


async def test_a_revoked_device_is_rejected(client, auth_client, enrolled):
    r = await auth_client.post(f"/api/v1/admin/devices/{enrolled['id']}/revoke")
    assert r.status_code == 204

    r = await client.get("/api/v1/time",
                         headers={"Authorization": f"Bearer {enrolled['token']}"})
    assert r.status_code == 401
```

> Note: these tests exercise `GET /api/v1/time`, which Task 9 implements. Expect the
> last four to fail until Task 9 is done — that is intentional, they pin the contract
> Task 9 must satisfy.

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_devices.py -v
```

Expected: FAIL — the enrol endpoint does not exist.

- [ ] **Step 3: Add the device dependency**

Append to `backend/app/deps.py`:

```python
from .models.identity import Device
from .security import hash_device_token


async def get_current_device(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings_from_app),
) -> Device:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise CREDENTIALS_ERROR

    doc = await db.devices.find_one({
        "token_hash": hash_device_token(token, settings.device_token_pepper),
        "revoked_at": None,
    })
    if doc is None:
        raise CREDENTIALS_ERROR

    await db.devices.update_one({"_id": doc["_id"]},
                                {"$set": {"last_seen_at": utcnow()}})
    return Device(**doc)
```

Add to that file's imports:

```python
from .models.common import utcnow
```

- [ ] **Step 4: Implement the router**

`backend/app/routers/admin_devices.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from ..config import Settings
from ..deps import get_current_user, get_db, get_settings_from_app
from ..models.common import utcnow
from ..models.identity import Device
from ..security import generate_device_token, hash_device_token

router = APIRouter(
    prefix="/api/v1/admin/devices",
    tags=["devices"],
    dependencies=[Depends(get_current_user)],
)


class EnrollRequest(BaseModel):
    edition_id: str
    bar_id: str
    label: str


class EnrollResponse(BaseModel):
    id: str
    label: str
    token: str          # shown exactly once, never retrievable again


class DeviceOut(BaseModel):
    id: str
    edition_id: str
    bar_id: str
    label: str
    enrolled_at: object
    last_seen_at: object | None
    revoked_at: object | None


@router.post("/enroll", status_code=status.HTTP_201_CREATED)
async def enroll(
    body: EnrollRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings_from_app),
) -> EnrollResponse:
    token = generate_device_token()
    device = Device(
        edition_id=body.edition_id,
        bar_id=body.bar_id,
        label=body.label,
        token_hash=hash_device_token(token, settings.device_token_pepper),
    )
    await db.devices.insert_one(device.to_mongo())
    return EnrollResponse(id=device.id, label=device.label, token=token)


@router.get("")
async def list_devices(db: AsyncIOMotorDatabase = Depends(get_db)) -> list[DeviceOut]:
    out = []
    async for d in db.devices.find({}):
        out.append(DeviceOut(
            id=d["_id"], edition_id=d["edition_id"], bar_id=d["bar_id"],
            label=d["label"], enrolled_at=d["enrolled_at"],
            last_seen_at=d.get("last_seen_at"), revoked_at=d.get("revoked_at"),
        ))
    return out


@router.post("/{device_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke(
    device_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Response:
    result = await db.devices.update_one(
        {"_id": device_id}, {"$set": {"revoked_at": utcnow()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="device not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 5: Mount the router**

In `backend/app/main.py`:

```python
from .routers import admin_catalog, admin_devices, auth
...
    app.include_router(admin_devices.router)
```

Mount `admin_devices` **before** `admin_catalog`, otherwise `/admin/devices` would be
captured by nothing — the catalog router has no such path, but keeping the more
specific prefix first avoids a future collision.

- [ ] **Step 6: Run to verify the enrolment tests pass**

```bash
uv run pytest tests/test_devices.py -v -k "not time and not revoked"
```

Expected: 4 passed. The `/api/v1/time` tests still fail — Task 9 fixes them.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/admin_devices.py backend/app/deps.py \
        backend/app/main.py backend/tests/test_devices.py
git commit -m "feat: device enrolment, listing and revocation"
```

---

### Task 9: Server time and bootstrap

What a tablet fetches to work offline: the clock reference and the entire catalog for its bar.

**Files:**
- Create: `backend/app/routers/sync.py`
- Test: `backend/tests/test_bootstrap.py`
- Modify: `backend/app/main.py` (mount)

**Interfaces:**
- Consumes: `get_current_device`, catalog models.
- Produces:
  - `GET /api/v1/time` → `{"server_time": "<ISO8601 UTC>"}`
  - `GET /api/v1/bootstrap` → `{edition, bar, products, staff, server_time}`, containing only products available at the device's bar.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_bootstrap.py`:

```python
from datetime import UTC, datetime

import pytest

from app.models.catalog import Bar, Edition, Product, Staff


@pytest.fixture
async def festival(db, auth_client):
    edition = Edition(name="Festival 2026", year=2026, coupon_value_eur=2.50,
                      starts_at=datetime(2026, 7, 1, tzinfo=UTC),
                      ends_at=datetime(2026, 7, 3, tzinfo=UTC))
    main_bar = Bar(edition_id=edition.id, name="Hoofdpodium")
    cocktail_bar = Bar(edition_id=edition.id, name="Cocktailbar")

    jupiler = Product(edition_id=edition.id, slug="jupiler", name="Jupiler",
                      category="bier", price_coupons=1,
                      available_at=[main_bar.id, cocktail_bar.id])
    gin = Product(edition_id=edition.id, slug="gin-tonic", name="Gin-Tonic",
                  category="cocktail", price_coupons=4,
                  available_at=[cocktail_bar.id])
    lotte = Staff(edition_id=edition.id, name="Lotte")

    await db.editions.insert_one(edition.to_mongo())
    await db.bars.insert_many([main_bar.to_mongo(), cocktail_bar.to_mongo()])
    await db.products.insert_many([jupiler.to_mongo(), gin.to_mongo()])
    await db.staff.insert_one(lotte.to_mongo())

    r = await auth_client.post("/api/v1/admin/devices/enroll",
                               json={"edition_id": edition.id, "bar_id": main_bar.id,
                                     "label": "Tablet 1"})
    return {"edition": edition, "main_bar": main_bar, "cocktail_bar": cocktail_bar,
            "device": r.json()}


def _auth(festival) -> dict:
    return {"Authorization": f"Bearer {festival['device']['token']}"}


async def test_time_returns_utc(client, festival):
    r = await client.get("/api/v1/time", headers=_auth(festival))
    assert r.status_code == 200
    parsed = datetime.fromisoformat(r.json()["server_time"])
    assert parsed.tzinfo is not None
    assert abs((datetime.now(UTC) - parsed).total_seconds()) < 5


async def test_bootstrap_returns_the_devices_edition_and_bar(client, festival):
    r = await client.get("/api/v1/bootstrap", headers=_auth(festival))
    assert r.status_code == 200
    body = r.json()
    assert body["edition"]["name"] == "Festival 2026"
    assert body["bar"]["name"] == "Hoofdpodium"


async def test_bootstrap_only_returns_products_sold_at_this_bar(client, festival):
    """A main-stage tablet must not show cocktail-only products."""
    body = (await client.get("/api/v1/bootstrap", headers=_auth(festival))).json()
    assert [p["slug"] for p in body["products"]] == ["jupiler"]


async def test_bootstrap_returns_staff_and_server_time(client, festival):
    body = (await client.get("/api/v1/bootstrap", headers=_auth(festival))).json()
    assert [s["name"] for s in body["staff"]] == ["Lotte"]
    assert body["server_time"]


async def test_bootstrap_requires_a_device_token(client, festival):
    assert (await client.get("/api/v1/bootstrap")).status_code == 401
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_bootstrap.py -v
```

Expected: FAIL, 404 on `/api/v1/time`.

- [ ] **Step 3: Implement**

`backend/app/routers/sync.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..deps import get_current_device, get_db
from ..models.common import utcnow
from ..models.identity import Device

router = APIRouter(prefix="/api/v1", tags=["sync"])


def _serialise(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


@router.get("/time")
async def server_time(device: Device = Depends(get_current_device)) -> dict:
    """Clock reference. Tablets stamp orders with device_now + (server - device)."""
    return {"server_time": utcnow().isoformat()}


@router.get("/bootstrap")
async def bootstrap(
    device: Device = Depends(get_current_device),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    edition = await db.editions.find_one({"_id": device.edition_id})
    bar = await db.bars.find_one({"_id": device.bar_id})
    if edition is None or bar is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This device is enrolled against an edition or bar that no longer exists",
        )

    products = [
        _serialise(d)
        async for d in db.products.find(
            {"edition_id": device.edition_id, "active": True,
             "available_at": device.bar_id}
        ).sort("sort_order")
    ]
    staff = [
        _serialise(d)
        async for d in db.staff.find({"edition_id": device.edition_id, "active": True})
    ]

    return {
        "edition": _serialise(edition),
        "bar": _serialise(bar),
        "products": products,
        "staff": staff,
        "server_time": utcnow().isoformat(),
    }
```

- [ ] **Step 4: Mount the router**

In `backend/app/main.py`:

```python
from .routers import admin_catalog, admin_devices, auth, sync
...
    app.include_router(sync.router)
```

- [ ] **Step 5: Run to verify it passes**

```bash
uv run pytest tests/test_bootstrap.py tests/test_devices.py -v
```

Expected: all pass, including the four device tests deferred from Task 8.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/sync.py backend/app/main.py backend/tests/test_bootstrap.py
git commit -m "feat: server time and bootstrap endpoints for tablets"
```

---

### Task 10: Order sync — idempotency and one-way voiding

The heart of the system. Everything about offline correctness lives here.

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/orders.py`
- Test: `backend/tests/test_sync_orders.py`
- Modify: `backend/app/routers/sync.py` (add `POST /sync/orders`)

**Interfaces:**
- Consumes: `OrderIn`, `Order`, `Device`.
- Produces:
  - `services.orders.upsert_order(db, order_in: OrderIn, device: Device) -> str` returning one of `"inserted"`, `"updated"`, `"ignored"`.
  - `POST /api/v1/sync/orders` — body `{"orders": [OrderIn, ...]}`, returns `{"accepted": [id, ...], "results": {id: outcome}}`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_sync_orders.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.catalog import Bar, Edition, Product, Staff


@pytest.fixture
async def setup(db, auth_client):
    edition = Edition(name="Festival 2026", year=2026, coupon_value_eur=2.50,
                      starts_at=datetime(2026, 7, 1, tzinfo=UTC),
                      ends_at=datetime(2026, 7, 3, tzinfo=UTC))
    bar = Bar(edition_id=edition.id, name="Hoofdpodium")
    product = Product(edition_id=edition.id, slug="jupiler", name="Jupiler",
                      category="bier", price_coupons=1, available_at=[bar.id])
    staff = Staff(edition_id=edition.id, name="Lotte")
    await db.editions.insert_one(edition.to_mongo())
    await db.bars.insert_one(bar.to_mongo())
    await db.products.insert_one(product.to_mongo())
    await db.staff.insert_one(staff.to_mongo())

    device = (await auth_client.post(
        "/api/v1/admin/devices/enroll",
        json={"edition_id": edition.id, "bar_id": bar.id, "label": "T1"})).json()

    return {"edition": edition, "bar": bar, "product": product,
            "staff": staff, "device": device}


def _order(setup, **overrides) -> dict:
    base = {
        "id": str(uuid4()),
        "edition_id": setup["edition"].id,
        "bar_id": setup["bar"].id,
        "staff_id": setup["staff"].id,
        "items": [{
            "product_id": setup["product"].id, "slug": "jupiler", "name": "Jupiler",
            "qty": 3, "unit_price_coupons": 1,
        }],
        "created_at": datetime.now(UTC).isoformat(),
        "status": "confirmed",
    }
    return base | overrides


def _auth(setup) -> dict:
    return {"Authorization": f"Bearer {setup['device']['token']}"}


async def _post(client, setup, *orders):
    return await client.post("/api/v1/sync/orders",
                             json={"orders": list(orders)}, headers=_auth(setup))


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
    order = _order(setup, status="voided", void={
        "at": datetime.now(UTC).isoformat(),
        "by": {"type": "staff", "id": setup["staff"].id},
        "reason": None,
    })
    await _post(client, setup, order)

    doc = await db.orders.find_one({"_id": order["id"]})
    assert doc["status"] == "voided"
    assert doc["void"]["by"]["type"] == "staff"


async def test_voiding_an_already_synced_order_works(client, setup, db):
    order = _order(setup)
    await _post(client, setup, order)

    voided = order | {"status": "voided", "void": {
        "at": datetime.now(UTC).isoformat(),
        "by": {"type": "staff", "id": setup["staff"].id},
        "reason": None,
    }}
    await _post(client, setup, voided)

    assert (await db.orders.find_one({"_id": order["id"]}))["status"] == "voided"


async def test_a_voided_order_can_never_be_resurrected(client, setup, db):
    """A stale tablet replaying an old queue must not undo a void."""
    order = _order(setup)
    await _post(client, setup, order)
    await _post(client, setup, order | {"status": "voided", "void": {
        "at": datetime.now(UTC).isoformat(),
        "by": {"type": "staff", "id": setup["staff"].id}, "reason": None}})

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
    bad = _order(setup, items=[])          # no items: rejected by the service
    r = await _post(client, setup, good, bad)

    assert good["id"] in r.json()["accepted"]
    assert r.json()["results"][bad["id"]] == "rejected"
    assert await db.orders.count_documents({}) == 1


async def test_sync_requires_a_device_token(client, setup):
    r = await client.post("/api/v1/sync/orders", json={"orders": [_order(setup)]})
    assert r.status_code == 401
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_sync_orders.py -v
```

Expected: FAIL, 404 on `/api/v1/sync/orders`.

- [ ] **Step 3: Implement the service**

```bash
touch backend/app/services/__init__.py
```

`backend/app/services/orders.py`:

```python
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from ..models.common import utcnow
from ..models.identity import Device
from ..models.order import OrderIn

Outcome = str  # "inserted" | "updated" | "ignored" | "rejected"


async def upsert_order(
    db: AsyncIOMotorDatabase, order_in: OrderIn, device: Device
) -> Outcome:
    """Idempotent write of one order.

    The tablet owns the `_id`, so a retry is a no-op rather than a duplicate sale.
    Status is a one-way ratchet: once voided, an order stays voided even if a stale
    tablet later replays the original confirmed copy.
    """
    if not order_in.items:
        return "rejected"
    if order_in.status == "voided" and order_in.void is None:
        return "rejected"

    total = sum(i.qty * i.unit_price_coupons for i in order_in.items)

    payload = {
        "edition_id": order_in.edition_id,
        "bar_id": order_in.bar_id,
        "staff_id": order_in.staff_id,
        "device_id": device.id,        # from the token, never from the payload
        "items": [i.model_dump() for i in order_in.items],
        "total_coupons": total,        # recomputed, never trusted
        "created_at": order_in.created_at,
        "status": order_in.status,
        "void": order_in.void.model_dump() if order_in.void else None,
    }

    try:
        result = await db.orders.update_one(
            {"_id": order_in.id, "status": {"$ne": "voided"}},
            {"$set": payload, "$setOnInsert": {"received_at": utcnow()}},
            upsert=True,
        )
    except DuplicateKeyError:
        # The filter excluded an existing voided document, so the upsert tried to
        # insert a duplicate _id. That means: already voided. Leave it alone.
        return "ignored"

    return "inserted" if result.upserted_id is not None else "updated"
```

- [ ] **Step 4: Add the endpoint**

Append to `backend/app/routers/sync.py`:

```python
from pydantic import BaseModel

from ..models.order import OrderIn
from ..services.orders import upsert_order


class OrderBatch(BaseModel):
    orders: list[OrderIn]


@router.post("/sync/orders")
async def sync_orders(
    body: OrderBatch,
    device: Device = Depends(get_current_device),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Drain a tablet's queue. One bad order never blocks the rest."""
    results: dict[str, str] = {}
    for order in body.orders:
        results[order.id] = await upsert_order(db, order, device)

    accepted = [oid for oid, outcome in results.items()
                if outcome in ("inserted", "updated")]
    return {"accepted": accepted, "results": results}
```

- [ ] **Step 5: Run to verify it passes**

```bash
uv run pytest tests/test_sync_orders.py -v
```

Expected: 11 passed.

- [ ] **Step 6: Run the whole suite**

```bash
uv run pytest -v
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services backend/app/routers/sync.py backend/tests/test_sync_orders.py
git commit -m "feat: idempotent order sync with one-way voiding"
```

---

### Task 11: Stockout sync and organiser voids

**Files:**
- Test: `backend/tests/test_stockouts.py`
- Modify: `backend/app/routers/sync.py` (add `POST /sync/stockouts`)
- Create: `backend/app/routers/admin_orders.py`
- Modify: `backend/app/main.py` (mount)

**Interfaces:**
- Consumes: `StockoutIn`, `Stockout`, `get_current_device`, `get_current_user`.
- Produces:
  - `POST /api/v1/sync/stockouts` — body `{"stockouts": [StockoutIn, ...]}` → `{"accepted": [id, ...]}`
  - `POST /api/v1/admin/orders/{id}/void` — body `{"reason": str}` → 200 with the voided order.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_stockouts.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.catalog import Bar, Edition, Product, Staff


@pytest.fixture
async def setup(db, auth_client):
    edition = Edition(name="F26", year=2026, coupon_value_eur=2.5,
                      starts_at=datetime(2026, 7, 1, tzinfo=UTC),
                      ends_at=datetime(2026, 7, 3, tzinfo=UTC))
    bar = Bar(edition_id=edition.id, name="Hoofdpodium")
    product = Product(edition_id=edition.id, slug="jupiler", name="Jupiler",
                      category="bier", price_coupons=1, available_at=[bar.id])
    staff = Staff(edition_id=edition.id, name="Lotte")
    await db.editions.insert_one(edition.to_mongo())
    await db.bars.insert_one(bar.to_mongo())
    await db.products.insert_one(product.to_mongo())
    await db.staff.insert_one(staff.to_mongo())
    device = (await auth_client.post(
        "/api/v1/admin/devices/enroll",
        json={"edition_id": edition.id, "bar_id": bar.id, "label": "T1"})).json()
    return {"edition": edition, "bar": bar, "product": product,
            "staff": staff, "device": device}


def _auth(setup):
    return {"Authorization": f"Bearer {setup['device']['token']}"}


async def test_a_stockout_is_recorded_with_the_product_slug(client, setup, db):
    sid = str(uuid4())
    r = await client.post("/api/v1/sync/stockouts", headers=_auth(setup), json={
        "stockouts": [{"id": sid, "product_id": setup["product"].id,
                       "out_at": datetime.now(UTC).isoformat()}]})

    assert r.status_code == 200
    doc = await db.stockouts.find_one({"_id": sid})
    assert doc["slug"] == "jupiler"           # denormalised for year-over-year joins
    assert doc["bar_id"] == setup["bar"].id
    assert doc["back_at"] is None


async def test_marking_a_product_back_in_stock_updates_the_same_record(client, setup, db):
    sid = str(uuid4())
    out_at = datetime.now(UTC).isoformat()
    await client.post("/api/v1/sync/stockouts", headers=_auth(setup), json={
        "stockouts": [{"id": sid, "product_id": setup["product"].id, "out_at": out_at}]})

    back = datetime.now(UTC).isoformat()
    await client.post("/api/v1/sync/stockouts", headers=_auth(setup), json={
        "stockouts": [{"id": sid, "product_id": setup["product"].id,
                       "out_at": out_at, "back_at": back}]})

    assert await db.stockouts.count_documents({}) == 1
    assert (await db.stockouts.find_one({"_id": sid}))["back_at"] is not None


async def test_a_stockout_for_an_unknown_product_is_rejected(client, setup):
    r = await client.post("/api/v1/sync/stockouts", headers=_auth(setup), json={
        "stockouts": [{"id": str(uuid4()), "product_id": "nope",
                       "out_at": datetime.now(UTC).isoformat()}]})
    assert r.json()["accepted"] == []


async def test_stockout_sync_requires_a_device_token(client, setup):
    r = await client.post("/api/v1/sync/stockouts", json={"stockouts": []})
    assert r.status_code == 401


async def test_an_organiser_can_void_an_order_with_a_reason(client, auth_client, setup, db):
    oid = str(uuid4())
    await client.post("/api/v1/sync/orders", headers=_auth(setup), json={"orders": [{
        "id": oid, "edition_id": setup["edition"].id, "bar_id": setup["bar"].id,
        "staff_id": setup["staff"].id,
        "items": [{"product_id": setup["product"].id, "slug": "jupiler",
                   "name": "Jupiler", "qty": 1, "unit_price_coupons": 1}],
        "created_at": datetime.now(UTC).isoformat(), "status": "confirmed"}]})

    r = await auth_client.post(f"/api/v1/admin/orders/{oid}/void",
                               json={"reason": "duplicate entry"})

    assert r.status_code == 200
    doc = await db.orders.find_one({"_id": oid})
    assert doc["status"] == "voided"
    assert doc["void"]["by"]["type"] == "user"
    assert doc["void"]["reason"] == "duplicate entry"


async def test_an_organiser_void_requires_a_reason(auth_client, setup):
    r = await auth_client.post("/api/v1/admin/orders/whatever/void", json={})
    assert r.status_code == 422


async def test_voiding_an_unknown_order_is_404(auth_client):
    r = await auth_client.post("/api/v1/admin/orders/nope/void",
                               json={"reason": "x"})
    assert r.status_code == 404
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_stockouts.py -v
```

Expected: FAIL, 404s.

- [ ] **Step 3: Add the stockout endpoint**

Append to `backend/app/routers/sync.py`:

```python
from ..models.order import StockoutIn


class StockoutBatch(BaseModel):
    stockouts: list[StockoutIn]


@router.post("/sync/stockouts")
async def sync_stockouts(
    body: StockoutBatch,
    device: Device = Depends(get_current_device),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    accepted: list[str] = []
    for item in body.stockouts:
        product = await db.products.find_one({"_id": item.product_id})
        if product is None:
            continue
        await db.stockouts.update_one(
            {"_id": item.id},
            {"$set": {
                "edition_id": device.edition_id,
                "bar_id": device.bar_id,
                "product_id": item.product_id,
                "slug": product["slug"],
                "out_at": item.out_at,
                "back_at": item.back_at,
            }},
            upsert=True,
        )
        accepted.append(item.id)
    return {"accepted": accepted}
```

- [ ] **Step 4: Add the organiser void endpoint**

`backend/app/routers/admin_orders.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from ..deps import get_current_user, get_db
from ..models.common import utcnow
from ..models.identity import User

router = APIRouter(
    prefix="/api/v1/admin/orders",
    tags=["admin-orders"],
    dependencies=[Depends(get_current_user)],
)


class VoidRequest(BaseModel):
    reason: str = Field(min_length=1)   # organiser voids must be explained


@router.post("/{order_id}/void")
async def void_order(
    order_id: str,
    body: VoidRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    doc = await db.orders.find_one_and_update(
        {"_id": order_id},
        {"$set": {
            "status": "voided",
            "void": {
                "at": utcnow(),
                "by": {"type": "user", "id": user.id},
                "reason": body.reason,
            },
        }},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="order not found")
    doc["id"] = doc.pop("_id")
    return doc
```

- [ ] **Step 5: Mount the router**

In `backend/app/main.py`:

```python
from .routers import admin_catalog, admin_devices, admin_orders, auth, sync
...
    app.include_router(admin_orders.router)
```

- [ ] **Step 6: Run to verify it passes**

```bash
uv run pytest tests/test_stockouts.py -v
```

Expected: 7 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/sync.py backend/app/routers/admin_orders.py \
        backend/app/main.py backend/tests/test_stockouts.py
git commit -m "feat: stockout sync and organiser order voiding"
```

---

### Task 12: Rate limiting, security headers, and a seed command

**Files:**
- Create: `backend/app/middleware.py`
- Create: `backend/app/cli.py`
- Test: `backend/tests/test_hardening.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `Settings`, `hash_password`, `User`.
- Produces:
  - `middleware.add_security_headers(app) -> None`
  - `middleware.limiter` — a `slowapi.Limiter` keyed by client IP.
  - `cli.create_organiser(email, password) -> None`, runnable as `uv run python -m app.cli create-organiser <email>`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_hardening.py`:

```python
async def test_security_headers_are_present(client):
    r = await client.get("/api/v1/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"


async def test_repeated_failed_logins_are_rate_limited(client, make_user):
    await make_user("org@example.com", "hunter2hunter2")
    codes = []
    for _ in range(12):
        r = await client.post("/api/v1/auth/login",
                              json={"email": "org@example.com", "password": "wrong"})
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
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_hardening.py -v
```

Expected: FAIL on the headers and the 429.

- [ ] **Step 3: Implement the middleware**

`backend/app/middleware.py`:

```python
from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


def add_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def _headers(request: Request, call_next):
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        return response
```

- [ ] **Step 4: Wire it into the app**

In `backend/app/main.py`, add the imports:

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .middleware import add_security_headers, limiter
```

and inside `create_app`, after the CORS middleware:

```python
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    add_security_headers(app)
```

- [ ] **Step 5: Rate-limit the login route**

In `backend/app/routers/auth.py`, add the import:

```python
from fastapi import Request

from ..middleware import limiter
```

then decorate `login` and add `request: Request` as its first parameter:

```python
@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    ...
```

> `slowapi` requires the parameter to be named exactly `request`.

- [ ] **Step 6: Run to verify it passes**

```bash
uv run pytest tests/test_hardening.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Add the organiser-creation command**

There is no signup endpoint by design — organiser accounts are made from the shell.

`backend/app/cli.py`:

```python
import asyncio
import getpass
import sys

from .config import get_settings
from .db import ensure_indexes, get_client
from .models.identity import User
from .security import hash_password


async def create_organiser(email: str, password: str) -> None:
    settings = get_settings()
    client = get_client(settings.mongo_uri)
    db = client[settings.mongo_db]
    await ensure_indexes(db)

    if await db.users.find_one({"email": email}):
        print(f"User {email} already exists.")
        return

    user = User(email=email, password_hash=hash_password(password))
    await db.users.insert_one(user.to_mongo())
    print(f"Created organiser {email} ({user.id})")
    client.close()


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] != "create-organiser":
        print("usage: python -m app.cli create-organiser <email>")
        raise SystemExit(1)

    password = getpass.getpass("Password: ")
    if len(password) < 12:
        print("Password must be at least 12 characters.")
        raise SystemExit(1)
    if password != getpass.getpass("Repeat: "):
        print("Passwords do not match.")
        raise SystemExit(1)

    asyncio.run(create_organiser(sys.argv[2], password))


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Run the whole suite**

```bash
uv run pytest -v
```

Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add backend/app/middleware.py backend/app/cli.py backend/app/main.py \
        backend/app/routers/auth.py backend/tests/test_hardening.py
git commit -m "feat: rate limiting, security headers, and organiser CLI"
```

---

### Task 13: Deploy to Render and Atlas

**Files:**
- Create: `render.yaml`
- Create: `docs/DEPLOYMENT.md`
- Create: `README.md`

**Interfaces:**
- Consumes: everything.
- Produces: a live HTTPS API. No code depends on this task.

- [ ] **Step 1: Create the Atlas cluster**

Do this by hand at https://cloud.mongodb.com:

1. Create a free **M0** cluster in an EU region (`eu-west-1` / Ireland is closest).
2. Database Access → add user `festival_app`, **Autogenerate Secure Password**, save it,
   privilege **Read and write to any database** scoped to database `festival`.
3. Network Access → add `0.0.0.0/0`. Render's free tier has no fixed egress IP, so this
   is unavoidable; the scoped user above is the compensating control.
4. Copy the connection string.

- [ ] **Step 2: Write the Render blueprint**

`render.yaml` — note that every secret is `sync: false`, meaning Render prompts for it
and it is never stored in the repository.

```yaml
services:
  - type: web
    name: festival-api
    runtime: python
    region: frankfurt
    plan: free
    rootDir: backend
    buildCommand: pip install uv && uv sync --frozen
    startCommand: uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port $PORT
    healthCheckPath: /api/v1/health
    envVars:
      - key: MONGO_DB
        value: festival
      - key: COOKIE_SECURE
        value: "true"
      - key: MONGO_URI
        sync: false
      - key: JWT_SECRET
        sync: false
      - key: DEVICE_TOKEN_PEPPER
        sync: false
      - key: CORS_ORIGINS
        sync: false
```

- [ ] **Step 3: Generate the secrets**

```bash
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))"
python3 -c "import secrets; print('DEVICE_TOKEN_PEPPER=' + secrets.token_urlsafe(48))"
```

Paste these into Render's dashboard only. **Never into a file in this repository.**

- [ ] **Step 4: Deploy**

Connect the repo at https://dashboard.render.com → New → Blueprint. Set `CORS_ORIGINS`
to `["https://pos-festival.pages.dev","https://admin-festival.pages.dev"]` for now;
Plan 3 revises it once the real frontend URLs exist.

- [ ] **Step 5: Verify the deployment**

```bash
curl -sS https://festival-api.onrender.com/api/v1/health
```

Expected: `{"status":"ok"}`. The first call after 15 minutes idle takes ~1 minute — that
is the documented free-tier behaviour, not a fault.

- [ ] **Step 6: Create your organiser account**

In the Render dashboard, open a Shell on the service:

```bash
uv run python -m app.cli create-organiser you@example.com
```

- [ ] **Step 7: Verify login works against the live API**

```bash
curl -sS -X POST https://festival-api.onrender.com/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"<the password you set>"}' -i | head -20
```

Expected: `200` and a `set-cookie: session=...; HttpOnly; Secure; SameSite=strict`.

- [ ] **Step 8: Write the docs**

`README.md`:

````markdown
# FestivalApp

Drink-sales registration and analysis for a festival. Bar staff record orders on a
tablet in as few taps as possible; organisers get live figures during the event and
purchasing advice afterwards.

- **Design:** `docs/superpowers/specs/2026-09-12-festival-sales-app-design.md`
- **Deployment:** `docs/DEPLOYMENT.md`

## Backend development

```bash
cd backend
uv sync
cp .env.example .env      # then fill in real values — .env is gitignored
uv run pytest             # downloads a local MongoDB on first run
uv run uvicorn app.main:create_app --factory --reload
```

API docs at http://127.0.0.1:8000/docs

## Security

Never commit `.env` or any real secret. `gitleaks` runs as a pre-commit hook and in CI,
and GitHub push protection is enabled on this repository.
````

`docs/DEPLOYMENT.md`: record the Atlas cluster name, the Render service name, which
environment variables exist (names only, never values), and how to rotate a secret.

- [ ] **Step 9: Commit**

```bash
git add render.yaml README.md docs/DEPLOYMENT.md
git commit -m "chore: deployment blueprint and documentation"
git push
```

- [ ] **Step 10: Confirm CI is green and no secret was committed**

```bash
gh run watch
git log -p | grep -iE "mongodb\+srv://[^<]|JWT_SECRET=[A-Za-z0-9_-]{20,}" || echo "clean"
```

Expected: CI green, and `clean`.

---

## Definition of done

- [ ] `uv run pytest` passes locally with a real MongoDB.
- [ ] CI is green on `main`, including the gitleaks job.
- [ ] `https://<service>.onrender.com/api/v1/health` returns `{"status":"ok"}`.
- [ ] An organiser can log in and receives an `HttpOnly; Secure; SameSite=strict` cookie.
- [ ] A device can be enrolled, can call `/bootstrap`, and stops working once revoked.
- [ ] Submitting the same order three times produces exactly one document.
- [ ] A voided order cannot be resurrected by a replayed confirmed copy.
- [ ] `git log -p` contains no secret.

## What this plan deliberately does not build

Handled by later plans, and listed here so their absence is not mistaken for an omission:

- **Plan 2 — POS app:** the tablet PWA, offline IndexedDB queue, sync worker.
- **Plan 3 — Admin shell:** login UI, catalog configuration screens, live dashboard.
- **Plan 4 — Reports:** aggregations for profit, margin–volume quadrant, Pareto, hourly
  demand, per-bar mix, year-over-year, the procurement engine, and CSV export.

No statistics endpoint is built here. The order documents this plan produces contain
everything those aggregations need.
