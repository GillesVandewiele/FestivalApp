from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from ..deps import get_current_user, get_db
from ..models.common import utcnow
from ..models.identity import User

router = APIRouter(
    prefix="/api/v1/admin/orders",
    tags=["admin-orders"],
    dependencies=[Depends(get_current_user)],
)


class VoidRequest(BaseModel):
    reason: str = Field(min_length=1)  # organiser voids must be explained


@router.post("/{order_id}/void")
async def void_order(
    order_id: str,
    body: VoidRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    doc = await db.orders.find_one_and_update(
        {"_id": order_id},
        {
            "$set": {
                "status": "voided",
                "void": {
                    "at": utcnow(),
                    "by": {"type": "user", "id": user.id},
                    "reason": body.reason,
                },
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")
    doc["id"] = doc.pop("_id")
    return doc
