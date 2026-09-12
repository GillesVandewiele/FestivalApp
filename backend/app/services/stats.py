"""Statistics. Everything is computed on demand: there are no stored counters, so
nothing can drift out of step with the orders.

Every pipeline starts from CONFIRMED, because a voided sale must never contribute
to a number that informs a purchasing decision.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

CONFIRMED = {"status": "confirmed"}


def _match(edition_id: str) -> dict:
    return {"$match": {"edition_id": edition_id, **CONFIRMED}}


async def _coupon_value(db: AsyncIOMotorDatabase, edition_id: str) -> float:
    edition = await db.editions.find_one({"_id": edition_id})
    return float(edition["coupon_value_eur"]) if edition else 0.0


def _round2(value: float) -> float:
    return round(value + 0.0, 2)


async def overview(db: AsyncIOMotorDatabase, edition_id: str) -> dict:
    value = await _coupon_value(db, edition_id)
    pipeline = [
        _match(edition_id),
        {
            "$group": {
                "_id": None,
                "orders": {"$sum": 1},
                "coupons": {"$sum": "$total_coupons"},
                "drinks": {"$sum": {"$sum": "$items.qty"}},
            }
        },
    ]
    rows = await db.orders.aggregate(pipeline).to_list(1)
    row = rows[0] if rows else {"orders": 0, "coupons": 0, "drinks": 0}
    voided = await db.orders.count_documents({"edition_id": edition_id, "status": "voided"})

    return {
        "orders": row["orders"],
        "drinks": row["drinks"],
        "coupons": row["coupons"],
        "revenue_eur": _round2(row["coupons"] * value),
        "voided_orders": voided,
    }


async def by_product(db: AsyncIOMotorDatabase, edition_id: str) -> list[dict]:
    value = await _coupon_value(db, edition_id)
    pipeline = [
        _match(edition_id),
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": "$items.slug",
                "name": {"$first": "$items.name"},
                "qty": {"$sum": "$items.qty"},
                "coupons": {"$sum": {"$multiply": ["$items.qty", "$items.unit_price_coupons"]}},
            }
        },
        {"$sort": {"qty": -1, "_id": 1}},
    ]
    rows = await db.orders.aggregate(pipeline).to_list(None)

    catalog = {p["slug"]: p async for p in db.products.find({"edition_id": edition_id})}

    out = []
    for row in rows:
        product = catalog.get(row["_id"], {})
        cost_price = product.get("cost_price_eur")
        revenue = _round2(row["coupons"] * value)
        # A missing cost must not read as 100% margin. That is a lie a purchasing
        # decision could rest on, so the whole margin is reported as unknown.
        cost = _round2(row["qty"] * cost_price) if cost_price is not None else None
        margin = _round2(revenue - cost) if cost is not None else None
        out.append(
            {
                "slug": row["_id"],
                "name": row["name"],
                "category": product.get("category", ""),
                "qty": row["qty"],
                "coupons": row["coupons"],
                "revenue_eur": revenue,
                "cost_eur": cost,
                "margin_eur": margin,
                "margin_pct": (
                    _round2(margin / revenue * 100) if margin is not None and revenue else None
                ),
                "cost_known": cost is not None,
            }
        )
    return out


async def by_bar(db: AsyncIOMotorDatabase, edition_id: str) -> list[dict]:
    value = await _coupon_value(db, edition_id)
    pipeline = [
        _match(edition_id),
        {
            "$group": {
                "_id": "$bar_id",
                "qty": {"$sum": {"$sum": "$items.qty"}},
                "coupons": {"$sum": "$total_coupons"},
            }
        },
        {"$sort": {"coupons": -1}},
    ]
    rows = await db.orders.aggregate(pipeline).to_list(None)
    names = {b["_id"]: b["name"] async for b in db.bars.find({"edition_id": edition_id})}

    return [
        {
            "bar_id": r["_id"],
            "name": names.get(r["_id"], "?"),
            "qty": r["qty"],
            "coupons": r["coupons"],
            "revenue_eur": _round2(r["coupons"] * value),
        }
        for r in rows
    ]


async def by_staff(db: AsyncIOMotorDatabase, edition_id: str) -> list[dict]:
    pipeline = [
        {"$match": {"edition_id": edition_id}},
        {
            "$group": {
                "_id": "$staff_id",
                "orders": {"$sum": {"$cond": [{"$eq": ["$status", "confirmed"]}, 1, 0]}},
                "voided": {"$sum": {"$cond": [{"$eq": ["$status", "voided"]}, 1, 0]}},
                "qty": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", "confirmed"]}, {"$sum": "$items.qty"}, 0]
                    }
                },
                "coupons": {
                    "$sum": {"$cond": [{"$eq": ["$status", "confirmed"]}, "$total_coupons", 0]}
                },
            }
        },
        {"$sort": {"coupons": -1}},
    ]
    rows = await db.orders.aggregate(pipeline).to_list(None)
    names = {s["_id"]: s["name"] async for s in db.staff.find({"edition_id": edition_id})}

    return [
        {
            "staff_id": r["_id"],
            "name": names.get(r["_id"], "?"),
            "orders": r["orders"],
            "qty": r["qty"],
            "coupons": r["coupons"],
            "voided": r["voided"],
        }
        for r in rows
    ]


async def by_hour(db: AsyncIOMotorDatabase, edition_id: str, tz: str) -> list[dict]:
    """Bucketed in the edition's local timezone. In UTC a Belgian evening lands two
    hours early and the peak-hour figure becomes useless."""
    pipeline = [
        _match(edition_id),
        {
            "$group": {
                "_id": {"$hour": {"date": "$created_at", "timezone": tz}},
                "qty": {"$sum": {"$sum": "$items.qty"}},
                "coupons": {"$sum": "$total_coupons"},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    rows = await db.orders.aggregate(pipeline).to_list(None)
    hours = [{"hour_local": r["_id"], "qty": r["qty"], "coupons": r["coupons"]} for r in rows]
    return _chronological(hours)


def _chronological(hours: list[dict]) -> list[dict]:
    """Order the hours as the night was actually lived, not 0..23.

    A festival that runs past midnight has hours like 18..23 plus 0..3. Sorting
    numerically puts the after-midnight hours first, so the chart claims the
    evening began at midnight. Rotating at the largest gap in the clock puts them
    in the order people experienced them, and works for any start time without
    needing to know one.
    """
    if len(hours) < 2:
        return hours

    present = [h["hour_local"] for h in hours]
    gaps = [((present[(i + 1) % len(present)] - present[i]) % 24, i) for i in range(len(present))]
    largest_gap, at = max(gaps)
    if largest_gap <= 1:  # a contiguous run, already in order
        return hours

    start = (at + 1) % len(hours)
    return hours[start:] + hours[:start]


async def peak_per_bar(db: AsyncIOMotorDatabase, edition_id: str, tz: str) -> list[dict]:
    """Busiest local hour per bar. This sizes stock and cooling per verkooppunt far
    better than the daily total does."""
    pipeline = [
        _match(edition_id),
        {
            "$group": {
                "_id": {
                    "bar": "$bar_id",
                    "hour": {"$hour": {"date": "$created_at", "timezone": tz}},
                },
                "qty": {"$sum": {"$sum": "$items.qty"}},
            }
        },
        {"$sort": {"qty": -1}},
        {
            "$group": {
                "_id": "$_id.bar",
                "peak_hour": {"$first": "$_id.hour"},
                "peak_qty": {"$first": "$qty"},
            }
        },
    ]
    rows = await db.orders.aggregate(pipeline).to_list(None)
    names = {b["_id"]: b["name"] async for b in db.bars.find({"edition_id": edition_id})}

    return [
        {
            "bar_id": r["_id"],
            "name": names.get(r["_id"], "?"),
            "peak_hour": r["peak_hour"],
            "peak_qty": r["peak_qty"],
        }
        for r in rows
    ]


async def _qty_by_slug(db: AsyncIOMotorDatabase, edition_id: str) -> dict[str, dict]:
    pipeline = [
        _match(edition_id),
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": "$items.slug",
                "name": {"$first": "$items.name"},
                "qty": {"$sum": "$items.qty"},
            }
        },
    ]
    rows = await db.orders.aggregate(pipeline).to_list(None)
    return {r["_id"]: r for r in rows}


async def compare(db: AsyncIOMotorDatabase, edition_a: str, edition_b: str) -> list[dict]:
    """Year-over-year, matched on slug. Products are edition-scoped documents, so slug
    is the only stable identity across editions."""
    a = await _qty_by_slug(db, edition_a)
    b = await _qty_by_slug(db, edition_b)

    out = []
    for slug in sorted(set(a) | set(b)):
        qty_a = a.get(slug, {}).get("qty", 0)
        qty_b = b.get(slug, {}).get("qty", 0)
        out.append(
            {
                "slug": slug,
                "name": b.get(slug, a.get(slug, {})).get("name", slug),
                "qty_a": qty_a,
                "qty_b": qty_b,
                "delta": qty_b - qty_a,
                # Growth from zero is undefined, not infinite. Reporting a number here
                # would put a fabricated percentage into a buying decision.
                "pct": _round2((qty_b - qty_a) / qty_a * 100) if qty_a else None,
            }
        )
    return out
