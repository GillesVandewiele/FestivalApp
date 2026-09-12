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


# Crockford base32: no I, L, O or U. Nothing ambiguous to mistype when a code is
# read aloud across a bar, and nothing accidentally rude.
CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CODE_LENGTH = 12  # 32**12 == 2**60
_CODE_FOLD = str.maketrans({"I": "1", "L": "1", "O": "0"})


def generate_device_token() -> str:
    """A 12-character code, 60 bits, grouped for reading aloud: XXXX-XXXX-XXXX.

    Short because somebody types it into a tablet. Safe at that length only because
    failed device authentications are throttled; see deps.get_current_device.
    """
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
    return "-".join(raw[i : i + 4] for i in range(0, CODE_LENGTH, 4))


def normalise_device_token(token: str) -> str:
    """Fold the ways a human can retype the same code into one canonical form.

    Lowercase, spaces, missing dashes, and the classic I/1 and O/0 confusions all
    resolve to the same string, which is then what gets hashed.
    """
    cleaned = "".join(ch for ch in token.upper() if ch.isalnum())
    return cleaned.translate(_CODE_FOLD)


def hash_device_token(token: str, pepper: str) -> str:
    """HMAC rather than argon2: this runs on every tablet request and must be fast.

    Device tokens are already high-entropy, so the slow-hash protection that passwords
    need (guarding weak human choices) buys nothing here.
    """
    return hmac.new(
        pepper.encode(), normalise_device_token(token).encode(), hashlib.sha256
    ).hexdigest()


def verify_device_token(token: str, token_hash: str, pepper: str) -> bool:
    return hmac.compare_digest(hash_device_token(token, pepper), token_hash)


def create_access_token(subject: str, secret: str, ttl_minutes: int) -> str:
    now = datetime.now(UTC)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=ttl_minutes)}
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> str:
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    return payload["sub"]
