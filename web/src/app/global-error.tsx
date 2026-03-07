"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="ko">
      <body className="flex min-h-screen items-center justify-center bg-white p-8">
        <div className="max-w-md space-y-6 text-center">
          <h2 className="text-lg font-semibold text-gray-900">
            예기치 않은 오류가 발생했습니다
          </h2>
          <p className="text-sm text-gray-500">
            {error.message || "잠시 후 다시 시도해주세요."}
          </p>
          <button
            onClick={reset}
            className="rounded-xl bg-gray-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-800"
          >
            다시 시도
          </button>
        </div>
      </body>
    </html>
  );
}
