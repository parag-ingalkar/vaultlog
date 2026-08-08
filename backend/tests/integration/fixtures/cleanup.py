"""Truncate all user tables in the public schema."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def truncate_all_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        tables = [row[0] for row in result.all() if row[0] != "alembic_version"]
        if not tables:
            return
        quoted = ", ".join(f'"{table}"' for table in tables)
        await conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
