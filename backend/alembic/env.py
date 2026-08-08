from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from alembic.script import ScriptDirectory
from scripts.rls.apply import apply_rls_policies, is_upgrade_revision
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from vaultlog.infrastructure.database import (
    identity_models,  # noqa: F401 — registers tables
    models,  # noqa: F401 — registers tables
)
from vaultlog.infrastructure.database.base import Base
from vaultlog.shared.config import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.migration_database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    migration_context = context.get_context()
    start_rev = migration_context.get_current_revision()
    script_dir = ScriptDirectory.from_config(config)

    with context.begin_transaction():
        context.run_migrations()
        end_rev = migration_context.get_current_revision()
        if is_upgrade_revision(script_dir, start_rev, end_rev):
            apply_rls_policies(connection, strict=False)


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
