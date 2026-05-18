"""Application settings loaded from .env via Pydantic BaseSettings."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    emr_username: SecretStr = Field(..., description="EMR login username")
    emr_password: SecretStr = Field(..., description="EMR login password")
    emr_base_url: str = Field(..., description="EMR base URL")
    emr_puskesmas: str = Field(..., description="Puskesmas name to select on login")
    browser_mode: Literal["headless", "visible"] = Field(default="headless")
    scrape_timeout: int = Field(default=60, ge=10, le=600)
    database_url: str = Field(default="sqlite+aiosqlite:///./rekap_in.db")
    app_host: str = Field(default="127.0.0.1")
    app_port: int = Field(default=8000, ge=1, le=65535)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()  # type: ignore[call-arg]


# Module-level alias for convenience
settings = get_settings()
