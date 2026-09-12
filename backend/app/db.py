from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, IndexModel

COLLECTIONS: tuple[str, ...] = (
    "editions",
    "bars",
    "products",
    "staff",
    "orders",
    "stockouts",
    "users",
    "devices",
)


def get_client(uri: str) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(uri, tz_aware=True, uuidRepresentation="standard")


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Idempotent. Safe to run on every startup."""
    await db.orders.create_indexes(
        [
            IndexModel([("edition_id", ASCENDING), ("created_at", ASCENDING)]),
            IndexModel(
                [("edition_id", ASCENDING), ("status", ASCENDING), ("created_at", ASCENDING)]
            ),
            IndexModel(
                [("edition_id", ASCENDING), ("bar_id", ASCENDING), ("created_at", ASCENDING)]
            ),
            IndexModel([("edition_id", ASCENDING), ("staff_id", ASCENDING)]),
        ]
    )
    await db.products.create_indexes(
        [
            IndexModel([("edition_id", ASCENDING), ("slug", ASCENDING)], unique=True),
            IndexModel([("slug", ASCENDING)]),
        ]
    )
    await db.devices.create_indexes([IndexModel([("token_hash", ASCENDING)], unique=True)])
    await db.users.create_indexes([IndexModel([("email", ASCENDING)], unique=True)])
    await db.stockouts.create_indexes(
        [IndexModel([("edition_id", ASCENDING), ("product_id", ASCENDING), ("out_at", ASCENDING)])]
    )
