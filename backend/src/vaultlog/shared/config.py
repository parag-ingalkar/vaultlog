from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"

    host: str = "localhost"
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: str = "http://localhost:5173"

    database_host: str = "localhost"
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "vaultlog"
    database_user: str = "vaultlog_app"
    database_password: str

    service_name: str = "vaultlog-api"

    @property
    def database_url(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.database_user,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            path=self.database_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
