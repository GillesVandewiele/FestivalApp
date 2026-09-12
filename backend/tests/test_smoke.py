async def test_mongodb_is_reachable(db):
    await db.ping_check.insert_one({"_id": "x", "ok": True})
    doc = await db.ping_check.find_one({"_id": "x"})
    assert doc["ok"] is True
