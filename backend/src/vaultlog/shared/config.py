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

    host: str = "0.0.0.0"  # noqa: S104
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: str = "http://localhost:5173"
    service_name: str = "vaultlog-api"

    database_host: str = "localhost"
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "vaultlog"
    database_user: str = "vaultlog_app"
    database_password: str

    migration_database_user: str = "vaultlog_owner"
    migration_database_password: str

    jwt_issuer: str = "vaultlog"
    jwt_audience: str = "vaultlog-api"
    jwt_private_key_pem_path: str = "./keys/jwt-private.pem"
    jwt_public_key_pem_path: str = "./keys/jwt-public.pem"
    access_token_ttl_seconds: int = 600
    refresh_token_ttl_days: int = 30
    refresh_cookie_secure: bool = True

    def build_database_url(
        self,
        user: str,
        password: str,
        *,
        database_name: str | None = None,
    ) -> str:
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=user,
            password=password,
            host=self.database_host,
            port=self.database_port,
            path=database_name or self.database_name,
        ).unicode_string()

    @property
    def database_url(self) -> str:
        return self.build_database_url(self.database_user, self.database_password)

    @property
    def migration_database_url(self) -> str:
        return self.build_database_url(
            self.migration_database_user, self.migration_database_password
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
