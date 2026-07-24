from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.errors import AppError, ErrorCode
from app.core.logging import setup_logging
from app.core.middleware import (
    AccessLoggingMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.version import APP_VERSION
from app.schemas.common import ErrorResponse

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging(log_level=settings.LOG_LEVEL, app_env=settings.APP_ENV)
    logger.info("Application starting", version=APP_VERSION, env=settings.APP_ENV)
    yield
    await engine.dispose()
    logger.info("Application shut down")


app = FastAPI(
    title="my-app",
    version=APP_VERSION,
    description="フルスタック Web アプリケーション",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)


# ---------- Middleware ----------
# Starlette/FastAPI ではミドルウェアは add_middleware の逆順で実行される。
# 最後に追加されたものが最も外側（リクエストを最初に受け取る）になる。
#
# リクエスト処理順:
#   TrustedHost → SecurityHeaders → RequestID → AccessLogging → GZip → CORS → Route
#
# レスポンス処理順:
#   Route → CORS → GZip → AccessLogging → RequestID → SecurityHeaders → TrustedHost

# (1) CORS — プリフライトリクエストの処理
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

# (2) GZip — レスポンス圧縮（1KB 以上のレスポンスを自動圧縮）
app.add_middleware(GZipMiddleware, minimum_size=1000)

# (3) アクセスログ — 全リクエストの構造化ログ
# RequestID の内側で実行されるため request_id が利用可能
app.add_middleware(AccessLoggingMiddleware)

# (4) Request ID — リクエスト追跡用の一意 ID を生成・伝搬
app.add_middleware(RequestIDMiddleware)

# (5) セキュリティヘッダー — 全レスポンスにセキュリティヘッダーを付与
app.add_middleware(SecurityHeadersMiddleware)

# (6) Trusted Host — Host ヘッダーインジェクション攻撃の防御（本番のみ）
if settings.TRUSTED_HOSTS:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.TRUSTED_HOSTS,
    )


# ---------- Prometheus Metrics ----------
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/api/health/live", "/api/health", "/metrics"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


# ---------- Exception Handlers ----------

@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            detail="Validation error",
            error_code=ErrorCode.VALIDATION_ERROR,
        ).model_dump(),
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(detail=exc.detail, error_code=exc.error_code).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception", path=request.url.path)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            detail="Internal server error",
            error_code=ErrorCode.INTERNAL_ERROR,
        ).model_dump(),
    )


app.include_router(api_router)

