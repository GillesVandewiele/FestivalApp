"""Create a demo festival and enrol one tablet, for local testing.

Not used in production. Run with: make seed
"""

import asyncio
from datetime import UTC, datetime, timedelta

from .config import get_settings
from .db import ensure_indexes, get_client
from .models.catalog import Bar, Category, Edition, Product, PurchaseUnit, Staff
from .models.identity import Device
from .security import generate_device_token, hash_device_token

# slug, name, category, coupons, cost EUR, (purchase unit, size)
DRINKS = [
    ("jupiler", "Jupiler", "bier", 1, 0.62, ("bak", 24)),
    ("duvel", "Duvel", "bier", 2, 1.35, ("bak", 24)),
    ("westmalle", "Westmalle", "bier", 2, 1.45, ("bak", 24)),
    ("witte-wijn", "Witte wijn", "wijn", 2, 1.10, ("doos", 6)),
    ("rode-wijn", "Rode wijn", "wijn", 2, 1.10, ("doos", 6)),
    ("cava", "Cava", "wijn", 3, 2.40, ("doos", 6)),
    ("gin-tonic", "Gin-tonic", "cocktail", 4, 1.95, ("fles", 12)),
    ("mojito", "Mojito", "cocktail", 4, 2.10, ("fles", 12)),
    ("cola", "Cola", "fris", 1, 0.45, ("bak", 24)),
    ("fanta", "Fanta", "fris", 1, 0.45, ("bak", 24)),
    ("water", "Water", "fris", 1, 0.28, ("bak", 24)),
    ("koffie", "Koffie", "warm", 1, 0.22, ("doos", 100)),
]

CATEGORIES = [
    ("bier", "Bier", "#e8a33d"),
    ("wijn", "Wijn", "#c0566f"),
    ("cocktail", "Cocktail", "#4fb3a5"),
    ("fris", "Frisdrank", "#5b9bd5"),
    ("warm", "Warme dranken", "#a9764a"),
]

STAFF = ["Lotte", "Jonas", "Emma", "Wout", "Marie", "Sofie"]


async def seed() -> None:
    settings = get_settings()
    client = get_client(settings.mongo_uri)
    db = client[settings.mongo_db]
    await ensure_indexes(db)

    for name in (
        "editions",
        "bars",
        "categories",
        "products",
        "staff",
        "orders",
        "stockouts",
        "devices",
    ):
        await db[name].delete_many({})

    now = datetime.now(UTC)
    edition = Edition(
        name=f"Festival {now.year}",
        year=now.year,
        starts_at=now - timedelta(hours=2),
        ends_at=now + timedelta(days=2),
        coupon_value_eur=2.50,
    )
    await db.editions.insert_one(edition.to_mongo())

    bars = [
        Bar(edition_id=edition.id, name="Hoofdpodium", sort_order=0),
        Bar(edition_id=edition.id, name="Cocktailbar", sort_order=1),
    ]
    await db.bars.insert_many([b.to_mongo() for b in bars])
    await db.categories.insert_many(
        [
            Category(
                edition_id=edition.id, slug=slug, name=name, colour=colour, sort_order=i
            ).to_mongo()
            for i, (slug, name, colour) in enumerate(CATEGORIES)
        ]
    )

    products = []
    for i, (slug, name, category, coupons, cost, (unit, size)) in enumerate(DRINKS):
        # The cocktail bar sells everything; the main stage skips cocktails.
        available = [bars[1].id] if category == "cocktail" else [b.id for b in bars]
        products.append(
            Product(
                edition_id=edition.id,
                slug=slug,
                name=name,
                category=category,
                price_coupons=coupons,
                cost_price_eur=cost,
                purchase_unit=PurchaseUnit(name=unit, size=size),
                available_at=available,
                sort_order=i,
            )
        )
    await db.products.insert_many([p.to_mongo() for p in products])
    await db.staff.insert_many([Staff(edition_id=edition.id, name=n).to_mongo() for n in STAFF])

    tokens = []
    for bar in bars:
        token = generate_device_token()
        device = Device(
            edition_id=edition.id,
            bar_id=bar.id,
            label=f"Demo tablet {bar.name}",
            token_hash=hash_device_token(token, settings.device_token_pepper),
        )
        await db.devices.insert_one(device.to_mongo())
        tokens.append((bar.name, token))

    print(f"\nSeeded {edition.name}: {len(bars)} bars, {len(products)} drinks, {len(STAFF)} staff.")
    print("\nDevice tokens (paste one into the POS app to link a tablet):\n")
    for bar_name, token in tokens:
        print(f"  {bar_name:14} {token}")
    print()
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
