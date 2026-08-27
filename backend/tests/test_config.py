from __future__ import annotations

import pytest

from sidra.config import Settings, get_settings

_SIDRA_ENV_VARS = (
    "SIDRA_POSTGRES_HOST",
    "SIDRA_POSTGRES_PORT",
    "SIDRA_POSTGRES_DB",
    "SIDRA_POSTGRES_USER",
    "SIDRA_POSTGRES_PASSWORD",
    "SIDRA_SEFARIA_BASE_URL",
    "SIDRA_HTTP_TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _SIDRA_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()


def test_defaults_match_the_allocated_ports() -> None:
    settings = Settings()
    assert settings.postgres_port == 5524
    assert settings.postgres_db == "sidra"
    assert settings.sefaria_base_url == "https://www.sefaria.org/api"


def test_env_prefix_is_sidra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIDRA_POSTGRES_DB", "sidra_test")
    assert Settings().postgres_db == "sidra_test"


def test_database_url_is_an_asyncpg_dsn() -> None:
    settings = Settings(
        postgres_host="db",
        postgres_port=5432,
        postgres_user="u",
        postgres_password="p",
    )
    assert settings.database_url == "postgresql+asyncpg://u:p@db:5432/sidra"


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
