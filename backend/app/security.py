import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def generate_device_token() -> str:
    return secrets.token_urlsafe(32)


def hash_device_token(token: str, pepper: str) -> str:
    """HMAC rather than argon2: this runs on every tablet request and must be fast.

    Device tokens are already high-entropy, so the slow-hash protection that passwords
    need (guarding weak human choices) buys nothing here.
    """
    return hmac.new(pepper.encode(), token.encode(), hashlib.sha256).hexdigest()


def verify_device_token(token: str, token_hash: str, pepper: str) -> bool:
    return hmac.compare_digest(hash_device_token(token, pepper), token_hash)


def create_access_token(subject: str, secret: str, ttl_minutes: int) -> str:
    now = datetime.now(UTC)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=ttl_minutes)}
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> str:
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    return payload["sub"]
