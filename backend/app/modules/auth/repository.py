from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.model import RevokedRefreshToken
from app.repositories import BaseRepository

_CLEANUP_INTERVAL_SECONDS = 300.0
_last_cleanup_monotonic = 0.0


class RefreshTokenDenylistRepository(BaseRepository[RevokedRefreshToken]):

    model = RevokedRefreshToken

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
    
    async def revoke_if_ative(
            self,
            *,
            jti: str,
            user_id: uuid.UUID,
            expires_at: datetime,
            reason: str,
    ) -> bool:
        await self._purge_expired_periodically()
        stmt = (
            pg_insert(RevokedRefreshToken)
            .values(
                id=uuid.uuid4(),
                jti=jti,
                user_id=user_id,
                expires_at=expires_at,
                reason=reason,
            )
            .on_conflict_do_nothing(index_elements=["jti"])
        )
        result = cast(CursorResult[object], await self._session.execute(stmt))
        await self._session.flush()
        return (result.rowcount or 0) == 1
    
    async def purge_expired(self, *, now: datetime | None = None) -> int:
        cutoff = now if now is not None else datetime.now(UTC)
        stmt = delete(RevokedRefreshToken).where(RevokedRefreshToken.expires_at <= cutoff)
        result = cast(CursorResult[object], await self._session.execute(stmt))
        await self._session.flush()
        return int(result.rowcount or 0)
    
    async def _purge_expired_periodically(self) -> int:
        """プロセスごとに一定間隔で期限切れ denylist を軽く掃除する。"""
        global _last_cleanup_monotonic
        now = time.monotonic()
        if now - _last_cleanup_monotonic < _CLEANUP_INTERVAL_SECONDS:
            return 0
        _last_cleanup_monotonic = now
        return await self.purge_expired()