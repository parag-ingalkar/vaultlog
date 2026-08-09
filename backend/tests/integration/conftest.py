from __future__ import annotations

from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from tests.integration.fixtures.cleanup import truncate_all_tables
from vaultlog.main import create_app


@pytest.fixture()
def client() -> Iterator[TestClient]:
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
async def _truncate_between_integration_tests(request, owner_engine) -> None:
    if "integration" not in request.node.nodeid:
        return
    await truncate_all_tables(owner_engine)


@pytest.fixture()
async def baseline_data(owner_engine, app_engine) -> None:
    from tests.integration.fixtures.seed import seed_baseline_data

    await seed_baseline_data(owner_engine, app_engine)
