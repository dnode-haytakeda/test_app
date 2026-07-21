// ホームページ: API ヘルスチェック、現在ユーザー、テーマ切り替え。
//
// このページは ``src/shared/lib`` / ``src/app/providers`` 配下の共通ユーティリティの
// 正典的な使用例として機能する:
//   - ``cn``         : 条件付き Tailwind クラス合成
//   - ``formatRelative`` : ヘルスチェック取得時刻のロケール対応相対表示
//   - ``useTheme``   : ライト/ダーク切り替えボタン
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../auth/useAuth";
import { api } from "../../../shared/api/client";
import { cn } from "../../../shared/lib/cn";
import { formatRelative } from "../../../shared/lib/formatDate";
import { useTheme } from "../../../app/providers/useTheme";

interface HealthResponse {
  status: string;
  version: string;
  checks: Record<string, string>;
}

export function HomePage() {
  const { user, logout } = useAuth();
  const { resolved, setMode } = useTheme();
  const { data, isLoading, error, dataUpdatedAt } = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => api.get<HealthResponse>("/health", { signal }),
  });

  const buttonClass = cn(
    "text-sm rounded border px-3 py-1",
    "border-gray-300 dark:border-gray-700",
    "text-gray-800 dark:text-gray-200",
    "hover:bg-gray-100 dark:hover:bg-gray-800",
  );

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <header className="flex items-center justify-between px-6 py-4 bg-white dark:bg-gray-900 shadow-sm">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
          {"my-app"}
        </h1>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setMode(resolved === "dark" ? "light" : "dark")}
            aria-label="Toggle theme"
            className={buttonClass}
          >
            {resolved === "dark" ? "☀️ Light" : "🌙 Dark"}
          </button>
          {user && (
            <>
              <span className="text-sm text-gray-600 dark:text-gray-300">
                {user.email}
              </span>
              <button
                type="button"
                onClick={() => void logout()}
                className={buttonClass}
              >
                Sign out
              </button>
            </>
          )}
        </div>
      </header>

      <main className="flex items-center justify-center py-16 px-4">
        <div className="text-center max-w-md">
          <p className="text-gray-600 dark:text-gray-400 mb-8">
            {"フルスタック Web アプリケーション"}
          </p>

          <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-2 text-gray-900 dark:text-gray-100">
              API Health
            </h2>
            {isLoading && <p className="text-gray-500">Checking…</p>}
            {error && (
              <p className="text-red-600">
                Failed to reach API: {error.message}
              </p>
            )}
            {data && (
              <div className="text-left space-y-1 text-gray-800 dark:text-gray-200">
                <p>
                  <span className="font-medium">Status:</span>{" "}
                  <span
                    className={cn(
                      data.status === "ok"
                        ? "text-green-600"
                        : "text-yellow-600",
                    )}
                  >
                    {data.status}
                  </span>
                </p>
                <p>
                  <span className="font-medium">Version:</span> {data.version}
                </p>
                {data.checks &&
                  Object.entries(data.checks).map(([key, value]) => (
                    <p key={key}>
                      <span className="font-medium">{key}:</span> {value}
                    </p>
                  ))}
                {dataUpdatedAt > 0 && (
                  <p className="text-xs text-gray-500 pt-2">
                    Last checked: {formatRelative(new Date(dataUpdatedAt))}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
