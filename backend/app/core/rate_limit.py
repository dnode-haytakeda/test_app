import time
from collections import defaultdict

from fastapi import Request

from app.core.errors import RateLimitedError


class RateLimiter:
    """インメモリ・スライディングウィンドウ方式のレートリミッター。

    同一クライアント IP から ``window_seconds`` 秒間に ``max_requests`` 回を
    超えるリクエストがあった場合、``RateLimitedError`` (HTTP 429) を送出する。

    Note:
        単一プロセス／単一インスタンス用。複数ワーカーや複数コンテナで
        正確な制限をかけるには Redis ベースの実装に置き換える。
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_global_cleanup: float = 0.0

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup_stale_keys(self, now: float) -> None:
        """一定間隔で全エントリを走査し、期限切れの IP を削除する。

        check() は該当 IP のエントリしか掃除しないため、
        リクエストが来なくなった IP のエントリがメモリに残り続ける。
        これを防ぐために定期的にグローバルクリーンアップを行う。
        """
        if now - self._last_global_cleanup < self.window_seconds * 2:
            return
        self._last_global_cleanup = now
        stale = [
            key
            for key, timestamps in self._requests.items()
            if all(now - t >= self.window_seconds for t in timestamps)
        ]
        for key in stale:
            del self._requests[key]

    def check(self, request: Request) -> None:
        key = self._client_key(request)
        now = time.monotonic()

        self._cleanup_stale_keys(now)

        window = self._requests[key]
        # ウィンドウ外のタイムスタンプを除去
        self._requests[key] = [t for t in window if now - t < self.window_seconds]

        if len(self._requests[key]) >= self.max_requests:
            raise RateLimitedError()

        self._requests[key].append(now)


# 認証エンドポイント用: 60 秒間に 10 回まで
auth_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
