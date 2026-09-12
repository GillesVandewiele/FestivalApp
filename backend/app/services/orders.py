from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from ..models.common import utcnow
from ..models.identity import Device
from ..models.order import OrderIn

Outcome = str  # "inserted" | "updated" | "ignored" | "rejected"


async def upsert_order(db: AsyncIOMotorDatabase, order_in: OrderIn, device: Device) -> Outcome:
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
        "device_id": device.id,  # from the token, never from the payload
        "items": [i.model_dump() for i in order_in.items],
        "total_coupons": total,  # recomputed, never trusted
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
        # The filter excluded an existing voided document, so the upsert tried to insert
        # a duplicate _id. That means: already voided. Leave it alone.
        return "ignored"

    return "inserted" if result.upserted_id is not None else "updated"
