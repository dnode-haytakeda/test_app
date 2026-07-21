// 404 ページ: 認証ガードに依存しない、機能横断のフォールバック画面。
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center px-4">
      <div className="max-w-md text-center">
        <p className="text-sm font-medium text-blue-600 dark:text-blue-400">
          404
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-gray-900 dark:text-gray-100">
          Page not found
        </h1>
        <p className="mt-3 text-gray-600 dark:text-gray-400">
          The page you are looking for does not exist or has been moved.
        </p>
        <Link
          to="/"
          className="inline-block mt-6 rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-500"
        >
          Go home
        </Link>
      </div>
    </main>
  );
}
