from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from scripts.rls.apply import (
    TENANT_TABLES,
    _split_sql_statements,
    apply_rls_policies,
    is_upgrade_revision,
    policy_table_names,
)
from scripts.rls.new_policy import render_policy

BACKEND_ROOT = Path(__file__).resolve().parents[2]
INITIAL_REVISION = "a1b2c3d4e5f6"
IDENTITY_REVISION = "6dc854c15a49"


def _script_dir() -> ScriptDirectory:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    return ScriptDirectory.from_config(config)


def test_split_sql_statements():
    sql = "ALTER TABLE t ENABLE ROW LEVEL SECURITY;\n\nDROP POLICY IF EXISTS p ON t;\n"
    assert len(_split_sql_statements(sql)) == 2


def test_render_policy_defaults():
    sql = render_policy("vault_grant")
    assert "{{" not in sql
    assert "vault_grant" in sql
    assert "tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid" in sql


def test_render_policy_organization_column():
    sql = render_policy("organization", tenant_column="id")
    assert "id = NULLIF(current_setting('app.current_tenant', true), '')::uuid" in sql


def test_policy_files_match_tenant_tables():
    assert policy_table_names() == TENANT_TABLES


@pytest.mark.parametrize("table", sorted(TENANT_TABLES))
def test_each_policy_file_contains_tenant_isolation(table: str):
    path = BACKEND_ROOT / "scripts" / "rls" / "policies" / f"{table}.sql"
    sql = path.read_text(encoding="utf-8")
    assert "tenant_isolation" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "WITH CHECK" in sql


def test_is_upgrade_revision_forward():
    script_dir = _script_dir()
    assert is_upgrade_revision(script_dir, INITIAL_REVISION, IDENTITY_REVISION)


def test_is_upgrade_revision_backward():
    script_dir = _script_dir()
    assert not is_upgrade_revision(script_dir, IDENTITY_REVISION, INITIAL_REVISION)


def test_is_upgrade_revision_same():
    script_dir = _script_dir()
    assert not is_upgrade_revision(script_dir, IDENTITY_REVISION, IDENTITY_REVISION)


def test_is_upgrade_revision_from_empty():
    script_dir = _script_dir()
    assert is_upgrade_revision(script_dir, None, INITIAL_REVISION)


def test_is_upgrade_revision_to_empty():
    script_dir = _script_dir()
    assert not is_upgrade_revision(script_dir, INITIAL_REVISION, None)


def test_apply_skips_missing_table_when_not_strict():
    connection = MagicMock()
    connection.execute.return_value.scalar.return_value = False

    apply_rls_policies(connection, strict=False)

    assert connection.execute.call_count == len(TENANT_TABLES)


def test_apply_raises_on_missing_table_when_strict():
    connection = MagicMock()
    connection.execute.return_value.scalar.return_value = False

    with pytest.raises(RuntimeError, match="missing table"):
        apply_rls_policies(connection, strict=True)
