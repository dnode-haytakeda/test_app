from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncIterable

    from sqlalchemy.ext.asyncio import AsyncSession


class BaseService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._logger = structlog.get_logger().bind(service=type(self).__name__)

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterable[None]:
        async with self._session.begin_nested():
            yield