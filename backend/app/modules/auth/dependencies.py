import uuid
from typing import Annotated

import jwt
import structlog
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import UnauthorizedError
from app.core.security import decode_token
from app.modules.auth.repository import RefreshTokenDenylistRepository
from app.modules.auth.service import AuthService
from app.modules.users.model import User
from app.modules.users.repository import UserRepository
from app.shared.dependencies import SessionDep

logger = structlog.get_logger()

bearer_schema = HTTPBearer(auto_error=False)


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


userRepoDep = Annotated[UserRepository, Depends(get_user_repository)]


def get_refresh_token_denylist_repository(session: SessionDep) -> RefreshTokenDenylistRepository:
    return RefreshTokenDenylistRepository(session)


RefreshTokenDenylistDep = Annotated[
    RefreshTokenDenylistRepository,
    Depends(get_refresh_token_denylist_repository),
]


def get_auth_service(
        session: SessionDep,
        users: userRepoDep,
        denylist: RefreshTokenDenylistDep,
) -> AuthService:
    return AuthService(session, users, denylist)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_schema)],
        users: userRepoDep,
) -> User:
    if credentials is None:
        raise UnauthorizedError("Not authenticated")
    
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except jwt.InvalidTokenError as exc:
        logger.warning("Invalid access token", error=str(exc))
        raise UnauthorizedError("Invalid or expires token") from exc
    
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Invalid or expired token") from exc
    
    user = await users.get_by_id(user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expires token")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]