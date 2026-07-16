import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.models.base import Base


class BaseRepository[ModelT: Base]:
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    async def get_by_id(self, entity_id: uuid.UUID) -> ModelT | None:
        return await self._session.get(self.model, entity_id)
    
    async def list_all(
            self, 
            *,
            limit: int = 50,
            offset: int = 0,
            order_by: Any | None = None,
    ) -> Sequence[ModelT]:
        stmt = select(self.model)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        elif hasattr(self.model, "created_at"):
            stmt = stmt.order_by(self.model.created_at.desc())
        else:
            stmt = stmt.order_by(self.model.id)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()
    
    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())
    
    async def create(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(f"Could not create {self.model.__name__}") from exc
        await self._session.refresh(entity)
        return entity
    
    async def update(self, entity: ModelT) -> ModelT:
        """エンティティを更新する。``id`` ベースで識別する。"""
        self._session.add(entity)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(f"Could not update {self.model.__name__}") from exc
        await self._session.refresh(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        """エンティティを削除する。"""
        await self._session.delete(entity)
        await self._session.flush()

    async def delete_by_id(self, entity_id: uuid.UUID) -> int:
        """主キーで削除し、削除した行数を返す (0 または 1)。"""
        entity = await self.get_by_id(entity_id)
        if entity is None:
            return 0
        await self.delete(entity)
        return 1
