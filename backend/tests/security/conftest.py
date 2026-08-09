from __future__ import annotations

from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from vaultlog.infrastructure.security.tokens import TokenService
from vaultlog.main import create_app
from vaultlog.shared.config import get_settings


@pytest.fixture()
def client() -> Iterator[TestClient]:
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture()
def token_service() -> TokenService:
    return TokenService(get_settings())
