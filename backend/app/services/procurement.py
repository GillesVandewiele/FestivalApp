"""Purchasing advice for the next edition.

The arithmetic is deliberately simple and fully exposed in the response, because a
forecast nobody can audit is a forecast nobody will trust in a year.

    advised  = ceil(sold x (1 + growth) x (1 + safety))
    to_order = ceil(advised / purchase_unit.size)
"""

import math

from motor.motor_asyncio import AsyncIOMotorDatabase

from . import stats

DEFAULT_SAFETY_PCT = 10.0
STOCKOUT_SAFETY_PCT = 25.0


async def advise(
    db: AsyncIOMotorDatabase,
    edition_id: str,
    growth_pct: float | None = None,
    safety_pct: float = DEFAULT_SAFETY_PCT,
    stockout_safety_pct: float = STOCKOUT_SAFETY_PCT,
    compare_to: str | None = None,
) -> list[dict]:
    products = await stats.by_product(db, edition_id)
    catalog = {p["slug"]: p async for p in db.products.find({"edition_id": edition_id})}

    stocked_out = {s["slug"] async for s in db.stockouts.find({"edition_id": edition_id})}

    observed: dict[str, float | None] = {}
    if compare_to is not None:
        for row in await stats.compare(db, compare_to, edition_id):
            observed[row["slug"]] = row["pct"]

    out = []
    for row in products:
        slug = row["slug"]
        product = catalog.get(slug, {})
        had_stockout = slug in stocked_out

        # A recorded stockout means demand was censored, so buy with more room.
        row_safety = stockout_safety_pct if had_stockout else safety_pct
        row_growth = growth_pct if growth_pct is not None else (observed.get(slug) or 0.0)

        sold = row["qty"]
        advised = math.ceil(sold * (1 + row_growth / 100) * (1 + row_safety / 100))

        unit = product.get("purchase_unit")
        unit_size = unit["size"] if unit else None
        units = math.ceil(advised / unit_size) if unit_size else None

        # Whole packs only, so you always end up with more than the advice. That
        # overshoot is real stock you carry: you cannot return a partial bak.
        total_units = units * unit_size if units is not None else None
        surplus = total_units - advised if total_units is not None else None

        cost_price = product.get("cost_price_eur")
        cost = (
            round(units * unit_size * cost_price, 2)
            if units is not None and cost_price is not None
            else None
        )

        out.append(
            {
                "slug": slug,
                "name": row["name"],
                "sold": sold,
                "growth_pct": round(row_growth, 2),
                "safety_pct": row_safety,
                "advised": advised,
                "purchase_unit": unit["name"] if unit else None,
                "unit_size": unit_size,
                "units_to_order": units,
                "total_units": total_units,
                "surplus_units": surplus,
                "cost_eur": cost,
                "cost_known": cost is not None,
                "had_stockout": had_stockout,
            }
        )
    return out
