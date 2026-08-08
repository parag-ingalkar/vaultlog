# Integration test fixtures

Integration tests always run against **`vaultlog_test`**, never the development `vaultlog` database. `tests/conftest.py` sets `DATABASE_NAME=vaultlog_test` and refuses `vaultlog`.

## Layout

| Module | Fixtures |
|--------|----------|
| `constants.py` | `TENANT_A`, `TENANT_B`, `VAULT_A_ID` |
| `database.py` | `ensure_test_database`, `owner_engine`, `app_engine` |
| `migrations.py` | `migrated_schema` (session Alembic upgrade head) |
| `cleanup.py` | `truncate_all_tables()` helper |
| `seed.py` | `seed_baseline_data()` helper |
| `sessions.py` | `db_reset`, `scoped_session`, identity/UoW/use-case fixtures |

## Per-test isolation

`db_reset` (autouse) runs before and after each test:

1. `TRUNCATE` all `public` tables except `alembic_version` `CASCADE`
2. Seed baseline organizations and vault
3. Run test
4. `TRUNCATE` again

Tests that commit via use cases (auth flows) leave a clean slate for the next test.

Tests marked `@pytest.mark.schema` skip `db_reset` (schema migration lifecycle tests).

## Reusing fixtures in new tests

```python
from tests.integration.fixtures.constants import TENANT_A


async def test_my_feature(scoped_session, register_user): ...
```

Add new shared fixtures to `sessions.py` (or a new module registered in `integration/conftest.py` `pytest_plugins`).

## First-time setup

- New Docker volumes: `init.sql` creates `vaultlog_test` and grants `CREATEDB` to `vaultlog_owner`.
- Existing volumes: `ensure_test_database` probes `vaultlog_test`, then creates it via `vaultlog_owner` or the Compose bootstrap superuser (`postgres_bootstrap` by default). Override with `TEST_DATABASE_BOOTSTRAP_USER` / `TEST_DATABASE_BOOTSTRAP_PASSWORD` if needed.

Run integration tests:

```bash
uv run pytest tests/integration -v
```
