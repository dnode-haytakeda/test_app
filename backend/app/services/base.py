from __future__ import annotations

from collections.abc import AsyncIterable
from contextlib import asynccontextmanager

import structlog
from sqlalchemy.ext.asyncio import AsyncSession


class BaseService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._logger = structlog.get_logger().bind(service=type(self).__name__)

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterable[None]:
        async with self._session.begin_nested():
            yield