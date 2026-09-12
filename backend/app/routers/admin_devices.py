from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from ..config import Settings
from ..deps import get_current_user, get_db, get_settings_from_app
from ..models.common import utcnow
from ..models.identity import Device
from ..security import generate_device_token, hash_device_token

router = APIRouter(
    prefix="/api/v1/admin/devices", tags=["devices"], dependencies=[Depends(get_current_user)]
)


class EnrollRequest(BaseModel):
    edition_id: str
    bar_id: str
    label: str


class EnrollResponse(BaseModel):
    id: str
    label: str
    token: str  # shown exactly once, never retrievable again


class DeviceOut(BaseModel):
    id: str
    edition_id: str
    bar_id: str
    label: str
    enrolled_at: datetime
    last_seen_at: datetime | None
    revoked_at: datetime | None


@router.post("/enroll", status_code=status.HTTP_201_CREATED)
async def enroll(
    body: EnrollRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings_from_app),
) -> EnrollResponse:
    token = generate_device_token()
    device = Device(
        edition_id=body.edition_id,
        bar_id=body.bar_id,
        label=body.label,
        token_hash=hash_device_token(token, settings.device_token_pepper),
    )
    await db.devices.insert_one(device.to_mongo())
    return EnrollResponse(id=device.id, label=device.label, token=token)


@router.get("")
async def list_devices(db: AsyncIOMotorDatabase = Depends(get_db)) -> list[DeviceOut]:
    return [
        DeviceOut(
            id=d["_id"],
            edition_id=d["edition_id"],
            bar_id=d["bar_id"],
            label=d["label"],
            enrolled_at=d["enrolled_at"],
            last_seen_at=d.get("last_seen_at"),
            revoked_at=d.get("revoked_at"),
        )
        async for d in db.devices.find({})
    ]


@router.post("/{device_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke(device_id: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> Response:
    result = await db.devices.update_one({"_id": device_id}, {"$set": {"revoked_at": utcnow()}})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
