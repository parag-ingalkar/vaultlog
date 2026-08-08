"""Pytest bootstrap: force test database settings before application imports."""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_NAME", "vaultlog_test")
os.environ.setdefault("MFA_KEK_B64", "6wAJZT3eh0Dqko9JxuXfLr8Tmct0ZwrYqvmQuwkGZwU=")

from vaultlog.shared.config import get_settings

get_settings.cache_clear()

pytest_plugins = [
    "tests.integration.fixtures.database",
    "tests.integration.fixtures.migrations",
    "tests.integration.fixtures.sessions",
]


def pytest_sessionstart(session) -> None:
    settings = get_settings()
    if settings.database_name == "vaultlog":
        msg = (
            "Tests must not use the development database (vaultlog). "
            "DATABASE_NAME must be vaultlog_test."
        )
        raise RuntimeError(msg)
