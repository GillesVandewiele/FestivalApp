"""Statistics. Everything is computed on demand: there are no stored counters, so
nothing can drift out of step with the orders.

Every pipeline starts from CONFIRMED, because a voided sale must never contribute
to a number that informs a purchasing decision.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

# A sale that was not voided. Staff drinks are recorded but never charged, so
# counting them here would report free drinks as revenue.
SOLD = {"status": "confirmed", "kind": {"$ne": "staff"}}


def _match(edition_id: str) -> dict:
    return {"$match": {"edition_id": edition_id, **SOLD}}


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
    voided = await db.orders.count_documents(
        {"edition_id": edition_id, "status": "voided", "kind": {"$ne": "staff"}}
    )

    # Margin reuses by_product so the "unknown cost" rule lives in exactly one
    # place. Summing only the priced products keeps the figure honest, and
    # cost_missing says how much of the assortment it leaves out.
    products = await by_product(db, edition_id)
    priced = [p for p in products if p["cost_known"]]
    margin = _round2(sum(p["margin_eur"] for p in priced)) if priced else None

    return {
        "orders": row["orders"],
        "drinks": row["drinks"],
        "coupons": row["coupons"],
        "revenue_eur": _round2(row["coupons"] * value),
        "cost_eur": _round2(sum(p["cost_eur"] for p in priced)) if priced else None,
        "margin_eur": margin,
        "cost_missing": len(products) - len(priced),
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
        {"$match": {"edition_id": edition_id, "kind": {"$ne": "staff"}}},
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
                "items": {"$push": "$items"},
            }
        },
        {"$sort": {"_id": 1}},
        {
            "$project": {
                "qty": 1,
                "coupons": 1,
                "items": {
                    "$reduce": {
                        "input": "$items",
                        "initialValue": [],
                        "in": {"$concatArrays": ["$$value", "$$this"]},
                    }
                },
            }
        },
    ]
    rows = await db.orders.aggregate(pipeline).to_list(None)
    value = await _coupon_value(db, edition_id)
    costs = {
        p["slug"]: p.get("cost_price_eur")
        async for p in db.products.find({"edition_id": edition_id})
    }

    hours = []
    for r in rows:
        # Margin is only meaningful for the drinks whose cost is known. An hour where
        # nothing is priced reports null rather than drawing a zero line.
        priced = [i for i in r["items"] if costs.get(i["slug"]) is not None]
        cost = sum(i["qty"] * costs[i["slug"]] for i in priced) if priced else None
        revenue = _round2(r["coupons"] * value)
        hours.append(
            {
                "hour_local": r["_id"],
                "qty": r["qty"],
                "coupons": r["coupons"],
                "revenue_eur": revenue,
                "margin_eur": _round2(revenue - cost) if cost is not None else None,
            }
        )
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


async def by_hour_split(
    db: AsyncIOMotorDatabase,
    edition_id: str,
    tz: str,
    metric: str = "qty",
    group_by: str = "product",
    top: int = 7,
) -> dict:
    """Per-hour figures split by drink or by category, for the stacked chart.

    `metric` is "qty", "revenue_eur" or "margin_eur".
    `group_by` is "product" for one series per drink, or "category" for the coarser
    view. Categories are few, so that one rarely needs an "Overig" bucket.

    Quantity and revenue are always computable: the coupon price is snapshotted onto
    every order line. Margin is not, because a drink whose cost price has not been
    entered has no margin to stack. Those drinks are left out and named in `excluded`,
    rather than being drawn as a zero-height segment that reads as "sold nothing".

    The validated palette has eight categorical slots on the adjacent pairlist that
    stacked bars use, so the busiest `top` drinks are named and the rest fold into one
    "Overig" series. A ninth generated hue is never an option.
    """
    value = await _coupon_value(db, edition_id)
    catalogue = {p["slug"]: p async for p in db.products.find({"edition_id": edition_id})}

    ranked = await by_product(db, edition_id)
    excluded: list[str] = []
    if metric == "margin_eur":
        excluded = [r["name"] for r in ranked if not r["cost_known"]]
        ranked = [r for r in ranked if r["cost_known"]]
    eligible = {r["slug"] for r in ranked}

    if group_by == "category":
        categories = {
            c["slug"]: c["name"] async for c in db.categories.find({"edition_id": edition_id})
        }

        def label_of(slug: str) -> str:
            # A configured category shows its name. One that has been deleted shows
            # its raw slug, which tells the organiser which category went missing;
            # "Overige" would hide that. A product with no category at all has
            # nothing to show but the bucket.
            cat = catalogue.get(slug, {}).get("category", "")
            return categories.get(cat, cat or "Overige")

        totals: dict[str, float] = {}
        for r in ranked:
            totals[label_of(r["slug"])] = totals.get(label_of(r["slug"]), 0) + (r.get(metric) or 0)
        ordered_labels = sorted(totals, key=lambda k: -totals[k])[:top]
        named = {
            r["slug"]: label_of(r["slug"]) for r in ranked if label_of(r["slug"]) in ordered_labels
        }
    else:
        ranked = sorted(ranked, key=lambda r: -(r.get(metric) or 0))
        named = {r["slug"]: r["name"] for r in ranked[:top]}

    pipeline = [
        _match(edition_id),
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": {
                    "hour": {"$hour": {"date": "$created_at", "timezone": tz}},
                    "slug": "$items.slug",
                },
                "qty": {"$sum": "$items.qty"},
                "coupons": {"$sum": {"$multiply": ["$items.qty", "$items.unit_price_coupons"]}},
            }
        },
    ]
    rows = await db.orders.aggregate(pipeline).to_list(None)

    def amount(row: dict) -> float:
        if metric == "qty":
            return row["qty"]
        revenue = row["coupons"] * value
        if metric == "revenue_eur":
            return revenue
        cost_price = catalogue.get(row["_id"]["slug"], {}).get("cost_price_eur") or 0
        return revenue - row["qty"] * cost_price

    hours = sorted({r["_id"]["hour"] for r in rows})
    labels = list(dict.fromkeys(named.values()))  # de-duplicated, order preserved
    has_other = (
        len({*named.values()}) < len({*(named.values())})
        or len({s for s in eligible if s not in named}) > 0
    )
    if has_other:
        labels.append("Overig")
    series: dict[str, dict[int, float]] = {label: dict.fromkeys(hours, 0.0) for label in labels}

    for r in rows:
        slug = r["_id"]["slug"]
        if slug not in eligible:
            continue  # unpriced drink in margin mode
        label = named.get(slug, "Overig")
        if label in series:
            series[label][r["_id"]["hour"]] += amount(r)

    ordered = [h["hour_local"] for h in _chronological([{"hour_local": h} for h in hours])]
    return {
        "hours": ordered,
        "metric": metric,
        "group_by": group_by,
        "excluded": excluded,
        "series": [
            {"name": name, "data": [_round2(by_h[h]) for h in ordered]}
            for name, by_h in series.items()
        ],
    }


async def staff_consumption(db: AsyncIOMotorDatabase, edition_id: str) -> dict:
    """What staff drank. Recorded but never charged, so it lives outside every
    revenue figure and is reported on its own terms."""
    value = await _coupon_value(db, edition_id)
    match = {"$match": {"edition_id": edition_id, "status": "confirmed", "kind": "staff"}}

    per_product = await db.orders.aggregate(
        [
            match,
            {"$unwind": "$items"},
            {
                "$group": {
                    "_id": "$items.slug",
                    "name": {"$first": "$items.name"},
                    "qty": {"$sum": "$items.qty"},
                    "coupons": {"$sum": {"$multiply": ["$items.qty", "$items.unit_price_coupons"]}},
                }
            },
            {"$sort": {"qty": -1}},
        ]
    ).to_list(None)

    per_staff = await db.orders.aggregate(
        [
            match,
            {
                "$group": {
                    "_id": "$staff_id",
                    "drinks": {"$sum": {"$sum": "$items.qty"}},
                    "coupons": {"$sum": "$total_coupons"},
                }
            },
            {"$sort": {"drinks": -1}},
        ]
    ).to_list(None)

    per_bar = await db.orders.aggregate(
        [
            match,
            {
                "$group": {
                    "_id": "$bar_id",
                    "drinks": {"$sum": {"$sum": "$items.qty"}},
                    "coupons": {"$sum": "$total_coupons"},
                }
            },
            {"$sort": {"drinks": -1}},
        ]
    ).to_list(None)

    names = {s["_id"]: s["name"] async for s in db.staff.find({"edition_id": edition_id})}
    bars = {b["_id"]: b["name"] async for b in db.bars.find({"edition_id": edition_id})}
    total_coupons = sum(r["coupons"] for r in per_product)

    return {
        "drinks": sum(r["qty"] for r in per_product),
        "coupons": total_coupons,
        # What those drinks would have been worth if they had been sold.
        "value_eur": _round2(total_coupons * value),
        "per_product": [
            {"slug": r["_id"], "name": r["name"], "qty": r["qty"], "coupons": r["coupons"]}
            for r in per_product
        ],
        "per_staff": [
            {
                "staff_id": r["_id"],
                "name": names.get(r["_id"], "?"),
                "drinks": r["drinks"],
                "coupons": r["coupons"],
                "value_eur": _round2(r["coupons"] * value),
            }
            for r in per_staff
        ],
        "per_bar": [
            {
                "bar_id": r["_id"],
                "name": bars.get(r["_id"], "?"),
                "drinks": r["drinks"],
                "value_eur": _round2(r["coupons"] * value),
            }
            for r in per_bar
        ],
    }


async def stockout_impact(db: AsyncIOMotorDatabase, edition_id: str) -> list[dict]:
    """Estimate what a drink would have sold if it had not run out.

    The method is deliberately simple enough to explain in one line, because a
    purchasing decision rests on it:

        share of all drinks before it ran out  x  all drinks sold while it was gone

    If Jupiler was 30% of everything sold up to 23:00, and the bar sold 400 drinks
    between 23:00 and closing, roughly 120 of those would have been Jupiler.

    It refuses to guess when there is too little to go on. A drink that ran out in
    the first half hour has no reliable share to project, and a made-up number in a
    purchasing plan is worse than an honest gap.
    """
    windows = await db.stockouts.find({"edition_id": edition_id}).to_list(None)
    if not windows:
        return []

    # Bounded by the edition's own dates rather than by its first and last order. A
    # single stray sale, from a test or a tablet with a wrong clock, would otherwise
    # stretch the window by weeks and turn every estimate into nonsense.
    edition = await db.editions.find_one({"_id": edition_id})
    if edition is None:
        return []
    festival_start = edition["starts_at"]

    last = (
        await db.orders.find(
            {"edition_id": edition_id, **SOLD, "created_at": {"$lte": edition["ends_at"]}}
        )
        .sort("created_at", -1)
        .limit(1)
        .to_list(1)
    )
    if not last:
        return []
    festival_end = last[0]["created_at"]

    names = {p["slug"]: p["name"] async for p in db.products.find({"edition_id": edition_id})}

    async def drinks_between(start, end, slug: str | None, include_end: bool = False) -> int:
        # An open-ended outage runs to the last sale of the night, and that sale is
        # inside the window. A closed one ends when the drink came back, and a sale
        # at that instant is after it returned.
        upper = {"$lte": end} if include_end else {"$lt": end}
        match: dict = {"edition_id": edition_id, **SOLD, "created_at": {"$gte": start, **upper}}
        pipeline: list[dict] = [{"$match": match}, {"$unwind": "$items"}]
        if slug:
            pipeline.append({"$match": {"items.slug": slug}})
        pipeline.append({"$group": {"_id": None, "qty": {"$sum": "$items.qty"}}})
        rows = await db.orders.aggregate(pipeline).to_list(1)
        return rows[0]["qty"] if rows else 0

    MIN_DRINKS_BEFORE = 10
    MIN_MINUTES_BEFORE = 30

    out = []
    for w in windows:
        slug = w["slug"]
        out_at = w["out_at"]
        closed = w.get("back_at") is not None
        back_at = w.get("back_at") or festival_end
        # A window outside the festival's own dates is not a stockout worth
        # reporting: it is a tablet with a wrong clock, or a test.
        out_at = max(out_at, festival_start)
        back_at = min(back_at, festival_end)
        if back_at <= out_at:
            continue

        minutes_before = (out_at - festival_start).total_seconds() / 60
        sold_before = await drinks_between(festival_start, out_at, slug)
        all_before = await drinks_between(festival_start, out_at, None)
        all_during = await drinks_between(out_at, back_at, None, include_end=not closed)

        reliable = (
            sold_before >= MIN_DRINKS_BEFORE
            and minutes_before >= MIN_MINUTES_BEFORE
            and all_before > 0
        )
        share = sold_before / all_before if all_before else 0.0
        estimated_lost = round(share * all_during) if reliable else None

        # A window nobody sold through had no impact, and listing it is noise.
        if all_during == 0:
            continue

        out.append(
            {
                "slug": slug,
                "name": names.get(slug, slug),
                "out_at": out_at.isoformat(),
                "back_at": w.get("back_at").isoformat() if w.get("back_at") else None,
                "hours_out": round((back_at - out_at).total_seconds() / 3600, 1),
                "sold_before": sold_before,
                "share_before_pct": _round2(share * 100),
                "drinks_during_outage": all_during,
                "estimated_lost": estimated_lost,
                "reliable": reliable,
            }
        )
    return out
