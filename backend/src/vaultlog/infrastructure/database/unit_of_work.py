from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vaultlog.application.ports.tenant_context import TenantContext


class SqlAlchemyUnitOfWork:
    """One transaction per use case, with tenant context pinned via SET LOCAL.

    SET LOCAL scopes the GUC to the current transaction, so tenant context
    cannot leak between requests sharing a pooled connection.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_context: TenantContext,
    ) -> None:
        self._session_factory = session_factory
        self._tenant_context = tenant_context

    async def __aenter__(self) -> Self:
        self.session: AsyncSession = self._session_factory()
        await self.session.begin()
        await self.session.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": str(self._tenant_context.tenant_id)},
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                await self.session.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
