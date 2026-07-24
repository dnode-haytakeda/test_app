from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import jwt

from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import (
    check_needs_rehash,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.users.model import User
from app.services import BaseService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.auth.repository import RefreshTokenDenylistRepository
    from app.modules.auth.schemas import LoginRequest, RegisterRequest
    from app.modules.users.repository import UserRepository


class AuthService(BaseService):

    def __init__(
            self,
            session: AsyncSession,
            users: UserRepository,
            denylist: RefreshTokenDenylistRepository,
            ) -> None:
        super().__init__(session)
        self._users = users
        self._denylist = denylist

    async def register(self, data: RegisterRequest) -> User:
        email = data.email.lower()
        existing = await self._users.get_by_email(email)
        if existing is not None:
            raise ConflictError("Could not create user")

        user = User(
            email=email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            is_active=True,
        )
        return await self._users.create(user)
    
    async def login(self, data: LoginRequest) -> tuple[User, str, str]:
        user = await self._users.get_by_email(data.email.lower())

        dummy_hash = (
            "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQAAAAAAAAAAA$RdescudvJCsgt3ub+b+dWRWJTmaaJObG"
        )
        is_valid = verify_password(
            data.password,
            user.hashed_password if user is not None else dummy_hash,
        )
        if user is None or not is_valid or not user.is_active:
            raise UnauthorizedError("Invalid credentials")
        
        if check_needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(data.password)
            await self._users.update(user)
        
        access, refresh = self._issue_tokens(user)
        self._logger.info("User logged in", user_id=str(user.id))
        return user, access, refresh
    
    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        payload = self._decode_refresh(refresh_token)
        user_id, jti, expires_at = self._parse_refresh_claims(payload)
        
        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("Invalid refresh token")
        
        revoked = await self._denylist.revoke_if_active(
            jti=jti,
            user_id=user.id,
            expires_at=expires_at,
            reason="rotated"
        )
        if not revoked:
            raise UnauthorizedError("Invalid refresh token")
        
        return self._issue_tokens(user)
    
    async def revoke_refresh_token(self, refresh_token: str, *, reason: str = "logout") -> None:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
            user_id, jti, expires_at = self._parse_refresh_claims(payload)
        except (jwt.InvalidTokenError, UnauthorizedError):
            return
        
        user = await self._users.get_by_id(user_id)
        if user is None:
            return
        
        await self._denylist.revoke_if_active(
            jti=jti,
            user_id=user.id,
            expires_at=expires_at,
            reason=reason,
        )
    

    @staticmethod
    def _decode_refresh(refresh_token: str) -> dict[str, object]:
        try:
            return decode_token(refresh_token, expected_type="refresh")
        except jwt.InvalidTokenError as exc:
            raise UnauthorizedError("Invalid refresh token") from exc

    @staticmethod
    def _parse_refresh_claims(payload: dict[str, object]) -> tuple[uuid.UUID, str, datetime]:
        try:
            user_id = uuid.UUID(str(payload["sub"]))
            jti = str(payload["jti"])
            exp = payload["exp"]
        except (KeyError, ValueError) as exc:
            raise UnauthorizedError("Invalid refresh token") from exc
        
        if not jti:
            raise UnauthorizedError("Invalid refresh token")
        if isinstance(exp, int | float):
            expires_at = datetime.fromtimestamp(exp, UTC)
        elif isinstance(exp, datetime):
            expires_at = exp if exp.tzinfo is not None else exp.replace(tzinfo=UTC)
        else:
            raise UnauthorizedError("Invalid refresh token")
        return user_id, jti, expires_at

    @staticmethod
    def _issue_tokens(user: User) -> tuple[str, str]:
        return (
            create_access_token(subject=str(user.id)),
            create_refresh_token(subject=str(user.id)),
        )