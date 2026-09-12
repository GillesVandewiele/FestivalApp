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


def test_device_tokens_are_unique():
    """Length is no longer the guarantee: codes are short so they can be typed, and
    the entropy check lives in the alphabet and length test below."""
    assert generate_device_token() != generate_device_token()


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


def test_device_codes_are_short_enough_to_type_and_long_enough_to_be_safe():
    from app.security import CODE_ALPHABET, CODE_LENGTH

    code = generate_device_token()
    assert len(code) == 14  # 12 characters plus two dashes
    assert code.count("-") == 2
    assert all(ch in CODE_ALPHABET for ch in code.replace("-", ""))
    assert CODE_LENGTH == 12  # 32**12 == 2**60


def test_device_codes_avoid_ambiguous_letters():
    """Nobody should have to ask whether that was a one or an ell."""
    from app.security import CODE_ALPHABET

    for ambiguous in "ILOU":
        assert ambiguous not in CODE_ALPHABET


def test_a_retyped_code_still_works():
    from app.security import normalise_device_token

    canonical = normalise_device_token("A1B2-C3D4-E5F6")
    for variant in ("a1b2-c3d4-e5f6", "A1B2C3D4E5F6", "a1b2 c3d4 e5f6", " A1B2-C3D4-E5F6 "):
        assert normalise_device_token(variant) == canonical


def test_confusable_characters_fold_to_the_same_code():
    from app.security import normalise_device_token

    assert normalise_device_token("IOL1-2345-6789") == normalise_device_token("1011-2345-6789")


def test_a_retyped_code_authenticates(monkeypatch):
    """The hash is taken of the normalised form, so sloppy retyping still matches."""
    token = generate_device_token()
    stored = hash_device_token(token, PEPPER)

    assert verify_device_token(token.lower().replace("-", ""), stored, PEPPER)
