from enum import StrEnum

class ErrorCode(StrEnum):
    """API レスポンスで返されるアプリケーションエラーコード。"""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"

class AppError(Exception):
    """ステータスコードとエラーコードを持つアプリケーション例外の基底クラス。"""

    def __init__(
        self,
        detail: str,
        status_code: int = 500,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
    ) -> None:
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(detail)


class NotFoundError(AppError):
    """リソースが見つからない。"""

    def __init__(self, detail: str = "Resource not found") -> None:
        super().__init__(detail=detail, status_code=404, error_code=ErrorCode.NOT_FOUND)


class UnauthorizedError(AppError):
    """認証が必要、または認証に失敗した。"""

    def __init__(self, detail: str = "Not authenticated") -> None:
        super().__init__(detail=detail, status_code=401, error_code=ErrorCode.UNAUTHORIZED)


class ForbiddenError(AppError):
    """権限が不足している。"""

    def __init__(self, detail: str = "Forbidden") -> None:
        super().__init__(detail=detail, status_code=403, error_code=ErrorCode.FORBIDDEN)


class ConflictError(AppError):
    """リソースの衝突 (例: 重複)。"""

    def __init__(self, detail: str = "Resource conflict") -> None:
        super().__init__(detail=detail, status_code=409, error_code=ErrorCode.CONFLICT)


class RateLimitedError(AppError):
    """このクライアントからのリクエストが多すぎる。"""

    def __init__(self, detail: str = "Too many requests. Please try again later.") -> None:
        super().__init__(detail=detail, status_code=429, error_code=ErrorCode.RATE_LIMITED)