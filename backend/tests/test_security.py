import pytest
from jwt import ExpiredSignatureError, InvalidSignatureError

from app.security import (
    create_access_token,
    decode_access_token,
    generate_device_token,
    hash_device_token,
    hash_password,
    verify_device_token,
    verify_password,
)

PEPPER = "pepper" * 8


def test_password_round_trip():
    hashed = hash_password("correct horse")
    assert hashed != "correct horse"
    assert verify_password("correct horse", hashed)
    assert not verify_password("wrong horse", hashed)


def test_password_hashes_are_salted():
    """Two identical passwords must not produce the same hash."""
    assert hash_password("same") != hash_password("same")


def test_device_tokens_are_long_and_unique():
    a, b = generate_device_token(), generate_device_token()
    assert a != b
    assert len(a) >= 32


def test_device_token_round_trip():
    token = generate_device_token()
    h = hash_device_token(token, PEPPER)
    assert h != token
    assert verify_device_token(token, h, PEPPER)
    assert not verify_device_token("other-token", h, PEPPER)


def test_device_token_hash_depends_on_the_pepper():
    """A stolen database is useless without the pepper, which lives only in env."""
    token = generate_device_token()
    assert hash_device_token(token, PEPPER) != hash_device_token(token, "other" * 8)


def test_access_token_round_trip():
    token = create_access_token("user-1", "secret" * 8, ttl_minutes=60)
    assert decode_access_token(token, "secret" * 8) == "user-1"


def test_access_token_rejects_a_wrong_signature():
    token = create_access_token("user-1", "secret" * 8, ttl_minutes=60)
    with pytest.raises(InvalidSignatureError):
        decode_access_token(token, "different" * 8)


def test_expired_access_token_is_rejected():
    token = create_access_token("user-1", "secret" * 8, ttl_minutes=-1)
    with pytest.raises(ExpiredSignatureError):
        decode_access_token(token, "secret" * 8)
