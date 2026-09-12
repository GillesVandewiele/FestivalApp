from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from ..deps import get_current_device, get_db
from ..models.common import utcnow
from ..models.identity import Device
from ..models.order import OrderIn, StockoutIn
from ..services.orders import upsert_order

router = APIRouter(prefix="/api/v1", tags=["sync"])


def _serialise(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


class OrderBatch(BaseModel):
    orders: list[OrderIn]


class StockoutBatch(BaseModel):
    stockouts: list[StockoutIn]


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
            {"edition_id": device.edition_id, "active": True, "available_at": device.bar_id}
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

    accepted = [oid for oid, outcome in results.items() if outcome in ("inserted", "updated")]
    return {"accepted": accepted, "results": results}


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
            {
                "$set": {
                    "edition_id": device.edition_id,
                    "bar_id": device.bar_id,
                    "product_id": item.product_id,
                    "slug": product["slug"],
                    "out_at": item.out_at,
                    "back_at": item.back_at,
                }
            },
            upsert=True,
        )
        accepted.append(item.id)
    return {"accepted": accepted}
