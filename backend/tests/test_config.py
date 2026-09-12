import pytest
from pydantic import ValidationError

from app.config import Settings

# _env_file=None keeps these hermetic: a developer's local backend/.env must not
# decide whether a test passes.
BASE = {"_env_file": None}


def test_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGO_DB", "festival")
    monkeypatch.setenv("JWT_SECRET", "s" * 32)
    monkeypatch.setenv("DEVICE_TOKEN_PEPPER", "p" * 32)
    monkeypatch.setenv("CORS_ORIGINS", '["https://pos.example.com"]')

    s = Settings(**BASE)

    assert s.mongo_db == "festival"
    assert s.cors_origins == ["https://pos.example.com"]
    assert s.access_token_ttl_minutes == 720
    assert s.cookie_secure is True


def test_missing_secret_is_a_startup_error(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("DEVICE_TOKEN_PEPPER", "p" * 32)
    with pytest.raises(ValidationError):
        Settings(**BASE)


def test_short_secrets_are_rejected(monkeypatch):
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("JWT_SECRET", "tooshort")
    monkeypatch.setenv("DEVICE_TOKEN_PEPPER", "p" * 32)
    with pytest.raises(ValidationError):
        Settings(**BASE)
