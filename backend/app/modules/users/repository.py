from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.model import User
from app.repositories import BaseRepository


class UserRepository(BaseRepository[User]):

    model = User

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
    
    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()