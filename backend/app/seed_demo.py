"""Generate three editions of plausible sales, so the reports have something to show.

This is demo data, not a fixture and not production code. It exists so the organiser
app can be judged on real-looking numbers before the first real festival.

    make seed-demo

Everything it writes is deterministic: same seed, same festival, so a screenshot
taken today matches one taken next week.
"""

import asyncio
import random
from datetime import UTC, datetime, timedelta

from .config import get_settings
from .db import ensure_indexes, get_client
from .models.catalog import Bar, Edition, Product, PurchaseUnit, Staff
from .models.identity import Device
from .models.order import Order, OrderItem, Stockout, VoidActor, VoidInfo
from .security import generate_device_token, hash_device_token

SEED = 20260912

# slug, name, category, coupons, cost EUR, (packaging, units in it), relative popularity
DRINKS = [
    ("jupiler", "Jupiler", "bier", 1, 0.62, ("bak", 24), 100),
    ("duvel", "Duvel", "bier", 2, 1.35, ("bak", 24), 38),
    ("westmalle", "Westmalle", "bier", 2, 1.45, ("bak", 24), 26),
    ("witte-wijn", "Witte wijn", "wijn", 2, 1.10, ("doos", 6), 34),
    ("rode-wijn", "Rode wijn", "wijn", 2, 1.10, ("doos", 6), 22),
    ("cava", "Cava", "wijn", 3, 2.40, ("doos", 6), 18),
    ("gin-tonic", "Gin-tonic", "cocktail", 4, 1.95, ("fles", 12), 30),
    ("mojito", "Mojito", "cocktail", 4, 2.10, ("fles", 12), 24),
    ("cola", "Cola", "fris", 1, 0.45, ("bak", 24), 46),
    ("fanta", "Fanta", "fris", 1, 0.45, ("bak", 24), 24),
    ("water", "Water", "fris", 1, 0.28, ("bak", 24), 52),
    ("koffie", "Koffie", "warm", 1, 0.22, ("doos", 100), 16),
]

STAFF = ["Lotte", "Jonas", "Emma", "Wout", "Marie", "Sofie", "Bram", "Nore"]

# Local hour -> relative busyness. The night builds to a peak just after midnight.
CURVE = {17: 8, 18: 18, 19: 34, 20: 55, 21: 74, 22: 92, 23: 100, 0: 88, 1: 60, 2: 32, 3: 14}

# year -> (scale, coupon value). The festival grew, and coupons got more expensive.
EDITIONS = [
    (2024, 0.72, 2.00),
    (2025, 0.86, 2.20),
    (2026, 1.00, 2.50),
]

# Trends worth seeing in the year-over-year report rather than flat growth everywhere.
TRENDS = {
    "water": {2024: 0.62, 2025: 0.80, 2026: 1.25},  # people drink more water every year
    "cava": {2024: 1.45, 2025: 1.20, 2026: 0.70},  # cava is falling out of favour
    "mojito": {2024: 0.0, 2025: 0.55, 2026: 1.30},  # only introduced in 2025
    "koffie": {2024: 1.30, 2025: 1.10, 2026: 0.95},
}


async def seed_demo() -> None:
    # Deterministic by design: the same seed must produce the same festival, so a
    # screenshot stays valid. Nothing security-relevant depends on this stream.
    rng = random.Random(SEED)  # noqa: S311
    settings = get_settings()
    client = get_client(settings.mongo_uri)
    db = client[settings.mongo_db]
    await ensure_indexes(db)

    for name in ("editions", "bars", "products", "staff", "orders", "stockouts", "devices"):
        await db[name].delete_many({})

    tokens: list[tuple[str, str]] = []
    summary: list[tuple[str, int, int]] = []

    for year, scale, coupon_value in EDITIONS:
        # A July weekend, anchored so the data is stable across runs.
        # 13:00 UTC is 15:00 in Brussels in July, so the CURVE keys below read as
        # local hours, which is how anyone looking at the chart will read them.
        start = datetime(year, 7, 4, 13, 0, tzinfo=UTC)
        edition = Edition(
            name=f"Festival {year}",
            year=year,
            starts_at=start,
            ends_at=start + timedelta(days=2),
            coupon_value_eur=coupon_value,
            is_active=(year == EDITIONS[-1][0]),
        )
        await db.editions.insert_one(edition.to_mongo())

        bars = [
            Bar(edition_id=edition.id, name="Hoofdpodium", sort_order=0),
            Bar(edition_id=edition.id, name="Cocktailbar", sort_order=1),
            Bar(edition_id=edition.id, name="Kampeerterrein", sort_order=2),
        ]
        await db.bars.insert_many([b.to_mongo() for b in bars])

        products: list[Product] = []
        weights: dict[str, float] = {}
        for i, (slug, name, category, coupons, cost, (pack, size), popularity) in enumerate(DRINKS):
            trend = TRENDS.get(slug, {}).get(year, 1.0)
            if trend == 0.0:
                continue  # not on sale that year
            available = [bars[1].id] if category == "cocktail" else [b.id for b in bars]
            # Cost prices drift up a little each year, as they do.
            drift = 1 + (year - 2024) * 0.04
            products.append(
                Product(
                    edition_id=edition.id,
                    slug=slug,
                    name=name,
                    category=category,
                    price_coupons=coupons,
                    cost_price_eur=round(cost * drift, 2),
                    purchase_unit=PurchaseUnit(name=pack, size=size),
                    available_at=available,
                    sort_order=i,
                )
            )
            weights[slug] = popularity * trend
        await db.products.insert_many([p.to_mongo() for p in products])

        staff = [Staff(edition_id=edition.id, name=n) for n in STAFF]
        await db.staff.insert_many([s.to_mongo() for s in staff])

        by_bar: dict[str, list[Product]] = {
            b.id: [p for p in products if b.id in p.available_at] for b in bars
        }
        # The camp site is quieter than the main stage.
        bar_share = {bars[0].id: 1.0, bars[1].id: 0.55, bars[2].id: 0.35}

        orders: list[Order] = []
        for day in range(2):
            for hour, busy in CURVE.items():
                when_day = start + timedelta(days=day, hours=(hour - 15) % 24)
                for bar in bars:
                    count = round(busy * scale * bar_share[bar.id] * 0.42)
                    catalogue = by_bar[bar.id]
                    pool = [p for p in catalogue for _ in range(int(weights[p.slug]))]
                    if not pool:
                        continue
                    for _ in range(count):
                        picks: list[Product] = []
                        for _ in range(rng.choice([1, 1, 1, 2, 2, 3])):
                            candidate = rng.choice(pool)
                            if candidate not in picks:
                                picks.append(candidate)
                        items = [
                            OrderItem(
                                product_id=p.id,
                                slug=p.slug,
                                name=p.name,
                                qty=rng.choice([1, 1, 1, 2, 2, 3]),
                                unit_price_coupons=p.price_coupons,
                            )
                            for p in picks
                        ]
                        created = when_day + timedelta(minutes=rng.randint(0, 59))
                        order = Order(
                            edition_id=edition.id,
                            bar_id=bar.id,
                            staff_id=rng.choice(staff).id,
                            device_id=f"demo-{bar.id[:8]}",
                            items=items,
                            total_coupons=sum(i.qty * i.unit_price_coupons for i in items),
                            created_at=created,
                            received_at=created,
                            # A realistic trickle of corrections, so void rate is visible.
                            status="voided" if rng.random() < 0.012 else "confirmed",
                        )
                        if order.status == "voided":
                            order.void = VoidInfo(
                                at=created, by=VoidActor(type="staff", id=order.staff_id)
                            )
                        orders.append(order)

        for i in range(0, len(orders), 500):
            await db.orders.insert_many([o.to_mongo() for o in orders[i : i + 500]])

        # Jupiler ran dry on the main stage on the second night. Demand was censored,
        # which is what makes the purchasing advice for that row interesting.
        if year == EDITIONS[-1][0]:
            jupiler = next(p for p in products if p.slug == "jupiler")
            await db.stockouts.insert_one(
                Stockout(
                    edition_id=edition.id,
                    bar_id=bars[0].id,
                    product_id=jupiler.id,
                    slug=jupiler.slug,
                    out_at=start + timedelta(days=1, hours=9),
                ).to_mongo()
            )

            for bar in bars:
                token = generate_device_token()
                await db.devices.insert_one(
                    Device(
                        edition_id=edition.id,
                        bar_id=bar.id,
                        label=f"Tablet {bar.name}",
                        token_hash=hash_device_token(token, settings.device_token_pepper),
                    ).to_mongo()
                )
                tokens.append((bar.name, token))

        drinks = sum(i.qty for o in orders if o.status == "confirmed" for i in o.items)
        summary.append((edition.name, len(orders), drinks))

    print("\nDemo data ready.\n")
    for name, order_count, drinks in summary:
        print(f"  {name}:  {order_count:>5} bestellingen, {drinks:>6} consumpties")
    print("\nDevice tokens for the current edition:\n")
    for bar_name, token in tokens:
        print(f"  {bar_name:16} {token}")
    print()
    client.close()


if __name__ == "__main__":
    asyncio.run(seed_demo())
