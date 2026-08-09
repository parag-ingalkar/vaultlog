from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from vaultlog.shared.config import get_settings

logger = logging.getLogger(__name__)

RLS_DIR = Path(__file__).resolve().parent
POLICIES_DIR = RLS_DIR / "policies"

# Tenant-owned tables that must have a matching policy file. Update when adding tables.
TENANT_TABLES = frozenset(
    {
        "organization",
        "vault",
        "vault_grant",
        "membership",
        "secret",
        "secret_version",
        "tenant_key_version",
        "audit_event",
        "audit_chain_head",
    }
)


def _split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    for part in sql.split(";"):
        stmt = part.strip()
        if stmt:
            statements.append(stmt)
    return statements


def _policy_files() -> list[Path]:
    return sorted(path for path in POLICIES_DIR.glob("*.sql") if not path.name.startswith("_"))


def is_upgrade_revision(
    script_dir: ScriptDirectory,
    start_rev: str | None,
    end_rev: str | None,
) -> bool:
    """Return True when end_rev is a descendant of start_rev (schema moved forward)."""
    if start_rev == end_rev:
        return False
    if end_rev is None:
        return False
    if start_rev is None:
        return True

    rev = script_dir.get_revision(end_rev)
    seen: set[str] = set()
    while rev is not None:
        if rev.revision == start_rev:
            return True
        if rev.revision in seen:
            break
        seen.add(rev.revision)

        down = rev.down_revision
        if down is None:
            break
        if isinstance(down, tuple):
            return any(is_upgrade_revision(script_dir, start_rev, parent) for parent in down)
        rev = script_dir.get_revision(down)

    return False


def apply_rls_policies(connection: Connection, *, strict: bool = False) -> None:
    """Apply every idempotent policy script in policies/ on the given connection.

      When strict is False (Alembic hook), skip policy files whose table does not exist
    and log a warning. When strict is True (standalone CLI), fail on missing tables.
    """
    for path in _policy_files():
        table = path.stem
        exists = connection.execute(
            text("SELECT to_regclass(:qualified_name) IS NOT NULL"),
            {"qualified_name": f"public.{table}"},
        ).scalar()
        if not exists:
            message = f"RLS policy script {path.name} targets missing table {table}; skipping"
            if strict:
                raise RuntimeError(message.replace("; skipping", ""))
            logger.warning(message)
            continue

        sql = path.read_text(encoding="utf-8")
        for statement in _split_sql_statements(sql):
            connection.execute(text(statement))

        logger.info("Applied RLS policy for table %s", table)


def policy_table_names() -> frozenset[str]:
    return frozenset(path.stem for path in _policy_files())


async def _run_standalone() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.migration_database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(lambda connection: apply_rls_policies(connection, strict=True))
    await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run_standalone())


if __name__ == "__main__":
    main()
