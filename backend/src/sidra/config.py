from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from sidra.constants import SEFARIA_BASE_URL


class Settings(BaseSettings):
    """Runtime configuration. Every field is overridable via a SIDRA_-prefixed environment variable."""

    model_config = SettingsConfigDict(env_prefix="SIDRA_", env_file=".env", extra="ignore")

    postgres_host: str = "localhost"
    postgres_port: int = 5524
    postgres_db: str = "sidra"
    postgres_user: str = "sidra"
    # S105: a local-development default matching docker-compose.yml, not a secret. The real
    # value comes from SIDRA_POSTGRES_PASSWORD; this app never leaves localhost.
    postgres_password: str = "sidra_dev"  # noqa: S105
    sefaria_base_url: str = SEFARIA_BASE_URL
    http_timeout_seconds: float = 30.0
    api_port: int = 8285
    cors_origins: str = "http://localhost:5285,http://127.0.0.1:5285"
    """Comma-separated allowlist. The frontend origin only -- never a wildcard."""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
