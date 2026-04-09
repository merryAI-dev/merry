"use client";

import * as React from "react";
import { AlertTriangle, RotateCcw, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { ApiError } from "@/lib/apiClient";

export default function ReportError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const correlationId = error instanceof ApiError ? error.correlationId : null;

  React.useEffect(() => {
    console.error("[ReportError]", error.message, {
      ...(correlationId && { correlationId }),
      ...(error.digest && { digest: error.digest }),
    });
  }, [error, correlationId]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 p-8 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[#FFF5F5]">
        <AlertTriangle className="h-8 w-8 text-[#DC2626]" />
      </div>

      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-[#191F28]">
          리포트를 불러올 수 없습니다
        </h2>
        <p className="max-w-md text-sm text-[#8B95A1]">
          {error.message || "리포트 데이터를 가져오는 중 오류가 발생했습니다."}
        </p>
        {(error.digest || correlationId) && (
          <p className="font-mono text-xs text-[#8B95A1]/60">
            {error.digest && <>오류 코드: {error.digest}</>}
            {error.digest && correlationId && " | "}
            {correlationId && <>CID: {correlationId}</>}
          </p>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Link
          href="/review"
          className="flex items-center gap-2 rounded-xl border border-[#E5E8EB] px-5 py-2.5 text-sm font-medium text-[#4E5968] transition-colors hover:bg-[#F9FAFB]"
        >
          <ArrowLeft className="h-4 w-4" />
          목록으로
        </Link>
        <button
          onClick={reset}
          className="flex items-center gap-2 rounded-xl bg-[#191F28] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#2D3540]"
        >
          <RotateCcw className="h-4 w-4" />
          다시 시도
        </button>
      </div>
    </div>
  );
}
