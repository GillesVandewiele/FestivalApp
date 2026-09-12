from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr

from ..config import Settings
from ..deps import get_current_user, get_db, get_settings_from_app
from ..middleware import limiter
from ..models.identity import User
from ..security import create_access_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: str


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings_from_app),
) -> UserOut:
    doc = await db.users.find_one({"email": body.email})
    # One identical error for both cases, so the response cannot enumerate accounts.
    if doc is None or not verify_password(body.password, doc["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    user = User(**doc)
    token = create_access_token(user.id, settings.jwt_secret, settings.access_token_ttl_minutes)
    response.set_cookie(
        "session",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.access_token_ttl_minutes * 60,
    )
    return UserOut(id=user.id, email=user.email, role=user.role)


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie("session", httponly=True, samesite="strict")
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(id=user.id, email=user.email, role=user.role)
