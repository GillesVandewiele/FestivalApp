from fastapi import Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from . import throttle
from .config import Settings
from .models.common import utcnow
from .models.identity import Device, User
from .security import decode_access_token, hash_device_token

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
)
TOO_MANY_ATTEMPTS = HTTPException(
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    detail="Too many failed device codes. Wait a few minutes.",
)


def get_settings_from_app(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.db


async def get_current_user(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings_from_app),
) -> User:
    token = request.cookies.get("session")
    if not token:
        raise CREDENTIALS_ERROR
    try:
        user_id = decode_access_token(token, settings.jwt_secret)
    except Exception as exc:
        raise CREDENTIALS_ERROR from exc

    doc = await db.users.find_one({"_id": user_id})
    if doc is None:
        raise CREDENTIALS_ERROR
    return User(**doc)


async def get_current_device(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings_from_app),
) -> Device:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise CREDENTIALS_ERROR

    # Device codes are short enough to type, which is only safe with a guess limit.
    ip = request.client.host if request.client else "unknown"
    if throttle.is_blocked(ip):
        raise TOO_MANY_ATTEMPTS

    doc = await db.devices.find_one(
        {
            "token_hash": hash_device_token(token, settings.device_token_pepper),
            "revoked_at": None,
        }
    )
    if doc is None:
        throttle.record_failure(ip)
        raise CREDENTIALS_ERROR
    throttle.clear(ip)

    await db.devices.update_one({"_id": doc["_id"]}, {"$set": {"last_seen_at": utcnow()}})
    return Device(**doc)
