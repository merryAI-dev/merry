"use client";

import Link from "next/link";
import * as React from "react";
import { useParams } from "next/navigation";
import { ArrowRight, FileText, RefreshCw, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { PresenceBar } from "@/components/report/PresenceBar";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Textarea";

type ReportSessionMeta = {
  sessionId: string;
  slug: string;
  title: string;
  createdAt?: string;
  fundId?: string;
  fundName?: string;
  companyId?: string;
  companyName?: string;
  reportDate?: string;
  fileTitle?: string;
  author?: string;
};

type ReportMessage = {
  role: "user" | "assistant";
  content: string;
  createdAt?: string;
  member?: string;
};

type DraftSummary = {
  draftId: string;
  title: string;
  createdAt?: string;
};

type ReportStashItem = {
  itemId: string;
  title: string;
  content: string;
  createdAt: string;
  createdBy?: string;
};

type JobType = "exit_projection" | "diagnosis_analysis" | "pdf_evidence" | "pdf_parse" | "contract_review";
type JobStatus = "queued" | "running" | "succeeded" | "failed";

type JobArtifact = {
  artifactId: string;
  label: string;
  contentType: string;
  s3Bucket: string;
  s3Key: string;
  sizeBytes?: number;
};

type JobRecord = {
  jobId: string;
  type: JobType;
  status: JobStatus;
  title: string;
  createdAt: string;
  artifacts?: JobArtifact[];
};

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.error || "FAILED");
  return json as T;
}

function badgeForJobStatus(status: JobStatus) {
  if (status === "succeeded") return <Badge tone="success">완료</Badge>;
  if (status === "failed") return <Badge tone="danger">실패</Badge>;
  if (status === "running") return <Badge tone="accent">진행 중</Badge>;
  return <Badge tone="neutral">대기</Badge>;
}

function scrollTo(id: string) {
  try {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch {
    // ignore
  }
}

export default function ReportSessionPage() {
  const params = useParams<{ slug: string }>();
  const slug = (params.slug ?? "").trim();
  const sessionId = `report_${slug}`;

  const [meta, setMeta] = React.useState<ReportSessionMeta | null>(null);
  const [messages, setMessages] = React.useState<ReportMessage[]>([]);
  const [prompt, setPrompt] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [sending, setSending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [stash, setStash] = React.useState<ReportStashItem[]>([]);
  const [stashBusy, setStashBusy] = React.useState(false);
  const [stashMsg, setStashMsg] = React.useState<string | null>(null);

  const [drafts, setDrafts] = React.useState<DraftSummary[]>([]);
  const [activeDraftId, setActiveDraftId] = React.useState<string>("");
  const [jobs, setJobs] = React.useState<JobRecord[]>([]);
  const [recBusy, setRecBusy] = React.useState(false);
  const [recMsg, setRecMsg] = React.useState<string | null>(null);
  const [autoImportEvidence, setAutoImportEvidence] = React.useState(false);
  const autoImportedJobsRef = React.useRef(new Set<string>());

  const loadMeta = React.useCallback(async () => {
    try {
      const res = await fetchJson<{ session: ReportSessionMeta }>(`/api/report/${sessionId}/meta`);
      setMeta(res.session);
    } catch {
      setMeta(null);
    }
  }, [sessionId]);

  const loadMessages = React.useCallback(async () => {
    setError(null);
    try {
      const res = await fetchJson<{ messages: ReportMessage[] }>(`/api/report/${sessionId}/messages`);
      setMessages(res.messages || []);
    } catch {
      setError("메시지를 불러오지 못했습니다.");
    }
  }, [sessionId]);

  const loadStash = React.useCallback(async () => {
    try {
      const res = await fetchJson<{ items: ReportStashItem[] }>(`/api/report/${sessionId}/stash`);
      setStash(res.items || []);
    } catch {
      setStash([]);
    }
  }, [sessionId]);

  React.useEffect(() => {
    loadMeta();
    loadMessages();
    loadStash();
  }, [loadMeta, loadMessages, loadStash]);

  const loadDrafts = React.useCallback(async () => {
    try {
      const res = await fetchJson<{ drafts: DraftSummary[] }>("/api/drafts");
      const list = res.drafts || [];
      setDrafts(list);
      if (!activeDraftId && list[0]?.draftId) setActiveDraftId(list[0].draftId);
    } catch {
      setDrafts([]);
    }
  }, [activeDraftId]);

  const loadJobs = React.useCallback(async () => {
    try {
      const res = await fetchJson<{ jobs: JobRecord[] }>("/api/jobs");
      setJobs(res.jobs || []);
    } catch {
      setJobs([]);
    }
  }, []);

  React.useEffect(() => {
    loadDrafts();
    loadJobs();
  }, [loadDrafts, loadJobs]);

  React.useEffect(() => {
    try {
      const raw = localStorage.getItem("merry:autoImportEvidence");
      if (raw === "1") setAutoImportEvidence(true);
    } catch {
      // ignore
    }
  }, []);

  React.useEffect(() => {
    try {
      localStorage.setItem("merry:autoImportEvidence", autoImportEvidence ? "1" : "0");
    } catch {
      // ignore
    }
  }, [autoImportEvidence]);

  async function sendMessage(message: string) {
    const text = message.trim();
    if (!text || sending) return;

    setSending(true);
    setError(null);

    const optimisticUser: ReportMessage = {
      role: "user",
      content: text,
      createdAt: new Date().toISOString(),
    };
    const optimisticAssistant: ReportMessage = {
      role: "assistant",
      content: "",
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUser, optimisticAssistant]);
    setPrompt("");

    try {
      const res = await fetch("/api/report/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId, message: text }),
      });

      if (!res.ok) {
        const json = await res.json().catch(() => ({}));
        throw new Error(json?.error || "FAILED");
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("NO_STREAM");

      const decoder = new TextDecoder("utf-8");
      let acc = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        acc += chunk;
        setMessages((prev) => {
          const next = [...prev];
          const idx = next.findLastIndex((m) => m.role === "assistant");
          if (idx >= 0) next[idx] = { ...next[idx], content: acc };
          return next;
        });
      }

      await loadMessages();
    } catch {
      setError("전송/생성에 실패했습니다. Bedrock/LLM 환경변수와 모델 접근 권한을 확인하세요.");
    } finally {
      setSending(false);
    }
  }

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant" && m.content.trim());

  async function addToStash(content: string, source?: Record<string, unknown>) {
    const text = (content ?? "").trim();
    if (!text) return;
    if (stashBusy) return;
    setStashBusy(true);
    setStashMsg(null);
    try {
      const res = await fetchJson<{ itemId: string; alreadyExists?: boolean }>(`/api/report/${sessionId}/stash`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ content: text, source }),
      });
      setStashMsg(res.alreadyExists ? "이미 바구니에 담긴 초안입니다." : "초안을 바구니에 담았습니다.");
      await loadStash();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "FAILED";
      if (msg === "UNAUTHORIZED") {
        setStashMsg("로그인이 필요합니다. 다시 로그인 후 시도하세요.");
      } else {
        setStashMsg(`초안을 바구니에 담지 못했습니다. (${msg})`);
      }
    } finally {
      setStashBusy(false);
    }
  }

  async function removeFromStash(itemId: string) {
    const id = (itemId ?? "").trim();
    if (!id) return;
    if (stashBusy) return;
    setStashBusy(true);
    setStashMsg(null);
    try {
      await fetchJson(`/api/report/${sessionId}/stash/${id}`, { method: "DELETE" });
      await loadStash();
      setStashMsg("바구니에서 제거했습니다.");
    } catch {
      setStashMsg("제거에 실패했습니다.");
    } finally {
      setStashBusy(false);
    }
  }

  async function commitStashToDraft() {
    if (!stash.length) return;
    if (stashBusy || busy) return;
    setBusy(true);
    setStashMsg(null);
    try {
      const now = new Date();
      const stamp = now.toISOString().slice(0, 16).replace("T", " ");
      const baseTitle = meta?.companyName ? `투자심사 보고서 - ${meta.companyName}` : meta?.title || "투자심사 보고서";
      const title = activeDraftId.trim()
        ? `초안 확정(${stash.length}파트) · ${stamp}`
        : `${baseTitle} · 초안 확정(${stash.length}파트)`;

      const res = await fetchJson<{ draftId: string }>(`/api/report/${sessionId}/stash/commit`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ draftId: activeDraftId.trim() || undefined, title }),
      });
      await loadDrafts();
      await loadStash();
      window.location.href = `/drafts/${res.draftId}`;
    } catch {
      setStashMsg("드래프트 반영(커밋)에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function importEvidenceToDraft(job: JobRecord) {
    const draftId = activeDraftId.trim();
    if (!draftId) {
      setRecMsg("대상 드래프트를 먼저 선택하세요.");
      return;
    }
    setRecBusy(true);
    setRecMsg(null);
    try {
      const artifactId =
        (job.artifacts || []).find((a) => a.artifactId === "pdf_evidence_json")?.artifactId ??
        (job.artifacts || [])[0]?.artifactId ??
        undefined;
      const res = await fetchJson<{ versionId: string; alreadyImported?: boolean }>(`/api/drafts/${draftId}/import-evidence`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ jobId: job.jobId, artifactId }),
      });
      setRecMsg(res.alreadyImported ? "이미 이 근거는 드래프트에 반영되었습니다." : "근거를 드래프트 버전으로 저장했습니다.");
    } catch {
      setRecMsg("근거 반영에 실패했습니다. 잡 상태/아티팩트를 확인하세요.");
    } finally {
      setRecBusy(false);
    }
  }

  const evidenceJobs = React.useMemo(() => {
    const list = (jobs || [])
      .filter((j) => j.type === "pdf_evidence")
      .slice()
      .sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""));
    return list.slice(0, 6);
  }, [jobs]);

  React.useEffect(() => {
    if (!autoImportEvidence) return;
    if (!activeDraftId.trim()) return;
    if (recBusy) return;

    const newest = evidenceJobs.find(
      (j) =>
        j.status === "succeeded" &&
        (j.artifacts || []).some((a) => a.artifactId === "pdf_evidence_json"),
    );
    if (!newest) return;
    if (autoImportedJobsRef.current.has(newest.jobId)) return;
    autoImportedJobsRef.current.add(newest.jobId);
    importEvidenceToDraft(newest);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoImportEvidence, activeDraftId, evidenceJobs]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-medium text-[color:var(--muted)]">Investment Report</div>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <h1 className="min-w-0 truncate font-[family-name:var(--font-display)] text-3xl tracking-tight text-[color:var(--ink)]">
              {meta?.title ?? "투자심사 보고서"}
            </h1>
            <Badge tone="accent">스트리밍</Badge>
          </div>
          <div className="mt-2 text-sm text-[color:var(--muted)]">
            필요한 답변을 &quot;초안 확정&quot;으로 담고, 여러 파트를 한 번에 드래프트로 옮겨 리뷰합니다.
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Link href="/report" className="inline-flex">
            <Button variant="secondary">세션 목록</Button>
          </Link>
          <Link href="/report/new" className="inline-flex">
            <Button variant="secondary">새 보고서</Button>
          </Link>
          <Button variant="secondary" onClick={() => { loadMeta(); loadMessages(); loadStash(); }} disabled={busy}>
            <RefreshCw className="h-4 w-4" />
            새로고침
          </Button>
          <Button
            variant="primary"
            onClick={() => (lastAssistant ? addToStash(lastAssistant.content, { kind: "last_assistant" }) : null)}
            disabled={busy || stashBusy || !lastAssistant}
          >
            <FileText className="h-4 w-4" />
            마지막 답변 초안 확정
          </Button>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 backdrop-blur-sm px-4 py-3 text-sm text-rose-300 shadow-[0_0_20px_rgba(244,63,94,0.15)]">
          {error}
        </div>
      ) : null}

      <Card variant="strong" className="p-5" id="step-info">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-[color:var(--ink)]">세션 정보</div>
            <div className="mt-1 text-sm text-[color:var(--muted)]">
              팀 히스토리는 AWS(DynamoDB)에 저장됩니다.
            </div>
          </div>
          <div className="min-w-[14rem]">
            <PresenceBar sessionId={sessionId} />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => scrollTo("step-info")}>1. 정보</Button>
          <Button variant="ghost" size="sm" onClick={() => scrollTo("step-evidence")}>2. 근거</Button>
          <Button variant="ghost" size="sm" onClick={() => scrollTo("step-write")}>3. 작성</Button>
          <Button variant="ghost" size="sm" onClick={() => scrollTo("step-confirm")}>4. 확정</Button>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-4 text-sm">
            <div className="text-xs font-semibold text-[color:var(--ink)]">기업</div>
            <div className="mt-1 text-[color:var(--ink)]">{meta?.companyName || "—"}</div>
            {meta?.companyId ? (
              <div className="mt-2 text-xs text-[color:var(--muted)]">
                <Link href={`/companies/${meta.companyId}${meta.fundId ? `?fundId=${encodeURIComponent(meta.fundId)}` : ""}`} className="underline underline-offset-4 hover:no-underline">
                  기업 상세 열기
                </Link>
              </div>
            ) : null}
          </div>
          <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-4 text-sm">
            <div className="text-xs font-semibold text-[color:var(--ink)]">메타데이터</div>
            <div className="mt-2 grid gap-1 text-xs text-[color:var(--muted)]">
              <div>작성자: <span className="text-[color:var(--ink)]">{meta?.author || "—"}</span></div>
              <div>작성일: <span className="text-[color:var(--ink)]">{meta?.reportDate || "—"}</span></div>
              <div>파일 제목: <span className="text-[color:var(--ink)]">{meta?.fileTitle || meta?.title || "—"}</span></div>
              <div>펀드: <span className="text-[color:var(--ink)]">{meta?.fundName || meta?.fundId || "—"}</span></div>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[1.65fr_1fr]">
        <Card variant="strong" className="p-0" id="step-write">
          <div className="border-b border-[color:var(--line)] px-5 py-4">
            <div className="text-sm font-semibold text-[color:var(--ink)]">대화</div>
            <div className="mt-1 text-sm text-[color:var(--muted)]">답변은 Markdown 초안 형태로 생성됩니다.</div>
          </div>

          <div className="max-h-[720px] space-y-3 overflow-auto px-5 py-5">
            {messages.length ? (
              messages.map((m, idx) => (
                <div key={idx} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
                  <div
                    className={
                      m.role === "user"
                        ? "max-w-[84%] rounded-2xl bg-gradient-to-br from-[color:var(--accent-purple)]/20 to-[color:var(--accent-cyan)]/20 border border-[color:var(--accent-purple)]/30 backdrop-blur-sm px-4 py-3 text-sm text-[color:var(--ink)] shadow-[0_0_15px_rgba(30,64,175,0.1)]"
                        : "max-w-[84%] rounded-2xl border border-[color:var(--line)] bg-[color:var(--card)]/80 backdrop-blur-md px-4 py-3 text-sm text-[color:var(--ink)] shadow-sm"
                    }
                  >
                    {m.role === "assistant" ? (
                      <article className="prose prose-zinc max-w-none prose-headings:font-[family-name:var(--font-display)] prose-p:text-[color:var(--ink)] prose-li:text-[color:var(--ink)] prose-strong:text-[color:var(--ink)] prose-a:text-[color:var(--accent-cyan)] prose-a:underline prose-a:underline-offset-4 hover:prose-a:no-underline">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                      </article>
                    ) : (
                      <div className="whitespace-pre-wrap">{m.content}</div>
                    )}
                    {m.role === "assistant" && m.content.trim() ? (
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => addToStash(m.content, { kind: "assistant_message", createdAt: m.createdAt || "" })}
                          disabled={stashBusy || busy || sending}
                        >
                          초안 확정
                        </Button>
                        {stash.some((it) => it.content.trim() === m.content.trim()) ? (
                          <Badge tone="neutral">바구니 담김</Badge>
                        ) : null}
                      </div>
                    ) : null}
                    <div className="mt-2 text-[10px] text-black/40">
                      {m.role === "user" ? "you" : "merry"} · {m.createdAt?.slice(0, 16).replace("T", " ") || ""}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-[color:var(--line)] bg-white/60 p-4 text-sm text-[color:var(--muted)]">
                시작 프롬프트 예시를 눌러 대화를 시작하세요.
              </div>
            )}
          </div>

          <div className="border-t border-[color:var(--line)] px-5 py-4">
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                onClick={() => sendMessage("시장규모/성장률 근거를 정리해줘. 근거가 없으면 필요한 자료를 질문해줘.")}
                disabled={sending}
              >
                시장규모 근거
              </Button>
              <Button
                variant="secondary"
                onClick={() => sendMessage("인수인의견 스타일로 투자심사 보고서 초안 문단을 작성해줘. 부족한 정보는 질문해줘.")}
                disabled={sending}
              >
                인수인의견 초안
              </Button>
              <Button
                variant="secondary"
                onClick={() => sendMessage("시장규모 근거 요약 + 투자심사 보고서 초안(인수인의견 스타일)을 한 번에 작성해줘. 부족한 정보는 질문해줘.")}
                disabled={sending}
              >
                근거+초안
              </Button>
              <Button
                variant="secondary"
                onClick={() => sendMessage("리스크 섹션을 더 날카롭게 써줘. 법무/재무/사업/시장 측면으로 나눠줘.")}
                disabled={sending}
              >
                리스크 강화
              </Button>
            </div>

            <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_auto]">
              <Textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="보고서 작성 관련 질문..."
                className="min-h-24"
                disabled={sending}
              />
              <Button
                variant="primary"
                onClick={() => sendMessage(prompt)}
                disabled={sending || !prompt.trim()}
              >
                {sending ? (
                  <>
                    <Sparkles className="h-4 w-4 animate-pulse" />
                    생성 중
                  </>
                ) : (
                  <>
                    전송 <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </div>
          </div>
        </Card>

        <Card variant="strong" className="p-5">
          <div className="text-sm font-semibold text-[color:var(--ink)]" id="step-confirm">초안 바구니</div>
          <div className="mt-1 text-sm text-[color:var(--muted)]">
            확정된 초안을 모아 한 번에 드래프트로 옮기고, 커서식 리뷰(수정/좋음/대안)를 시작합니다.
          </div>

          <div className="mt-4 space-y-3">
            <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-4">
              <div className="flex items-center justify-between gap-2">
                <div className="text-xs font-semibold text-[color:var(--ink)]">확정된 초안</div>
                <Button variant="ghost" onClick={loadStash} disabled={stashBusy}>
                  새로고침
                </Button>
              </div>

              {stashMsg ? (
                <div className="mt-3 rounded-xl border border-[color:var(--line)] bg-white/80 px-3 py-2 text-xs text-[color:var(--muted)]">
                  {stashMsg}
                </div>
              ) : null}

              <div className="mt-3 space-y-2">
                {!stash.length ? (
                  <div className="text-sm text-[color:var(--muted)]">
                    아직 바구니에 담긴 초안이 없습니다. 대화 메시지에서 &quot;초안 확정&quot;을 눌러 담아보세요.
                  </div>
                ) : (
                  stash.map((it) => (
                    <div key={it.itemId} className="rounded-2xl border border-[color:var(--line)] bg-white/80 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium text-[color:var(--ink)]">{it.title}</div>
                          <div className="mt-1 flex items-center justify-between gap-2 text-xs text-[color:var(--muted)]">
                            <span className="font-mono">{it.itemId}</span>
                            <span>{(it.createdAt || "").slice(0, 16).replace("T", " ")}</span>
                          </div>
                          <div className="mt-2 line-clamp-3 text-xs text-[color:var(--muted)]">
                            {(it.content || "").trim().slice(0, 180)}
                          </div>
                        </div>
                        <Button variant="ghost" size="sm" disabled={stashBusy} onClick={() => removeFromStash(it.itemId)}>
                          제거
                        </Button>
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                <div className="text-xs text-[color:var(--muted)]">{stash.length ? `${stash.length}개 파트 확정됨` : "0개"}</div>
                <Button variant="primary" disabled={!stash.length || busy || stashBusy} onClick={commitStashToDraft}>
                  드래프트로 옮기기
                </Button>
              </div>
            </div>

            <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-4" id="step-evidence">
              <div className="text-xs font-semibold text-[color:var(--ink)]">대상 드래프트</div>
              <div className="mt-2 grid gap-2">
                <select
                  className="h-11 w-full rounded-xl border border-[color:var(--line)] bg-white/80 px-3 text-sm text-[color:var(--ink)] outline-none focus:border-[color:var(--accent)]"
                  value={activeDraftId}
                  onChange={(e) => setActiveDraftId(e.target.value)}
                >
                  <option value="">드래프트 선택…</option>
                  {drafts.map((d) => (
                    <option key={d.draftId} value={d.draftId}>
                      {d.title} · {d.createdAt?.slice(0, 16).replace("T", " ") || d.draftId}
                    </option>
                  ))}
                </select>
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[color:var(--muted)]">
                  <span>근거 결과는 새 버전으로 저장됩니다.</span>
                  {activeDraftId ? (
                    <Link href={`/drafts/${activeDraftId}`} className="text-[color:var(--ink)] underline underline-offset-4 hover:no-underline">
                      드래프트 열기
                    </Link>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-4">
              <div className="flex items-center justify-between gap-2">
                <div className="text-xs font-semibold text-[color:var(--ink)]">PDF 근거 → 드래프트 버전</div>
                <Button variant="ghost" onClick={loadJobs} disabled={recBusy}>
                  새로고침
                </Button>
              </div>

              <div className="mt-2 flex items-center gap-2 text-xs text-[color:var(--muted)]">
                <label className="inline-flex items-center gap-2">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-[color:var(--line)]"
                    checked={autoImportEvidence}
                    onChange={(e) => setAutoImportEvidence(e.target.checked)}
                    disabled={!activeDraftId}
                  />
                  완료 시 자동 저장
                </label>
                <span className="text-[color:var(--muted)]">·</span>
                <Link href="/analysis" className="text-[color:var(--ink)] underline underline-offset-4 hover:no-underline">
                  근거 추출 잡 실행
                </Link>
              </div>

              {recMsg ? (
                <div className="mt-3 rounded-xl border border-[color:var(--line)] bg-white/80 px-3 py-2 text-xs text-[color:var(--muted)]">
                  {recMsg}
                </div>
              ) : null}

              <div className="mt-3 space-y-2">
                {!evidenceJobs.length ? (
                  <div className="text-sm text-[color:var(--muted)]">최근 PDF 근거 추출 잡이 없습니다. 먼저 잡을 생성하세요.</div>
                ) : (
                  evidenceJobs.map((j) => {
                    const ready =
                      j.status === "succeeded" &&
                      (j.artifacts || []).some((a) => a.artifactId === "pdf_evidence_json");
                    return (
                      <div key={j.jobId} className="rounded-2xl border border-[color:var(--line)] bg-white/80 p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-medium text-[color:var(--ink)]">{j.title}</div>
                            <div className="mt-1 flex items-center justify-between gap-2 text-xs text-[color:var(--muted)]">
                              <span className="font-mono">{j.jobId}</span>
                              {badgeForJobStatus(j.status)}
                            </div>
                          </div>
                          <Button variant="secondary" disabled={!ready || recBusy || !activeDraftId} onClick={() => importEvidenceToDraft(j)}>
                            드래프트 저장
                          </Button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-4 text-sm text-[color:var(--muted)]">
              <div className="text-xs font-semibold text-[color:var(--ink)]">다음 연결</div>
              <div className="mt-2">
                - PDF/엑셀 업로드 → 근거 추출<br />
                - DART 인수인의견 데이터셋 검색<br />
                - 심화 의견(딥 옵피니언) 파이프라인<br />
                - 결과를 자동으로 드래프트 버전으로 저장
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
