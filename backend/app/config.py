from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from the environment. Nothing is defaulted to a secret."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str
    mongo_db: str = "festival"

    jwt_secret: str = Field(min_length=32)
    device_token_pepper: str = Field(min_length=32)

    cors_origins: list[str] = Field(default_factory=list)
    access_token_ttl_minutes: int = 720
    cookie_secure: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
