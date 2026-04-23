"use client";

import * as React from "react";
import { FileDown, Loader2, Send, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { apiFetch } from "@/lib/apiClient";

type DiagnosisAnalysisSummary = {
  companyName?: string;
  sheets: string[];
  gapCount: number;
  scoreCards: Array<{
    category: string;
    score?: number | null;
    yesRatePct?: number | null;
  }>;
  sampleGaps: Array<{
    module?: string;
    question?: string;
    detail?: string;
  }>;
};

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
  messages: Array<{ messageId: string; role: "user" | "assistant" | "system"; content: string; createdAt: string }>;
  artifacts: Array<{ artifactId: string; label: string; createdAt: string; contentType: string }>;
  conversationState: {
    status: "awaiting_user" | "thinking" | "generating_report" | "failed";
    canGenerateReport: boolean;
    sourceFile?: { fileId: string; originalName: string };
    analysisSummary?: DiagnosisAnalysisSummary | null;
  } | null;
};

function statusLabel(session: DiagnosisDetail): string {
  if (session.status === "failed") return "실패";
  if (session.conversationState?.status === "generating_report") return "리포트 생성 중";
  if (session.conversationState?.status === "thinking") return "응답 생성 중";
  if (session.status === "processing") return "준비 중";
  return "대화 중";
}

export function DiagnosisSessionDetailPage({ sessionId }: { sessionId: string }) {
  const [session, setSession] = React.useState<DiagnosisDetail | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [draft, setDraft] = React.useState("");
  const [sending, setSending] = React.useState(false);
  const [generating, setGenerating] = React.useState(false);

  const load = React.useCallback(async () => {
    setError(null);
    try {
      const result = await apiFetch<{ session: DiagnosisDetail }>(`/api/diagnosis/sessions/${sessionId}`);
      setSession(result.session);
    } catch {
      setError("진단 세션을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function sendMessage() {
    const content = draft.trim();
    if (!content) return;

    setSending(true);
    setError(null);
    try {
      await apiFetch(`/api/diagnosis/sessions/${sessionId}/messages`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ content }),
      });
      setDraft("");
      await load();
    } catch {
      setError("답변을 전달하지 못했습니다.");
    } finally {
      setSending(false);
    }
  }

  async function generateReport() {
    setGenerating(true);
    setError(null);
    try {
      await apiFetch(`/api/diagnosis/sessions/${sessionId}/generate`, {
        method: "POST",
      });
      await load();
    } catch {
      setError("분석보고서를 생성하지 못했습니다.");
    } finally {
      setGenerating(false);
    }
  }

  async function downloadArtifact(artifactId: string) {
    try {
      const result = await apiFetch<{ url: string }>(
        `/api/diagnosis/sessions/${sessionId}/artifacts/${artifactId}`,
      );
      window.open(result.url, "_blank", "noopener,noreferrer");
    } catch {
      setError("결과물 다운로드 링크를 가져오지 못했습니다.");
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[320px] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-[#A68645]" />
      </div>
    );
  }

  if (error && !session) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        {error}
      </div>
    );
  }

  if (!session) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        진단 세션을 찾을 수 없습니다.
      </div>
    );
  }

  const analysis = session.conversationState?.analysisSummary ?? null;

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-6 py-10 md:px-10">
      <section className="rounded-[32px] border border-[#E2D6BA] bg-[#FFF9EE] p-8 shadow-[0_18px_40px_rgba(52,40,18,0.08)]">
        <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[#A68645]">
          {statusLabel(session)}
        </div>
        <h1 className="mt-3 text-3xl font-black tracking-tight text-[#231F16]">{session.title}</h1>
        <p className="mt-4 text-sm leading-7 text-[#6C624D]">
          원본 파일 {session.conversationState?.sourceFile?.originalName || session.originalFileName || "-"} · 작성자{" "}
          {session.createdBy}
        </p>
        {error ? (
          <div className="mt-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        ) : null}
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr]">
        <section className="rounded-[32px] border border-[#E2D6BA] bg-[#FFFDF7] p-6 shadow-[0_18px_40px_rgba(52,40,18,0.06)]">
          <div className="flex items-center justify-between gap-4 border-b border-[#EADFC7] pb-4">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[#A68645]">Conversation</div>
              <div className="mt-2 text-xl font-black tracking-tight text-[#231F16]">현황진단 Copilot</div>
            </div>
            <Button
              variant="secondary"
              disabled={!session.conversationState?.canGenerateReport || generating}
              onClick={() => void generateReport()}
            >
              {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              분석보고서 생성
            </Button>
          </div>

          <div className="mt-6 space-y-4">
            {session.messages.map((message) => (
              <article
                key={message.messageId}
                className={
                  message.role === "assistant"
                    ? "rounded-[24px] border border-[#E2D6BA] bg-[#FFF9EE] px-5 py-4"
                    : "rounded-[24px] border border-[#D7CFC0] bg-white px-5 py-4"
                }
              >
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#9E8350]">
                  {message.role === "assistant" ? "Merry Diagnosis" : "You"}
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[#30281D]">{message.content}</p>
              </article>
            ))}
          </div>

          <div className="mt-6 rounded-[24px] border border-[#E2D6BA] bg-white p-4">
            <label className="text-sm font-semibold text-[#5E5137]" htmlFor="diagnosis-reply">
              다음 답변
            </label>
            <textarea
              id="diagnosis-reply"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              rows={5}
              placeholder="예: 현재는 오프라인 리퍼럴 중심이고, CAC는 아직 따로 계산하지 못했습니다."
              className="mt-3 w-full resize-y rounded-2xl border border-[#E2D6BA] px-4 py-3 text-sm leading-6 text-[#231F16] outline-none focus:border-[#C89B38]"
              disabled={sending || generating}
            />
            <div className="mt-4 flex justify-end">
              <Button onClick={() => void sendMessage()} disabled={sending || generating || !draft.trim()}>
                {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                답변 보내기
              </Button>
            </div>
          </div>
        </section>

        <aside className="space-y-6">
          <section className="rounded-[32px] border border-[#E2D6BA] bg-[#FFF9EE] p-6 shadow-[0_18px_40px_rgba(52,40,18,0.08)]">
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[#A68645]">Snapshot</div>
            <div className="mt-4 space-y-3 text-sm leading-6 text-[#4C412E]">
              <div>기업명: {analysis?.companyName || "미상"}</div>
              <div>시트: {analysis?.sheets?.join(", ") || "없음"}</div>
              <div>갭 개수: {analysis?.gapCount ?? 0}</div>
            </div>
            {analysis?.scoreCards?.length ? (
              <div className="mt-5 grid gap-2">
                {analysis.scoreCards.slice(0, 4).map((card) => (
                  <div
                    key={card.category}
                    className="rounded-2xl border border-[#E8DDBF] bg-white px-4 py-3 text-sm text-[#5E5137]"
                  >
                    <div className="font-semibold">{card.category}</div>
                    <div className="mt-1">
                      점수 {card.score ?? "-"} / 예 비율 {card.yesRatePct ?? "-"}%
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
            {analysis?.sampleGaps?.length ? (
              <div className="mt-5 rounded-2xl border border-[#E8DDBF] bg-white px-4 py-4 text-sm leading-6 text-[#5E5137]">
                <div className="font-semibold text-[#6D5421]">확인 필요한 항목</div>
                <ul className="mt-2 space-y-2">
                  {analysis.sampleGaps.map((gap, index) => (
                    <li key={`${gap.module ?? "gap"}-${index}`}>
                      {(gap.module || "기타")}: {gap.question || gap.detail || "세부 확인 필요"}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>

          <section className="rounded-[32px] border border-[#E2D6BA] bg-[#FFF9EE] p-6 shadow-[0_18px_40px_rgba(52,40,18,0.08)]">
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[#A68645]">Artifacts</div>
            <div className="mt-4 flex flex-col gap-3">
              {session.artifacts.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-[#D8C59A] bg-[#FFFCF5] px-4 py-4 text-sm text-[#7C6E55]">
                  아직 생성된 결과물이 없습니다.
                </div>
              ) : (
                session.artifacts.map((artifact) => (
                  <Button
                    key={artifact.artifactId}
                    variant="secondary"
                    onClick={() => void downloadArtifact(artifact.artifactId)}
                  >
                    <FileDown className="h-4 w-4" />
                    {artifact.label} 다운로드
                  </Button>
                ))
              )}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
