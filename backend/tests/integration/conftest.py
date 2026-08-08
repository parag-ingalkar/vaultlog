"""Integration tests use vaultlog_test with per-test TRUNCATE + reseed (see fixtures/)."""

from __future__ import annotations

import pytest
import pytest_asyncio

from tests.integration.fixtures.cleanup import truncate_all_tables
from tests.integration.fixtures.seed import seed_baseline_data

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def db_reset(request, owner_engine, migrated_schema):
    if request.node.get_closest_marker("schema") is not None:
        yield
        return

    await truncate_all_tables(owner_engine)
    await seed_baseline_data(owner_engine)
    yield
    await truncate_all_tables(owner_engine)
