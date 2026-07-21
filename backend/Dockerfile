# ==============================================================================
# Multi-stage Dockerfile
#   - development: docker-compose 用（volume mount + --reload 前提）
#   - production:  本番デプロイ用（非 root, ヘルスチェック付き）
# ==============================================================================

# ---- base: 共通の依存インストール ----
FROM python:3.12-slim AS base
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ---- development (docker-compose のデフォルト) ----
FROM base AS development
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---- production ----
FROM base AS production

# セキュリティ: 非 root ユーザーで実行
RUN groupadd --system app && useradd --system --gid app --no-create-home app

COPY ./app ./app
COPY ./migrations ./migrations
COPY ./alembic.ini ./

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/live')"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]