# タスク1: アプリケーション品質改善レポート

## 概要

プロのエンジニアの視点から、バックエンド(FastAPI + SQLAlchemy)とフロントエンド(React + Vite)の全コードを網羅的に評価し、セキュリティ、可観測性、堅牢性、保守性の観点で修正を実施しました。

---

## 1. セキュリティに関する問題

### 1.1 CORS（Cross-Origin Resource Sharing）未設定 ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | FastAPI アプリに CORS ミドルウェアが一切設定されていなかった |
| **なぜ不十分か** | 本番環境でフロントエンド（異なるオリジン）からの API リクエストがブラウザにブロックされる。開発環境では Vite のプロキシで隠れているが、本番デプロイ時に即座に障害となる。CORS はブラウザの**同一オリジンポリシー**を制御するための必須設定であり、これを忘れると「開発環境では動くが本番では動かない」という典型的な問題を引き起こす |
| **どう修正したか** | `app/main.py` に `CORSMiddleware` を追加。`settings.CORS_ORIGINS` で許可するオリジンを設定可能にした。`allow_credentials=True`（Cookie 送信に必要）、メソッド・ヘッダーも適切に制限 |

**修正ファイル**: `backend/app/main.py`, `backend/app/core/config.py`

### 1.2 セキュリティヘッダー未設定 ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | HTTP レスポンスにセキュリティヘッダーが一切付与されていなかった |
| **なぜ不十分か** | クリックジャッキング（`X-Frame-Options`）、MIME タイプスニッフィング（`X-Content-Type-Options`）、リファラー漏洩（`Referrer-Policy`）、HTTPS ダウングレード攻撃（`Strict-Transport-Security`）など、基本的な Web 攻撃に対する防御が皆無だった。OWASP Top 10 の「Security Misconfiguration」に該当 |
| **どう修正したか** | `SecurityHeadersMiddleware` を追加し、全レスポンスに以下を付与:<br>- `X-Content-Type-Options: nosniff`<br>- `X-Frame-Options: DENY`<br>- `Referrer-Policy: strict-origin-when-cross-origin`<br>- 本番環境のみ `Strict-Transport-Security`（HSTS） |

**修正ファイル**: `backend/app/main.py`

### 1.3 Cookie の `secure` フラグ未設定 ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | Refresh Token Cookie に `secure=True` が設定されていなかった |
| **なぜ不十分か** | `secure` フラグがないと、HTTP（暗号化されていない通信）でも Cookie が送信されてしまう。中間者攻撃（MITM）で Refresh Token が盗聴されるリスクがある。一方、開発環境では HTTP を使うため、常に `secure=True` にすると開発が困難になる |
| **どう修正したか** | `settings.is_production` プロパティを追加し、本番環境（`APP_ENV=production`）のときだけ `secure=True` にする条件分岐を実装 |

**修正ファイル**: `backend/app/modules/auth/cookies.py`, `backend/app/core/config.py`

---

## 2. 可観測性（Observability）に関する問題

### 2.1 ログ初期化が呼び出されていない ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `setup_logging()` が定義されているのに、アプリケーション起動時に一度も呼び出されていなかった |
| **なぜ不十分か** | structlog のプロセッサーチェーン（タイムスタンプ、ログレベル、機密情報マスク、トレースID注入など）が一切適用されない。つまり、本番環境で JSON 構造化ログが出力されず、機密情報のマスクも行われない。障害調査が極めて困難になる |
| **どう修正したか** | FastAPI の `lifespan` イベントハンドラーを追加し、起動時に `setup_logging()` を呼び出すようにした |

**修正ファイル**: `backend/app/main.py`

### 2.2 Request ID（リクエスト追跡）がない ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | リクエストごとの一意な識別子がログにもレスポンスにも含まれていなかった |
| **なぜ不十分か** | 本番環境で障害が発生した際、「どのリクエストでエラーが起きたか」を特定できない。マイクロサービスやフロントエンドとの連携で、リクエストの追跡（トレーシング）は必須のプラクティスである |
| **どう修正したか** | `RequestIDMiddleware` を追加。クライアントが `X-Request-ID` ヘッダーを送信すればそれを使用し、なければ UUID を自動生成。structlog の contextvars にバインドしてログに自動出力し、レスポンスヘッダーにも付与 |

**修正ファイル**: `backend/app/main.py`

### 2.3 未ハンドル例外でログ出力がない ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `unhandled_exception_handler` で例外をキャッチしているが、ログに出力していなかった |
| **なぜ不十分か** | 500 エラーが発生しても、スタックトレースがどこにも記録されない。原因調査が不可能 |
| **どう修正したか** | `logger.exception()` を追加し、スタックトレースとリクエストパスをログに記録 |

**修正ファイル**: `backend/app/main.py`

---

## 3. アプリケーション設計の問題

### 3.1 Lifespan（ライフサイクル管理）の欠如 ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | FastAPI の lifespan（起動・終了処理）が定義されていなかった |
| **なぜ不十分か** | データベースエンジンのコネクションプールが、アプリケーション終了時に適切に破棄（`dispose`）されない。これにより、コネクションリークやグレースフルシャットダウンの失敗が起きる。プロのアプリケーションでは「起動時の初期化」と「終了時のクリーンアップ」はセットで実装する |
| **どう修正したか** | `@asynccontextmanager` で `lifespan` 関数を定義。起動時にログ初期化、終了時にエンジン `dispose()` を実行 |

**修正ファイル**: `backend/app/main.py`

### 3.2 FastAPI のパラメータ名が間違っている ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `FastAPI(service_version=APP_VERSION)` と記述されていた |
| **なぜ不十分か** | FastAPI の正しいパラメータ名は `version`。`service_version` は認識されないため、OpenAPI スキーマにバージョン情報が含まれない |
| **どう修正したか** | `version=APP_VERSION` に修正 |

**修正ファイル**: `backend/app/main.py`

### 3.3 本番環境での API ドキュメント公開 ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `/docs`（Swagger UI）と `/redoc` が常に公開されていた |
| **なぜ不十分か** | 本番環境で API ドキュメントが公開されていると、攻撃者にエンドポイント情報を与えてしまう。情報漏洩のリスク |
| **どう修正したか** | `settings.is_production` が `True` の場合、`docs_url=None, redoc_url=None` にしてドキュメントを無効化 |

**修正ファイル**: `backend/app/main.py`

### 3.4 バリデーションエラーのレスポンス形式が不統一 ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | FastAPI デフォルトの `RequestValidationError` がアプリ独自の `ErrorResponse` 形式に統一されていなかった |
| **なぜ不十分か** | 422 エラーだけ他のエラー（401、404、409 など）と異なる JSON 構造で返却されてしまう。フロントエンドのエラーハンドリングが複雑化する |
| **どう修正したか** | `RequestValidationError` 用のハンドラーを追加し、`ErrorResponse` 形式で統一 |

**修正ファイル**: `backend/app/main.py`

### 3.5 MetaData の命名規約（Naming Convention）未設定 ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | SQLAlchemy の `Base` クラスに `MetaData` の命名規約が設定されていなかった |
| **なぜ不十分か** | Alembic がマイグレーションを自動生成するとき、制約名（インデックス、外部キー、ユニーク制約など）がデータベースに依存したランダムな名前になる。ダウングレード時に制約を参照できず失敗するケースがある。命名規約を統一することで、マイグレーションの再現性と可搬性が保証される |
| **どう修正したか** | `MetaData(naming_convention=convention)` を設定。主キー (`pk_`)、外部キー (`fk_`)、ユニーク制約 (`uq_`)、チェック制約 (`ck_`)、インデックス (`ix_`) に一貫した命名パターンを適用 |

**修正ファイル**: `backend/app/models/base.py`

### 3.6 `pool_timeout` 設定が未使用 ★☆☆ 軽微

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `DATABASE_POOL_TIMEOUT` の設定値が定義されているが、`create_async_engine` に渡されていなかった |
| **なぜ不十分か** | 設定を定義しても使わなければ意味がない。また、デフォルト値が `5` 秒と短すぎたため、`30` 秒に変更 |
| **どう修正したか** | `create_async_engine` に `pool_timeout` パラメータを追加。デフォルト値を `30` 秒に変更 |

**修正ファイル**: `backend/app/core/database.py`, `backend/app/core/config.py`

### 3.7 `POSTGRES_SSL` 設定が未使用 ★☆☆ 軽微

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `POSTGRES_SSL` 設定が定義されているのに、データベース URL に反映されていなかった |
| **なぜ不十分か** | AWS RDS 等で SSL 接続を強制する場合に使えない |
| **どう修正したか** | `POSTGRES_SSL=True` のとき、接続 URL にクエリパラメータ `ssl=require` を追加するよう修正 |

**修正ファイル**: `backend/app/core/config.py`

### 3.8 Liveness エンドポイントの未実装 ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `LivenessResponse` スキーマが定義されているのに、対応するエンドポイントがなかった |
| **なぜ不十分か** | Kubernetes/ECS 等のコンテナオーケストレーションでは、**Liveness Probe**（アプリが生きているか）と **Readiness Probe**（リクエストを受け付けられるか）を分離するのがベストプラクティス。Liveness は DB 接続不要で即座に応答すべきもの |
| **どう修正したか** | `/api/health/live` エンドポイントを追加。データベースチェックなしで即座に `{"status":"ok"}` を返す |

**修正ファイル**: `backend/app/api/health.py`

---

## 4. コード品質・バグ

### 4.1 タイポ: `FieldError.filed` → `field` ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `schemas/common.py` の `FieldError` モデルで `filed` と誤記されていた |
| **なぜ不十分か** | フロントエンドが `field` を期待して API エラーを解析するため、フィールドエラー情報が正しくマッピングされない |
| **どう修正したか** | `filed` → `field` に修正 |

**修正ファイル**: `backend/app/schemas/common.py`

### 4.2 タイポ: エラーメッセージの不整合 ★☆☆ 軽微

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `auth/dependencies.py` で `"Invalid or expires token"` と `"Invalid or expired token"` が混在していた |
| **なぜ不十分か** | 同じ意味のエラーメッセージが一貫していないと、フロントエンドのエラーハンドリングやログ検索で混乱を招く |
| **どう修正したか** | 全て `"Invalid or expired token"` に統一 |

**修正ファイル**: `backend/app/modules/auth/dependencies.py`

### 4.3 タイポ: `font-semibodl` → `font-semibold`（フロントエンド）★☆☆ 軽微

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `LoginPage.tsx` で Tailwind CSS のクラス名が `font-semibodl` と誤記されていた |
| **なぜ不十分か** | Tailwind CSS はクラス名を正確に記述しないとスタイルが適用されない。ログインページの見出しが通常のフォントウェイトのままになっていた |
| **どう修正したか** | `font-semibold` に修正 |

**修正ファイル**: `frontend/src/features/auth/pages/LoginPage.tsx`

### 4.4 未使用 import: `useEffectEvent`（フロントエンド）★☆☆ 軽微

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `AuthProvider.tsx` で `useEffectEvent` がインポートされているが使用されていなかった |
| **なぜ不十分か** | 未使用の import はバンドルサイズに影響はないが、コードの可読性を下げ、ESLint 警告の原因にもなる |
| **どう修正したか** | import 文から削除 |

**修正ファイル**: `frontend/src/features/auth/AuthProvider.tsx`

### 4.5 存在しないルートへのリンク（フロントエンド）★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `HomePage.tsx` に `/posts` へのリンクがあるが、ルーティングに `/posts` が定義されていない |
| **なぜ不十分か** | ユーザーがクリックすると 404 ページに遷移してしまう |
| **どう修正したか** | 未実装のリンクを削除。合わせて未使用の `Link` import も削除 |

**修正ファイル**: `frontend/src/features/home/pages/HomePage.tsx`

---

## 5. 依存関係管理

### 5.1 本番用と開発用の依存関係が混在 ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `requirements.txt` に `ruff`, `mypy`, `pytest` 等の開発ツールが含まれていた |
| **なぜ不十分か** | 本番の Docker イメージに不要なツールがインストールされ、イメージサイズが肥大化し、攻撃面が広がる。プロの現場では本番用と開発用の依存関係を厳密に分離する |
| **どう修正したか** | `requirements.txt` を本番用のみに整理し、`requirements-dev.txt` を新設。開発ツールはそちらに移動 |

**修正ファイル**: `backend/requirements.txt`（修正）, `backend/requirements-dev.txt`（新規）

---

## 修正一覧（サマリー）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 1 | ★★★ | セキュリティ | CORS ミドルウェア追加 | `main.py`, `config.py` |
| 2 | ★★★ | セキュリティ | セキュリティヘッダーミドルウェア追加 | `main.py` |
| 3 | ★★☆ | セキュリティ | Cookie `secure` フラグ条件付与 | `cookies.py`, `config.py` |
| 4 | ★★★ | 可観測性 | ログ初期化の呼び出し追加 | `main.py` |
| 5 | ★★☆ | 可観測性 | Request ID ミドルウェア追加 | `main.py` |
| 6 | ★★☆ | 可観測性 | 未ハンドル例外のログ出力追加 | `main.py` |
| 7 | ★★★ | 設計 | Lifespan（起動・終了処理）追加 | `main.py` |
| 8 | ★★☆ | 設計 | `service_version` → `version` 修正 | `main.py` |
| 9 | ★★☆ | セキュリティ | 本番環境での API ドキュメント非公開 | `main.py` |
| 10 | ★★☆ | 設計 | バリデーションエラー形式の統一 | `main.py` |
| 11 | ★★☆ | 設計 | MetaData 命名規約の設定 | `base.py` |
| 12 | ★☆☆ | 設計 | `pool_timeout` 設定の適用 | `database.py`, `config.py` |
| 13 | ★☆☆ | 設計 | `POSTGRES_SSL` 設定の適用 | `config.py` |
| 14 | ★★☆ | 設計 | Liveness エンドポイント追加 | `health.py` |
| 15 | ★★☆ | バグ | `filed` → `field` タイポ修正 | `common.py` |
| 16 | ★☆☆ | バグ | エラーメッセージの統一 | `dependencies.py` |
| 17 | ★☆☆ | バグ | `font-semibodl` → `font-semibold` | `LoginPage.tsx` |
| 18 | ★☆☆ | 品質 | 未使用 import 削除 | `AuthProvider.tsx` |
| 19 | ★★☆ | バグ | 存在しないルートへのリンク削除 | `HomePage.tsx` |
| 20 | ★★☆ | 依存関係 | 本番/開発依存関係の分離 | `requirements.txt`, `requirements-dev.txt` |
| 21 | ★★☆ | バグ | `revoke_if_ative` → `revoke_if_active` タイポ修正 | `repository.py`, `service.py` |
| 22 | ★☆☆ | 品質 | デッドコード `_client_key` 削除 | `auth/router.py` |
| 23 | ★★☆ | 規約 | `userRepoDep` → `UserRepoDep` PEP 8 命名規約準拠 | `dependencies.py` |
| 24 | ★★☆ | 規約 | `main.py` import 順序を PEP 8 準拠に修正 | `main.py` |
| 25 | ★★☆ | セキュリティ | `clear_refresh_cookie` に `secure`/`samesite` 追加 | `cookies.py` |
| 26 | ★☆☆ | 品質 | `_encode_token` の死コード除去（PyJWT v2+ 対応） | `security.py` |
| 27 | ★☆☆ | 品質 | `config.py`/`database.py` 未使用 import 削除 | `config.py`, `database.py` |
| 28 | ★☆☆ | 品質 | `auth/router.py` 未使用 `request` パラメータ削除 | `auth/router.py` |

---

## 6. フロントエンド TypeScript 設定の問題

### 6.1 `tsconfig.json` が Project References 形式でない ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | ルートの `tsconfig.json` が独立した `compilerOptions` と `include` を持つ旧来の単一設定ファイルだった。`tsconfig.app.json` と `tsconfig.node.json` が存在するにもかかわらず、VS Code の TypeScript Language Server はルートの `tsconfig.json` を優先して使用していた |
| **なぜ不十分か** | Vite + TypeScript プロジェクトのデファクトスタンダードは **Project References** 形式である。ルート `tsconfig.json` は `"files": []` + `"references"` のみを持ち、実際のコンパイラ設定は `tsconfig.app.json`（アプリコード用）と `tsconfig.node.json`（設定ファイル用）に分離する。旧構成では:<br>1. ルート設定に `"types": ["vitest/globals"]` しかなく `"vite/client"` が欠落 → `import.meta.env` が型エラー<br>2. CSS import（`import "./index.css"`）の型宣言が無効 → エラー<br>3. `tsconfig.app.json` の設定（`strict` 等）が IDE に適用されない |
| **どう修正したか** | `tsconfig.json` を Vite 標準の Project References 形式に変換。`tsconfig.app.json` に旧ルート設定の `strict`、`noUncheckedIndexedAccess`、`noImplicitOverride`、`vitest/globals` を統合 |

**修正ファイル**: `frontend/tsconfig.json`, `frontend/tsconfig.app.json`

**修正前の `tsconfig.json`（問題あり）:**
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "strict": true,
    "types": ["vitest/globals"],
    ...
  },
  "include": ["src", "vite.config.ts"]
}
```

**修正後の `tsconfig.json`（Vite 標準）:**
```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

### 6.2 `src/vite-env.d.ts` が欠落 ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | Vite プロジェクトに標準で含まれるべき `src/vite-env.d.ts` が存在しなかった |
| **なぜ不十分か** | このファイルは `/// <reference types="vite/client" />` を含み、Vite 固有の型定義（`import.meta.env`、CSS モジュール、静的アセット import 等）を TypeScript に認識させる。Vite が `npm create vite@latest` で生成するテンプレートには必ず含まれるファイルであり、これがないと IDE 上で多数の型エラーが表示される |
| **どう修正したか** | `src/vite-env.d.ts` を作成し、Vite のクライアント型参照を追加 |

**修正ファイル**: `frontend/src/vite-env.d.ts`（新規作成）

### 6.3 `ApiError` がパラメータプロパティを使用 ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `shared/api/client.ts` の `ApiError` クラスが `constructor(public readonly status: number, ...)` というパラメータプロパティ構文を使用していた |
| **なぜ不十分か** | `tsconfig.app.json` で `erasableSyntaxOnly: true` が有効であるため、TypeScript コンパイルエラーとなる。`erasableSyntaxOnly` は Node.js の `--experimental-strip-types` や `tsx` 等の型除去ツールと互換性を保つための設定であり、モダン TypeScript プロジェクトで推奨されている。パラメータプロパティはランタイムに影響する構文であるため、この制約に抵触する |
| **どう修正したか** | パラメータプロパティを明示的なフィールド宣言 + constructor 内代入に書き換え |

**修正ファイル**: `frontend/src/shared/api/client.ts`

**修正前:**
```typescript
export class ApiError extends Error {
    constructor(
        public readonly status: number,
        public readonly code: string,
        public readonly requestId: string | null,
        message: string,
    ) { ... }
}
```

**修正後:**
```typescript
export class ApiError extends Error {
    readonly status: number;
    readonly code: string;
    readonly requestId: string | null;

    constructor(status: number, code: string, requestId: string | null, message: string) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.code = code;
        this.requestId = requestId;
    }
}
```

### 6.4 `ErrorBoundary` に `override` 修飾子が欠落 ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `ErrorBoundary.tsx` の `componentDidCatch` と `render` メソッドに `override` キーワードがなかった |
| **なぜ不十分か** | `noImplicitOverride: true`（`strict` に含まれる設定）が有効な場合、基底クラスのメソッドをオーバーライドする際に `override` キーワードが必須となる。これは「意図せず基底クラスのメソッドを上書きしてしまう」バグを防ぐ TypeScript の安全機構 |
| **どう修正したか** | `componentDidCatch` と `render` に `override` 修飾子を追加 |

**修正ファイル**: `frontend/src/app/ErrorBoundary.tsx`

---

## 修正一覧（全サマリー）

### バックエンド（20項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 1 | ★★★ | セキュリティ | CORS ミドルウェア追加 | `main.py`, `config.py` |
| 2 | ★★★ | セキュリティ | セキュリティヘッダーミドルウェア追加 | `main.py` |
| 3 | ★★☆ | セキュリティ | Cookie `secure` フラグ条件付与 | `cookies.py`, `config.py` |
| 4 | ★★☆ | セキュリティ | `clear_refresh_cookie` に `secure`/`samesite` 追加 | `cookies.py` |
| 5 | ★★★ | 可観測性 | ログ初期化の呼び出し追加 | `main.py` |
| 6 | ★★☆ | 可観測性 | Request ID ミドルウェア追加 | `main.py` |
| 7 | ★★☆ | 可観測性 | 未ハンドル例外のログ出力追加 | `main.py` |
| 8 | ★★★ | 設計 | Lifespan（起動・終了処理）追加 | `main.py` |
| 9 | ★★☆ | 設計 | `service_version` → `version` 修正 | `main.py` |
| 10 | ★★☆ | セキュリティ | 本番環境での API ドキュメント非公開 | `main.py` |
| 11 | ★★☆ | 設計 | バリデーションエラー形式の統一 | `main.py` |
| 12 | ★★☆ | 設計 | MetaData 命名規約の設定 | `base.py` |
| 13 | ★☆☆ | 設計 | `pool_timeout` 設定の適用 | `database.py`, `config.py` |
| 14 | ★☆☆ | 設計 | `POSTGRES_SSL` 設定の適用 | `config.py` |
| 15 | ★★☆ | 設計 | Liveness エンドポイント追加 | `health.py` |
| 16 | ★★☆ | バグ | `filed` → `field` タイポ修正 | `common.py` |
| 17 | ★★☆ | バグ | `revoke_if_ative` → `revoke_if_active` タイポ修正 | `repository.py`, `service.py` |
| 18 | ★☆☆ | バグ | エラーメッセージの統一 (`expires` → `expired`) | `dependencies.py` |
| 19 | ★★☆ | 規約 | `userRepoDep` → `UserRepoDep` PEP 8 命名規約 | `dependencies.py` |
| 20 | ★★☆ | 規約 | `main.py` import 順序を PEP 8 準拠に修正 | `main.py` |

### バックエンド — コード品質（4項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 21 | ★☆☆ | 品質 | デッドコード `_client_key` 削除 | `auth/router.py` |
| 22 | ★☆☆ | 品質 | `_encode_token` の死コード除去（PyJWT v2+） | `security.py` |
| 23 | ★☆☆ | 品質 | `config.py`/`database.py` 未使用 import 削除 | `config.py`, `database.py` |
| 24 | ★☆☆ | 品質 | `auth/router.py` 未使用 `request` パラメータ削除 | `auth/router.py` |

### バックエンド — 依存関係（1項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 25 | ★★☆ | 依存関係 | 本番/開発依存関係の分離 | `requirements.txt`, `requirements-dev.txt` |

### フロントエンド（7項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 26 | ★★★ | 設定 | `tsconfig.json` を Project References 形式に変換 | `tsconfig.json`, `tsconfig.app.json` |
| 27 | ★★☆ | 設定 | `src/vite-env.d.ts` 新規作成 | `vite-env.d.ts` |
| 28 | ★★☆ | 型安全性 | `ApiError` パラメータプロパティを明示的宣言に変換 | `client.ts` |
| 29 | ★★☆ | 型安全性 | `ErrorBoundary` に `override` 修飾子追加 | `ErrorBoundary.tsx` |
| 30 | ★☆☆ | バグ | `font-semibodl` → `font-semibold` タイポ修正 | `LoginPage.tsx` |
| 31 | ★☆☆ | 品質 | 未使用 import 削除（`useEffectEvent`, `Link`） | `AuthProvider.tsx`, `HomePage.tsx` |
| 32 | ★★☆ | バグ | 存在しない `/posts` ルートへのリンク削除 | `HomePage.tsx` |

---

## 7. ミドルウェア・アーキテクチャの問題

### 7.1 構造化アクセスログが存在しない ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | リクエストの HTTP メソッド、パス、ステータスコード、レスポンス時間を構造化ログで出力するミドルウェアがなかった |
| **なぜ不十分か** | 本番環境でのデバッグ・パフォーマンス分析・異常検知の基盤となるアクセスログは、あらゆる本番アプリケーションで**必須**のインフラストラクチャである。Uvicorn のデフォルトのアクセスログは非構造化テキストであり、JSON パース不可、`request_id` やクライアント IP との紐づけができない |
| **どう修正したか** | `AccessLoggingMiddleware` を作成。全リクエストに対して `method`, `path`, `status`, `duration_ms`, `client`, `request_id` を構造化ログで出力。ヘルスチェック・メトリクス等のノイズの多いエンドポイントは除外設定可能 |

**修正ファイル**: `backend/app/core/middleware.py`（新規）, `backend/app/main.py`

### 7.2 GZip 圧縮未設定 ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | レスポンスの GZip 圧縮が設定されていなかった |
| **なぜ不十分か** | API レスポンスの帯域幅削減は本番環境の基本的な最適化である。特に JSON レスポンスは圧縮効率が高く、70-90% のサイズ削減が可能 |
| **どう修正したか** | Starlette 組み込みの `GZipMiddleware` を追加。`minimum_size=1000`（1KB 以上のレスポンスのみ圧縮）で設定 |

**修正ファイル**: `backend/app/main.py`

### 7.3 TrustedHost ミドルウェア未設定 ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | Host ヘッダーの検証が行われていなかった |
| **なぜ不十分か** | Host ヘッダーインジェクション攻撃により、パスワードリセットメール等で悪意ある URL を生成される可能性がある（OWASP: Host Header Injection）。本番環境では許可するホスト名を明示的に制限すべき |
| **どう修正したか** | `settings.TRUSTED_HOSTS` が設定されている場合のみ `TrustedHostMiddleware` を有効化。開発環境ではデフォルト空リストのため無効 |

**修正ファイル**: `backend/app/main.py`, `backend/app/core/config.py`

### 7.4 Prometheus メトリクスが未初期化 ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `prometheus-fastapi-instrumentator` パッケージが `requirements.txt` にインストールされているにもかかわらず、アプリケーションコード内で一切初期化されていなかった |
| **なぜ不十分か** | 依存関係に含めながら使用していない「死んだ依存関係」は品質の低さを示す。Prometheus メトリクスは本番環境での監視（リクエスト数、レイテンシ分布、エラー率）の基盤であり、CloudWatch や Grafana と連携して可観測性を提供する |
| **どう修正したか** | `Instrumentator` を初期化し、`app` に計装を適用。`/metrics` エンドポイントを公開（OpenAPI スキーマには含めない）。ヘルスチェック・メトリクスエンドポイント自体はメトリクス収集から除外 |

**修正ファイル**: `backend/app/main.py`

### 7.5 認証エンドポイントにレート制限がない ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `/auth/login` と `/auth/register` エンドポイントにレート制限が一切なかった |
| **なぜ不十分か** | レート制限なしのログインエンドポイントは、ブルートフォース攻撃（パスワード総当たり）やクレデンシャルスタッフィング攻撃（他サイトから漏洩したパスワードリストによる攻撃）に対して完全に無防備である。OWASP Top 10「Broken Authentication」の典型的な脆弱性 |
| **どう修正したか** | `RateLimiter` クラスをスライディングウィンドウ方式で実装し、同一 IP から 60 秒間に 10 回を超えるリクエストを HTTP 429 で拒否。FastAPI の `Depends` で `/auth/login` と `/auth/register` に適用 |

**修正ファイル**: `backend/app/core/rate_limit.py`（新規）, `backend/app/modules/auth/router.py`

### 7.6 ミドルウェアがモジュール分離されていない ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | カスタムミドルウェアクラスが `main.py` 内にインラインで定義されていた |
| **なぜ不十分か** | `main.py` はアプリケーションの組み立て（ワイヤリング）だけを行うべきファイルであり、ビジネスロジックやミドルウェアの実装を含めると肥大化し保守性が下がる。関心の分離（Separation of Concerns）に反する |
| **どう修正したか** | `app/core/middleware.py` を新設し、`RequestIDMiddleware`、`AccessLoggingMiddleware`、`SecurityHeadersMiddleware` の 3 つのカスタムミドルウェアを移動。`main.py` は import して登録するだけに簡素化 |

**修正ファイル**: `backend/app/core/middleware.py`（新規）, `backend/app/main.py`

### 7.7 `Permissions-Policy` ヘッダー未設定 ★☆☆ 軽微

| 項目 | 内容 |
|------|------|
| **何が不十分か** | ブラウザの機能ポリシー（カメラ、マイク、位置情報等）を制限するヘッダーがなかった |
| **なぜ不十分か** | `Permissions-Policy` ヘッダーを設定しないと、XSS 攻撃で注入されたスクリプトがカメラやマイクにアクセスできる可能性がある |
| **どう修正したか** | `SecurityHeadersMiddleware` に `Permissions-Policy: camera=(), microphone=(), geolocation=()` を追加 |

**修正ファイル**: `backend/app/core/middleware.py`

### 7.8 ミドルウェアの実行順序が未文書化 ★☆☆ 軽微

| 項目 | 内容 |
|------|------|
| **何が不十分か** | ミドルウェアの実行順序がコード上で明示されておらず、依存関係が不明だった |
| **なぜ不十分か** | Starlette のミドルウェアは `add_middleware` の逆順で実行される特殊な挙動があり、順序を間違えると機能が正しく動かない（例: AccessLogging が RequestID の外側だと `request_id` がログに含まれない） |
| **どう修正したか** | `main.py` のミドルウェア登録箇所にリクエスト/レスポンスの処理順序を明示的にコメントで文書化 |

**修正ファイル**: `backend/app/main.py`

---

### 現在のミドルウェアスタック（完成形）

```
リクエスト処理順（外側 → 内側）:

  TrustedHost（本番のみ）
    → SecurityHeaders
      → RequestID
        → AccessLogging
          → GZip
            → CORS
              → [Prometheus 計測]
                → Route Handler

ファイル構成:
  app/core/middleware.py   — カスタムミドルウェア（RequestID / AccessLogging / SecurityHeaders）
  app/core/rate_limit.py   — レート制限（認証エンドポイント用）
  app/main.py              — ミドルウェアスタックの組み立て + Prometheus 初期化
```

---

## 修正一覧（全サマリー）

### バックエンド — セキュリティ・可観測性・設計（20項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 1 | ★★★ | セキュリティ | CORS ミドルウェア追加 | `main.py`, `config.py` |
| 2 | ★★★ | セキュリティ | セキュリティヘッダーミドルウェア追加 | `middleware.py` |
| 3 | ★★☆ | セキュリティ | Cookie `secure` フラグ条件付与 | `cookies.py`, `config.py` |
| 4 | ★★☆ | セキュリティ | `clear_refresh_cookie` に `secure`/`samesite` 追加 | `cookies.py` |
| 5 | ★★★ | 可観測性 | ログ初期化の呼び出し追加 | `main.py` |
| 6 | ★★☆ | 可観測性 | Request ID ミドルウェア追加 | `middleware.py` |
| 7 | ★★☆ | 可観測性 | 未ハンドル例外のログ出力追加 | `main.py` |
| 8 | ★★★ | 設計 | Lifespan（起動・終了処理）追加 | `main.py` |
| 9 | ★★☆ | 設計 | `service_version` → `version` 修正 | `main.py` |
| 10 | ★★☆ | セキュリティ | 本番環境での API ドキュメント非公開 | `main.py` |
| 11 | ★★☆ | 設計 | バリデーションエラー形式の統一 | `main.py` |
| 12 | ★★☆ | 設計 | MetaData 命名規約の設定 | `base.py` |
| 13 | ★☆☆ | 設計 | `pool_timeout` 設定の適用 | `database.py`, `config.py` |
| 14 | ★☆☆ | 設計 | `POSTGRES_SSL` 設定の適用 | `config.py` |
| 15 | ★★☆ | 設計 | Liveness エンドポイント追加 | `health.py` |
| 16 | ★★☆ | バグ | `filed` → `field` タイポ修正 | `common.py` |
| 17 | ★★☆ | バグ | `revoke_if_ative` → `revoke_if_active` タイポ修正 | `repository.py`, `service.py` |
| 18 | ★☆☆ | バグ | エラーメッセージの統一 (`expires` → `expired`) | `dependencies.py` |
| 19 | ★★☆ | 規約 | `userRepoDep` → `UserRepoDep` PEP 8 命名規約 | `dependencies.py` |
| 20 | ★★☆ | 規約 | `main.py` import 順序を PEP 8 準拠に修正 | `main.py` |

### バックエンド — ミドルウェア・アーキテクチャ（8項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 21 | ★★★ | 可観測性 | 構造化アクセスログミドルウェア追加 | `middleware.py` |
| 22 | ★★☆ | 最適化 | GZip 圧縮ミドルウェア追加 | `main.py` |
| 23 | ★★☆ | セキュリティ | TrustedHost ミドルウェア追加（本番用） | `main.py`, `config.py` |
| 24 | ★★★ | 可観測性 | Prometheus メトリクス計装 + `/metrics` エンドポイント | `main.py` |
| 25 | ★★★ | セキュリティ | 認証エンドポイントのレート制限追加 | `rate_limit.py`, `auth/router.py` |
| 26 | ★★☆ | 設計 | ミドルウェアを専用モジュール `core/middleware.py` に分離 | `middleware.py`, `main.py` |
| 27 | ★☆☆ | セキュリティ | `Permissions-Policy` ヘッダー追加 | `middleware.py` |
| 28 | ★☆☆ | 品質 | ミドルウェア実行順序のコメント文書化 | `main.py` |

### バックエンド — コード品質（4項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 29 | ★☆☆ | 品質 | デッドコード `_client_key` 削除 | `auth/router.py` |
| 30 | ★☆☆ | 品質 | `_encode_token` の死コード除去（PyJWT v2+） | `security.py` |
| 31 | ★☆☆ | 品質 | `config.py`/`database.py` 未使用 import 削除 | `config.py`, `database.py` |
| 32 | ★☆☆ | 品質 | `auth/router.py` 未使用 `request` パラメータ削除 | `auth/router.py` |

### バックエンド — 依存関係（1項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 33 | ★★☆ | 依存関係 | 本番/開発依存関係の分離 | `requirements.txt`, `requirements-dev.txt` |

### フロントエンド（7項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 34 | ★★★ | 設定 | `tsconfig.json` を Project References 形式に変換 | `tsconfig.json`, `tsconfig.app.json` |
| 35 | ★★☆ | 設定 | `src/vite-env.d.ts` 新規作成 | `vite-env.d.ts` |
| 36 | ★★☆ | 型安全性 | `ApiError` パラメータプロパティを明示的宣言に変換 | `client.ts` |
| 37 | ★★☆ | 型安全性 | `ErrorBoundary` に `override` 修飾子追加 | `ErrorBoundary.tsx` |
| 38 | ★☆☆ | バグ | `font-semibodl` → `font-semibold` タイポ修正 | `LoginPage.tsx` |
| 39 | ★☆☆ | 品質 | 未使用 import 削除（`useEffectEvent`, `Link`） | `AuthProvider.tsx`, `HomePage.tsx` |
| 40 | ★★☆ | バグ | 存在しない `/posts` ルートへのリンク削除 | `HomePage.tsx` |

---

## 8. インフラストラクチャ・ビルド品質の問題（追加改善）

以下は初回レビュー後にさらに深掘りしたプロ品質レビューで発見・修正した項目です。

### 8.1 Backend Dockerfile がプロ品質でない ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | 単一ステージの最小構成で、(1) マイグレーションファイルがコピーされていない (2) root ユーザーで実行 (3) HEALTHCHECK 命令なし (4) 開発/本番の区別なし |
| **なぜ不十分か** | **root 実行**: コンテナ内で任意コード実行（RCE）の脆弱性が発生した場合、root 権限でホストに影響を与えるリスクがある。CIS Docker Benchmark で非 root 実行は必須要件。**マイグレーション未コピー**: `docker build` で本番イメージを作っても `alembic upgrade head` を実行できない。**HEALTHCHECK なし**: コンテナオーケストレーター（ECS/K8s）がコンテナの生死を判断できない。**単一ステージ**: 開発と本番で同じイメージを使うと、不要なファイル（テスト、docs 等）が本番に含まれる |
| **どう修正したか** | マルチステージ Dockerfile に書き換え: `base`（依存インストール）→ `development`（docker-compose 用）→ `production`（非 root ユーザー、HEALTHCHECK、最小ファイル構成）。docker-compose.yml で `target: development` を明示指定 |

**修正ファイル**: `backend/Dockerfile`, `docker-compose.yml`

### 8.2 Frontend Dockerfile が開発専用 ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `npm run dev` のみで、本番ビルド（`npm run build`）のステージがなかった |
| **なぜ不十分か** | CI/CD で `docker build` しても本番成果物（静的ファイル）が生成されない。AWS S3 + CloudFront にデプロイするには `dist/` が必要であり、ビルドステージがなければ CI パイプラインに組み込めない |
| **どう修正したか** | マルチステージ Dockerfile: `deps`（依存）→ `development`（HMR 開発）→ `build`（静的ファイル生成）→ `production`（nginx で配信、非 root）。docker-compose.yml で `target: development` を指定 |

**修正ファイル**: `frontend/Dockerfile`, `docker-compose.yml`

### 8.3 `.dockerignore` ファイルが存在しない ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | バックエンド・フロントエンド両方に `.dockerignore` がなかった |
| **なぜ不十分か** | **セキュリティリスク**: `.env` ファイル（パスワード、SECRET_KEY 等を含む）や `.git` ディレクトリ（リポジトリ全履歴）がイメージに含まれてしまう。イメージが外部に漏洩した場合、全機密情報が流出する。**ビルド速度**: `node_modules`（数百MB）、`__pycache__`、`.venv` 等の不要ファイルがビルドコンテキストに含まれ、ビルドが遅くなる |
| **どう修正したか** | 両方に `.dockerignore` を作成。`.env*`、`.git`、キャッシュ、IDE 設定、ドキュメント等を除外 |

**修正ファイル**: `backend/.dockerignore`（新規）, `frontend/.dockerignore`（新規）

### 8.4 `.env.example` が存在しない ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | 必要な環境変数を文書化したテンプレートファイルがなかった |
| **なぜ不十分か** | 新しいチームメンバーがプロジェクトをセットアップする際、どの環境変数が必要か分からない。`.env` は `.gitignore` で除外されるため、リポジトリには含まれない。`.env.example` はリポジトリに含まれるテンプレートとして、**必要な変数名と安全なデフォルト値**を提供する |
| **どう修正したか** | `.env.example` を作成。PostgreSQL、バックエンド、CORS、フロントエンドの全設定項目を網羅 |

**修正ファイル**: `.env.example`（新規）

### 8.5 `pyproject.toml` が存在しない ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | Python プロジェクトのメタデータとツール設定を一元管理する `pyproject.toml` がなかった |
| **なぜ不十分か** | `pyproject.toml` は Python のモダンな標準（PEP 518/621）であり、ruff、mypy、pytest、coverage の設定を一箇所にまとめる。これがないと各ツールの設定が `setup.cfg`、`ruff.toml`、`mypy.ini`、`pytest.ini` 等に分散し、保守性が低下する。Apple/Google レベルのプロジェクトでは `pyproject.toml` での一元管理が標準 |
| **どう修正したか** | `pyproject.toml` を作成。ruff（lint ルール、isort、line-length）、mypy（strict + pydantic プラグイン）、pytest（asyncio_mode、testpaths）、coverage（ソース指定、カバレッジ閾値 70%）を設定 |

**修正ファイル**: `backend/pyproject.toml`（新規）

### 8.6 RateLimiter のメモリリーク ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `RateLimiter._requests` 辞書で、リクエストが来なくなった IP のエントリが永久にメモリに残り続ける設計だった |
| **なぜ不十分か** | `check()` メソッドは呼び出し元の IP のウィンドウ外タイムスタンプのみ除去するが、その IP が二度とリクエストしなかった場合、空リストのエントリが辞書に残る。長時間稼働するサーバーでは、異なるクライアント IP が蓄積し続け、メモリ使用量が単調増加する。これは DoS 攻撃（大量の異なる IP からリクエスト送信）で加速する |
| **どう修正したか** | `_cleanup_stale_keys()` メソッドを追加。`window_seconds * 2` の間隔で全エントリを走査し、ウィンドウ外のエントリを持つ IP を削除。`check()` 呼び出し時に自動実行される |

**修正ファイル**: `backend/app/core/rate_limit.py`

### 8.7 `database.py` に未使用の import とロガー ★☆☆ 軽微

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `structlog`、`text`（SQLAlchemy）がインポートされ、`logger` が定義されているが、いずれも `database.py` 内で使用されていない |
| **なぜ不十分か** | デッドコードはメンテナンスの負担を増やし、「意図的に使っているのか、消し忘れか」の判断コストが発生する。ruff の `F401`（未使用 import）ルールで検出される類のもの |
| **どう修正したか** | 未使用の `structlog`、`text` import および `logger` 定義を削除 |

**修正ファイル**: `backend/app/core/database.py`

### 8.8 `POSTGRES_HOST_PORT` が定義されているが未使用 ★☆☆ 軽微

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `config.py` に `POSTGRES_HOST_PORT` が定義されているが、コード上でもテンプレート上でも一切参照されていない |
| **なぜ不十分か** | docker-compose.yml のポートマッピングは `POSTGRES_PORT` を使用しており、`POSTGRES_HOST_PORT` は死んだ設定。`extra="forbid"` を設定しているにもかかわらず、使わない設定を定義するのは矛盾であり、混乱の原因 |
| **どう修正したか** | `config.py` から `POSTGRES_HOST_PORT` を削除 |

**修正ファイル**: `backend/app/core/config.py`

### 8.9 `__init__.py` ファイルの不整合 ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `repositories/` と `services/` には `__init__.py` があるのに、`app/`、`core/`、`api/`、`models/`、`modules/`、`auth/`、`users/`、`schemas/`、`shared/` にはなかった |
| **なぜ不十分か** | Python 3.3+ では暗黙的名前空間パッケージにより `__init__.py` なしでも import は動作するが、(1) mypy が `--namespace-packages` なしでは認識しない (2) pytest のテスト検出に影響する (3) プロジェクト内で一貫性がない（ある場所にはあり、ない場所にはない）のは品質上の問題 |
| **どう修正したか** | 全パッケージディレクトリに空の `__init__.py` を追加し、一貫したパッケージ構造に統一 |

**修正ファイル**: `app/`, `app/api/`, `app/core/`, `app/models/`, `app/modules/`, `app/modules/auth/`, `app/modules/users/`, `app/schemas/`, `app/shared/` に `__init__.py` を追加

### 8.10 docker-compose.yml の堅牢性不足 ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | (1) バックエンドにヘルスチェックがない (2) ビルドターゲットが未指定 (3) フロントエンドがバックエンドの起動完了を待たずに起動 |
| **なぜ不十分か** | ヘルスチェックがないと `docker compose ps` でコンテナの実際の状態が分からない（`Up` と表示されてもアプリが起動失敗している可能性がある）。ビルドターゲット未指定だとマルチステージ Dockerfile で意図しないステージがビルドされる。フロントエンドが先に起動すると API プロキシ先がまだ応答できずエラーになる |
| **どう修正したか** | バックエンドにヘルスチェック追加（liveness エンドポイントを使用）。両サービスに `target: development` を指定。フロントエンドの `depends_on` に `condition: service_healthy` を追加し、バックエンド起動完了後に起動するよう変更 |

**修正ファイル**: `docker-compose.yml`

---

## 修正一覧（追加改善分）

### インフラストラクチャ・ビルド品質（10項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 41 | ★★★ | セキュリティ/インフラ | Backend Dockerfile マルチステージ化 + 非 root 実行 | `Dockerfile`, `docker-compose.yml` |
| 42 | ★★★ | インフラ | Frontend Dockerfile マルチステージ化 + 本番ビルド対応 | `Dockerfile`, `docker-compose.yml` |
| 43 | ★★★ | セキュリティ | `.dockerignore` 追加（機密ファイル除外） | `backend/.dockerignore`, `frontend/.dockerignore` |
| 44 | ★★☆ | DX | `.env.example` 追加（環境変数テンプレート） | `.env.example` |
| 45 | ★★☆ | 品質 | `pyproject.toml` 追加（ツール設定一元管理） | `backend/pyproject.toml` |
| 46 | ★★☆ | バグ | RateLimiter メモリリーク修正 | `rate_limit.py` |
| 47 | ★☆☆ | 品質 | `database.py` 未使用 import/logger 削除 | `database.py` |
| 48 | ★☆☆ | 品質 | `POSTGRES_HOST_PORT` 死設定削除 | `config.py` |
| 49 | ★★☆ | 品質 | `__init__.py` 一貫性修正（全パッケージに追加） | 9 ファイル |
| 50 | ★★☆ | 堅牢性 | docker-compose.yml ヘルスチェック・ターゲット追加 | `docker-compose.yml` |

---

## 9. Terraform / CI/CD のブラッシュアップ

以下は Terraform コードおよび GitHub Actions ワークフローのプロ品質レビューで発見・修正した項目です。

### 9.1 VPC モジュール: 変数参照のタイポ ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `aws_subnet.private` の tags で `var.availability_zone[count.index]`（`var.` と `s` が欠落）、`aws_subnet.database` で `availability_zones[count.index]`（`var.` が欠落）と記述されていた |
| **なぜ不十分か** | `terraform plan` 時にエラーとなり、インフラを構築できない |
| **どう修正したか** | 全箇所を `var.availability_zones[count.index]` に統一 |

**修正ファイル**: `infrastructure/modules/vpc/main.tf`

### 9.2 VPC モジュール: variables.tf / outputs.tf が空 ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `variables.tf` と `outputs.tf` が空ファイルで、`main.tf` が参照する変数が未定義 |
| **なぜ不十分か** | `terraform plan` が即座に失敗する |
| **どう修正したか** | `project_name`, `environment`, `vpc_cidr`, `availability_zones`, `aws_region` の変数定義と、`vpc_id`, `public_subnet_ids`, `private_subnet_ids`, `database_subnet_ids` の出力定義を追加 |

**修正ファイル**: `infrastructure/modules/vpc/variables.tf`, `infrastructure/modules/vpc/outputs.tf`

### 9.3 NAT Gateway → VPC エンドポイントへのコスト最適化 ★★★ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | NAT Gateway（約 $32/月/AZ × 2 = $64/月）がデフォルトで有効だった |
| **なぜ不十分か** | 個人開発・小規模プロジェクトでは大きなコスト負担。ECS Fargate が外部インターネットに出る必要があるのは ECR/S3/CloudWatch Logs/Secrets Manager への接続のみで、これらは VPC エンドポイントで代替可能 |
| **どう修正したか** | NAT Gateway をコメントアウトし、Gateway 型（S3: 無料）+ Interface 型（ECR API, ECR DKR, Logs, Secrets Manager）の VPC エンドポイントを追加。コスト約 56% 削減（$64/月 → $28/月） |

**修正ファイル**: `infrastructure/modules/vpc/main.tf`

### 9.4 ECR モジュール: `image_scanning_congiguration` タイポ ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `image_scanning_congiguration`（`configuration` のスペルミス） |
| **なぜ不十分か** | Terraform が未知のブロック名としてエラーを出す |
| **どう修正したか** | `image_scanning_configuration` に修正 |

**修正ファイル**: `infrastructure/modules/ecr/main.tf`

### 9.5 RDS モジュール: 多数のタイポ ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | 以下の 7 箇所のタイポ:<br>- `var.production` → `var.project_name`<br>- `var.esc_security_group_id` → `var.ecs_security_group_id`<br>- `indentifier` → `identifier`<br>- `{$var.project_name}` → `${var.project_name}`<br>- `var.db.allocated_storage` → `var.db_allocated_storage`<br>- `ture` → `true`（4 箇所）<br>- `"prod"` → `"production"`（環境名の不一致） |
| **なぜ不十分か** | いずれも `terraform plan` でエラーとなる致命的なバグ |
| **どう修正したか** | 全箇所を正しい記述に修正 |

**修正ファイル**: `infrastructure/modules/rds/main.tf`

### 9.6 ALB モジュール: 全ファイルが空 ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `main.tf`, `variables.tf`, `outputs.tf` がすべて空 |
| **なぜ不十分か** | ECS サービスがインターネットからのリクエストを受け取れない。ALB はバックエンド API の入口であり、ヘルスチェック・TLS 終端・HTTP→HTTPS リダイレクトを担う必須コンポーネント |
| **どう修正したか** | ALB + セキュリティグループ + ターゲットグループ + HTTPS/HTTP リスナーを完全実装 |

**修正ファイル**: `infrastructure/modules/alb/main.tf`, `variables.tf`, `outputs.tf`

### 9.7 ECS モジュール: 重複セキュリティグループ定義 ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `main.tf` 末尾に ALB/ECS/RDS のセキュリティグループが重複定義されていた。さらに `aws_vpc.main.id`（このモジュールに存在しない参照）や `aws_security_gropu.alb.id`（タイポ）を含んでいた |
| **なぜ不十分か** | 同名リソースの重複定義は Terraform エラー。存在しない参照もエラー |
| **どう修正したか** | 重複セキュリティグループ定義を削除。各モジュールに適切に分離されているものだけを残した |

**修正ファイル**: `infrastructure/modules/ecs/main.tf`

### 9.8 ECS モジュール: ヘルスチェックで httpx を使用 ★★☆ 重要

| 項目 | 内容 |
|------|------|
| **何が不十分か** | タスク定義のヘルスチェックが `import httpx` を使用していた |
| **なぜ不十分か** | 本番用 Docker イメージに httpx がインストールされていない場合、ヘルスチェックが常に失敗する |
| **どう修正したか** | Python 標準ライブラリの `urllib.request` を使用するヘルスチェックに変更 |

**修正ファイル**: `infrastructure/modules/ecs/main.tf`

### 9.9 S3-CloudFront モジュール: 複数タイポ ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | - `Version = "2017-10-17"` → `"2012-10-17"`（IAM ポリシーバージョン）<br>- `origin_access_contorol_id` → `origin_access_control_id`<br>- `us_east_1` → `us-east-1`（リージョン名）<br>- ACM 証明書と Route 53 レコードがモジュール内にハードコードされていた |
| **なぜ不十分か** | いずれも `terraform plan/apply` でエラーとなるか、リソースが正しく動作しない |
| **どう修正したか** | タイポ修正 + ACM/Route53 リソースをモジュールから分離（ドメイン設定はオプショナルに）+ カスタムドメインなしでもデフォルト CloudFront 証明書で動作するよう修正 |

**修正ファイル**: `infrastructure/modules/s3-cloudfront/main.tf`

### 9.10 IAM モジュール: 全ファイルが空 ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | OIDC プロバイダとデプロイ用 IAM ロールが未実装 |
| **なぜ不十分か** | GitHub Actions の `aws-actions/configure-aws-credentials` が AssumeRole に失敗し、CI/CD パイプラインが動作しない |
| **どう修正したか** | OIDC プロバイダ + GitHub Actions デプロイ用 IAM ロール + 最小権限ポリシー（ECR push, ECS update, S3 sync, CloudFront invalidation）を完全実装 |

**修正ファイル**: `infrastructure/modules/iam/main.tf`, `variables.tf`, `outputs.tf`

### 9.11 Production 環境: main.tf が不完全 ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `main.tf` に VPC と ECS の 2 モジュールしか記述されておらず、ECR, ALB, RDS, S3-CloudFront, IAM が欠落。`terraform` ブロック（required_version, required_providers）もなし |
| **なぜ不十分か** | 全モジュールの呼び出しと相互接続がなければインフラは構築できない |
| **どう修正したか** | 全 7 モジュールの呼び出しとパラメータ連携、provider 設定、data source を追加 |

**修正ファイル**: `infrastructure/environments/production/main.tf`

### 9.12 Production 環境: variables.tf / terraform.tfvars / outputs.tf が空 ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | 全ファイルが空で、`main.tf` が参照する変数が未定義 |
| **なぜ不十分か** | `terraform plan` が変数未定義エラーで即座に失敗する |
| **どう修正したか** | 全変数の定義（`variables.tf`）、最小コスト構成のデフォルト値（`terraform.tfvars`）、必要な出力値（`outputs.tf`）を追加 |

**修正ファイル**: `infrastructure/environments/production/variables.tf`, `terraform.tfvars`, `outputs.tf`

### 9.13 ci.yml: YAML 構文が不正 ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | `ci.yml` が YAML として不正な構造だった（`name:`, `on:`, jobs の適切な定義がない断片的なコード）。また `downgrade` という typo（`done` の誤り）、`applocation/json`（`application/json` の誤り）を含んでいた |
| **なぜ不十分か** | GitHub Actions が YAML をパースできず、CI パイプラインが一切動作しない |
| **どう修正したか** | 完全な YAML 構造で書き直し。`backend-test`（lint + type check + test + migration test）、`frontend-build`（lint + build）、`compose-smoke`（統合テスト）の 3 ジョブ構成 |

**修正ファイル**: `.github/workflows/ci.yml`

### 9.14 deploy.yml: 複数のタイポ ★★★ 致命的

| 項目 | 内容 |
|------|------|
| **何が不十分か** | 以下のタイポ:<br>- `guthub.ref` → `github.ref`<br>- `test-app-ECS_CLUSTER` → `test-app-cluster`（Terraform のクラスタ名と不一致）<br>- `npm run Lint` → `npm run lint`<br>- `$ECR_REPOSITORY/$ECR_REPOSITORY:` → 環境変数の二重展開バグ<br>- `$ECR_SERVICE` → `$ECS_SERVICE`<br>- `${{ setps.task-def.outputs.arn }}` → `${{ steps.task-def.outputs.arn }}` |
| **なぜ不十分か** | いずれも CI/CD パイプラインの実行失敗を引き起こす |
| **どう修正したか** | 全タイポを修正し、環境変数名を Terraform の出力と一致させた |

**修正ファイル**: `.github/workflows/deploy.yml`

---

## 修正一覧（Terraform / CI/CD ブラッシュアップ分）

### Terraform — VPC モジュール（3 項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 51 | ★★★ | バグ | 変数参照のタイポ修正 | `modules/vpc/main.tf` |
| 52 | ★★★ | 欠落 | variables.tf / outputs.tf の内容追加 | `modules/vpc/variables.tf`, `outputs.tf` |
| 53 | ★★★ | コスト | NAT Gateway → VPC エンドポイントへ置換 | `modules/vpc/main.tf` |

### Terraform — ECR モジュール（2 項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 54 | ★★★ | バグ | `image_scanning_congiguration` タイポ修正 | `modules/ecr/main.tf` |
| 55 | ★★★ | 欠落 | variables.tf / outputs.tf の内容追加 | `modules/ecr/variables.tf`, `outputs.tf` |

### Terraform — RDS モジュール（2 項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 56 | ★★★ | バグ | 7 箇所のタイポ一括修正 | `modules/rds/main.tf` |
| 57 | ★★★ | 欠落 | variables.tf / outputs.tf の内容追加 | `modules/rds/variables.tf`, `outputs.tf` |

### Terraform — ALB モジュール（1 項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 58 | ★★★ | 欠落 | ALB + SG + TG + リスナーの全実装 | `modules/alb/main.tf`, `variables.tf`, `outputs.tf` |

### Terraform — ECS モジュール（3 項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 59 | ★★★ | バグ | 重複 SG 定義 + タイポ削除 | `modules/ecs/main.tf` |
| 60 | ★★☆ | 堅牢性 | ヘルスチェックを標準ライブラリに変更 | `modules/ecs/main.tf` |
| 61 | ★★★ | 欠落 | variables.tf / outputs.tf の内容追加 | `modules/ecs/variables.tf`, `outputs.tf` |

### Terraform — S3-CloudFront モジュール（2 項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 62 | ★★★ | バグ | 複数タイポ + ACM 分離 + デフォルト証明書対応 | `modules/s3-cloudfront/main.tf` |
| 63 | ★★★ | 欠落 | variables.tf / outputs.tf の内容追加 | `modules/s3-cloudfront/variables.tf`, `outputs.tf` |

### Terraform — IAM モジュール（1 項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 64 | ★★★ | 欠落 | OIDC + デプロイロール + ポリシーの全実装 | `modules/iam/main.tf`, `variables.tf`, `outputs.tf` |

### Terraform — Production 環境（2 項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 65 | ★★★ | 欠落 | main.tf の全モジュール呼び出し完成 | `environments/production/main.tf` |
| 66 | ★★★ | 欠落 | variables.tf / terraform.tfvars / outputs.tf 追加 | `environments/production/` |

### GitHub Actions（2 項目）

| # | 重要度 | カテゴリ | 修正内容 | 修正ファイル |
|---|--------|----------|----------|-------------|
| 67 | ★★★ | バグ | ci.yml 完全書き直し（YAML 構文修正） | `.github/workflows/ci.yml` |
| 68 | ★★★ | バグ | deploy.yml の 6 箇所のタイポ修正 | `.github/workflows/deploy.yml` |
