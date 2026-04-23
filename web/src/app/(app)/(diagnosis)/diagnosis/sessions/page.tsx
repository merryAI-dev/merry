/* eslint-disable @next/next/no-img-element */
"use client";

import * as React from "react";
import Link from "next/link";
import { FolderKanban, Loader2, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { apiFetch } from "@/lib/apiClient";

type DiagnosisSessionRow = {
  sessionId: string;
  title: string;
  status: "uploaded" | "processing" | "ready" | "failed";
  createdAt: string;
  updatedAt: string;
  createdBy: string;
  originalFileName?: string;
  latestArtifactCount: number;
};

function statusLabel(status: DiagnosisSessionRow["status"]): string {
  switch (status) {
    case "processing":
      return "처리 중";
    case "ready":
      return "대화 중";
    case "failed":
      return "실패";
    default:
      return "업로드됨";
  }
}

export default function DiagnosisSessionsPage() {
  const [sessions, setSessions] = React.useState<DiagnosisSessionRow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setError(null);
    try {
      const result = await apiFetch<{ sessions: DiagnosisSessionRow[] }>("/api/diagnosis/sessions?limit=20");
      setSessions(result.sessions ?? []);
    } catch {
      setError("진단 세션을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="min-h-full px-6 py-10 md:px-10">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-sm font-semibold uppercase tracking-[0.22em] text-[#A68645]">Sessions</div>
            <h1 className="mt-3 text-3xl font-black tracking-tight text-[#231F16]">최근 진단 세션</h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-[#6C624D]">
              diagnosis 전용 대화 세션, 응답 상태, 생성된 결과물을 한 곳에서 확인합니다.
            </p>
          </div>
          <Button variant="secondary" onClick={() => void load()} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            새로고침
          </Button>
        </div>

        {error ? (
          <div className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        <div className="mt-8 grid gap-4">
          {sessions.map((session) => (
            <article
              key={session.sessionId}
              className="rounded-[28px] border border-[#E2D6BA] bg-[#FFF9EE] p-6 shadow-[0_18px_40px_rgba(52,40,18,0.08)]"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[#A68645]">
                    {statusLabel(session.status)}
                  </div>
                  <h2 className="mt-2 text-2xl font-black tracking-tight text-[#231F16]">{session.title}</h2>
                  <div className="mt-3 text-sm text-[#6C624D]">
                    {session.originalFileName || "파일명 없음"} · 작성자 {session.createdBy}
                  </div>
                </div>
                <Link
                  href={`/diagnosis/sessions/${session.sessionId}`}
                  className="inline-flex items-center gap-2 rounded-full border border-[#D8C59A] bg-white px-4 py-2 text-sm font-semibold text-[#6D5421]"
                >
                  <FolderKanban className="h-4 w-4" />
                  세션 열기
                </Link>
              </div>
            </article>
          ))}
          {!loading && sessions.length === 0 ? (
            <div className="rounded-[28px] border border-dashed border-[#D8C59A] bg-[#FFFCF5] px-6 py-10 text-center text-sm text-[#7C6E55]">
              아직 진단 세션이 없습니다. 먼저 업로드에서 시트를 올려주세요.
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
