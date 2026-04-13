"use client";

import * as React from "react";
import { FileDown, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { apiFetch } from "@/lib/apiClient";

type DiagnosisDetail = {
  sessionId: string;
  title: string;
  status: "uploaded" | "processing" | "ready" | "failed";
  createdAt: string;
  updatedAt: string;
  createdBy: string;
  originalFileName?: string;
  latestRunId: string | null;
  legacyJobId: string | null;
  latestArtifactCount: number;
  uploads: Array<{ uploadId: string; originalName: string }>;
  runs: Array<{ runId: string; legacyJobId: string; status: string }>;
  events: Array<{ eventId: string; description: string; createdAt: string }>;
  legacyJob?: {
    jobId: string;
    status: string;
    error: string;
    artifacts: Array<{ artifactId: string; label: string }>;
  } | null;
};

function statusLabel(status: DiagnosisDetail["status"]): string {
  switch (status) {
    case "processing":
      return "처리 중";
    case "ready":
      return "완료";
    case "failed":
      return "실패";
    default:
      return "업로드됨";
  }
}

export function DiagnosisSessionDetailPage({ sessionId }: { sessionId: string }) {
  const [session, setSession] = React.useState<DiagnosisDetail | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    void (async () => {
      setError(null);
      try {
        const result = await apiFetch<{ session: DiagnosisDetail }>(`/api/diagnosis/sessions/${sessionId}`);
        if (active) setSession(result.session);
      } catch {
        if (active) setError("진단 세션을 불러오지 못했습니다.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [sessionId]);

  if (loading) {
    return (
      <div className="flex min-h-[320px] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-[#A68645]" />
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        {error ?? "진단 세션을 찾을 수 없습니다."}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-6 py-10 md:px-10">
      <section className="rounded-[32px] border border-[#E2D6BA] bg-[#FFF9EE] p-8 shadow-[0_18px_40px_rgba(52,40,18,0.08)]">
        <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[#A68645]">
          {statusLabel(session.status)}
        </div>
        <h1 className="mt-3 text-3xl font-black tracking-tight text-[#231F16]">{session.title}</h1>
        <p className="mt-4 text-sm leading-7 text-[#6C624D]">
          원본 파일 {session.originalFileName || "-"} · 작성자 {session.createdBy}
        </p>
      </section>

      <section className="rounded-[32px] border border-[#E2D6BA] bg-[#FFF9EE] p-8 shadow-[0_18px_40px_rgba(52,40,18,0.08)]">
        <div className="text-sm font-semibold uppercase tracking-[0.22em] text-[#A68645]">Artifacts</div>
        <div className="mt-5 flex flex-wrap gap-3">
          {(session.legacyJob?.artifacts ?? []).map((artifact) => (
            <Button
              key={artifact.artifactId}
              variant="secondary"
              onClick={() => {
                if (!session.legacyJob?.jobId) return;
                window.open(
                  `/api/jobs/${session.legacyJob.jobId}/artifact?artifactId=${artifact.artifactId}`,
                  "_blank",
                  "noopener,noreferrer",
                );
              }}
            >
              <FileDown className="h-4 w-4" />
              {artifact.label} 다운로드
            </Button>
          ))}
        </div>
      </section>
    </div>
  );
}
