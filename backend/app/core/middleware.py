import time
import uuid

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """リクエストごとに一意な ID を割り当て、ログとレスポンスヘッダーに伝搬する。

    クライアントが ``X-Request-ID`` を送信すればそれを採用し、
    なければ UUID v4 を自動生成する。
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            structlog.contextvars.unbind_contextvars("request_id")


class AccessLoggingMiddleware(BaseHTTPMiddleware):
    """全リクエストの構造化アクセスログを出力する。

    記録項目: HTTP メソッド、パス、ステータスコード、レスポンス時間(ms)。
    ヘルスチェック等の高頻度エンドポイントはノイズ低減のため除外する。
    """

    _SKIP_PATHS = frozenset({"/api/health/live", "/api/health", "/metrics"})

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self._SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        log = logger.info if response.status_code < 400 else logger.warning
        log(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            client=request.client.host if request.client else None,
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """セキュリティ関連のレスポンスヘッダーを全レスポンスに付与する。"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response
