from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from app.core.errors import UnauthorizedError
from app.core.rate_limit import auth_rate_limiter
from app.modules.auth.cookies import (
    REFRESH_COOKIE_NAME, clear_refresh_cookie, set_refresh_cookie,
)
from app.modules.auth.dependencies import AuthServiceDep, CurrentUserDep
from app.modules.auth.schemas import AccessTokenResponse, LoginRequest, RegisterRequest
from app.modules.users.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _check_rate_limit(request: Request) -> None:
    auth_rate_limiter.check(request)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_check_rate_limit)],
)
async def register(payload: RegisterRequest, auth: AuthServiceDep) -> UserResponse:
    user = await auth.register(payload)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=AccessTokenResponse,
    dependencies=[Depends(_check_rate_limit)],
)
async def login(
    payload: LoginRequest, auth: AuthServiceDep, response: Response,
) -> AccessTokenResponse:
    _, access_token, refresh_token = await auth.login(payload)
    set_refresh_cookie(response, refresh_token)
    return AccessTokenResponse(access_token=access_token)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    auth: AuthServiceDep, response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> AccessTokenResponse:
    if not refresh_token:
        raise UnauthorizedError("Missing refresh token")
    access_token, new_refresh_token = await auth.refresh(refresh_token)
    set_refresh_cookie(response, new_refresh_token)
    return AccessTokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response, auth: AuthServiceDep,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> Response:
    if refresh_token:
        await auth.revoke_refresh_token(refresh_token, reason="logout")
    clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUserDep) -> UserResponse:
    return UserResponse.model_validate(current_user)