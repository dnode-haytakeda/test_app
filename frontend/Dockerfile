# ==============================================================================
# Multi-stage Dockerfile
#   - development: docker-compose 用（volume mount + HMR 前提）
#   - build:       CI / production artifact 生成用
#   - production:  nginx で静的ファイル配信
# ==============================================================================

# ---- deps: 依存パッケージインストール ----
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- development (docker-compose のデフォルト) ----
FROM node:20-alpine AS development
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

# ---- build: 静的ファイル生成 ----
FROM deps AS build
WORKDIR /app
COPY . .
RUN npm run build

# ---- production: nginx で配信 ----
FROM nginx:1.27-alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html

# セキュリティ: 非 root ユーザーで実行
RUN addgroup -S app && adduser -S app -G app \
    && chown -R app:app /usr/share/nginx/html \
    && chown -R app:app /var/cache/nginx \
    && touch /var/run/nginx.pid && chown app:app /var/run/nginx.pid

USER app
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
