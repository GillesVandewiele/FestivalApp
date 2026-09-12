import pytest
from pymongo.errors import DuplicateKeyError

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
    await ensure_indexes(db)
