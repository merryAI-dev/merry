"use client";

import Link from "next/link";
import * as React from "react";
import { useParams } from "next/navigation";
import { ArrowRight, FileText, PanelRightClose, PanelRightOpen, RefreshCw, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { PresenceBar } from "@/components/report/PresenceBar";
import { FactsAssumptionsPanel } from "@/components/report/FactsAssumptionsPanel";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Textarea";
import { apiFetch } from "@/lib/apiClient";

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
  section?: {
    key: string;
    title: string;
    index?: number;
  };
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
  source?: Record<string, unknown>;
};

type TocSection = {
  key: string;
  index: number;
  title: string;
  hint?: string;
};

const TOC_SECTIONS: TocSection[] = [
  { key: "executive_summary", index: 1, title: "Executive Summary (요약)" },
  { key: "company_overview", index: 2, title: "회사 개요" },
  { key: "market_competition", index: 3, title: "시장/경쟁" },
  { key: "gtm_b2g", index: 4, title: "B2G/조달 전략" },
  { key: "investment_points", index: 5, title: "투자 포인트" },
  { key: "risks", index: 6, title: "리스크 (법무/재무/사업/시장)" },
];

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

function sectionLabel(section?: { title: string; index?: number }): string | null {
  if (!section || !section.title) return null;
  const idx = typeof section.index === "number" ? `${section.index}. ` : "";
  return `${idx}${section.title}`.trim();
}

function stashSectionIndex(it: ReportStashItem): number | null {
  const src = it.source;
  if (!src || typeof src !== "object") return null;
  const idx = (src as Record<string, unknown>)["sectionIndex"];
  return typeof idx === "number" && Number.isFinite(idx) ? idx : null;
}

function stashSectionKey(it: ReportStashItem): string | null {
  const src = it.source;
  if (!src || typeof src !== "object") return null;
  const key = (src as Record<string, unknown>)["sectionKey"];
  return typeof key === "string" && key.trim() ? key.trim() : null;
}

function buildSectionPrompt(section: TocSection, meta: ReportSessionMeta | null): string {
  const company = meta?.companyName ? `- 회사명: ${meta.companyName}\n` : "";
  const author = meta?.author ? `- 작성자: ${meta.author}\n` : "";
  const reportDate = meta?.reportDate ? `- 작성일: ${meta.reportDate}\n` : "";
  const fileTitle = meta?.fileTitle ? `- 파일 제목: ${meta.fileTitle}\n` : "";
  const fund = meta?.fundName ? `- 펀드: ${meta.fundName}\n` : meta?.fundId ? `- 펀드: ${meta.fundId}\n` : "";
  const context = `${company}${author}${reportDate}${fileTitle}${fund}`.trim();

  const extra =
    section.key === "gtm_b2g"
      ? "\n특히 아래 항목을 구체적으로 포함:\n- B2G 시장 진입 전략\n- 조달청 계약 전략(조달 프로세스 관점)\n- 실증(PoC) 모델 설계(교육기관/지자체 대상으로 확장)\n- 글로벌 정신건강 플랫폼과 파트너십 탐색 포인트\n"
      : "";

  return (
    `다음 목차만 작성해줘: ${section.index}. ${section.title}\n` +
    (context ? `\n컨텍스트(있으면 반영):\n${context}\n` : "\n") +
    "\n규칙:\n" +
    `- 제목은 반드시 \"## ${section.index}. ${section.title}\"로 시작\n` +
    "- 다른 목차/섹션은 작성하지 말 것\n" +
    "- 근거 없는 숫자/사실은 [확인 필요]로 두고, 마지막에 질문 3-5개만 추가\n" +
    "- 길게 늘어놓지 말고, 1-2페이지 분량으로 압축\n" +
    extra
  );
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
  const sendingRef = React.useRef(false);
  const [error, setError] = React.useState<string | null>(null);
  const [genAllLabel, setGenAllLabel] = React.useState<string | null>(null);

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
  const [panelOpen, setPanelOpen] = React.useState(true);

  React.useEffect(() => {
    const saved = localStorage.getItem("merry:report-panel");
    if (saved === "0") setPanelOpen(false);
  }, []);

  function togglePanel() {
    setPanelOpen((prev) => {
      const next = !prev;
      localStorage.setItem("merry:report-panel", next ? "1" : "0");
      return next;
    });
  }

  const loadMeta = React.useCallback(async () => {
    try {
      const res = await apiFetch<{ session: ReportSessionMeta }>(`/api/report/${sessionId}/meta`);
      setMeta(res.session);
    } catch {
      setMeta(null);
    }
  }, [sessionId]);

  const loadMessages = React.useCallback(async () => {
    setError(null);
    try {
      const res = await apiFetch<{ messages: ReportMessage[] }>(`/api/report/${sessionId}/messages`);
      setMessages(res.messages || []);
    } catch {
      setError("메시지를 불러오지 못했습니다.");
    }
  }, [sessionId]);

  const loadStash = React.useCallback(async () => {
    try {
      const res = await apiFetch<{ items: ReportStashItem[] }>(`/api/report/${sessionId}/stash`);
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
      const res = await apiFetch<{ drafts: DraftSummary[] }>("/api/drafts");
      const list = res.drafts || [];
      setDrafts(list);
      if (!activeDraftId && list[0]?.draftId) setActiveDraftId(list[0].draftId);
    } catch {
      setDrafts([]);
    }
  }, [activeDraftId]);

  const loadJobs = React.useCallback(async () => {
    try {
      const res = await apiFetch<{ jobs: JobRecord[] }>("/api/jobs");
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

  async function sendMessage(message: string, section?: TocSection): Promise<string> {
    const text = message.trim();
    if (!text || sendingRef.current) return "";

    sendingRef.current = true;
    setSending(true);
    setError(null);

    const sectionMeta = section
      ? { key: section.key, title: section.title, index: section.index }
      : undefined;

    const optimisticUser: ReportMessage = {
      role: "user",
      content: text,
      createdAt: new Date().toISOString(),
      section: sectionMeta,
    };
    const optimisticAssistant: ReportMessage = {
      role: "assistant",
      content: "",
      createdAt: new Date().toISOString(),
      section: sectionMeta,
    };
    setMessages((prev) => [...prev, optimisticUser, optimisticAssistant]);
    setPrompt("");

    let acc = "";
    try {
      const res = await fetch("/api/report/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId, message: text, section: sectionMeta }),
      });

      if (!res.ok) {
        const json = await res.json().catch(() => ({}));
        throw new Error(json?.error || "FAILED");
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("NO_STREAM");

      const decoder = new TextDecoder("utf-8");

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
      sendingRef.current = false;
      setSending(false);
    }
    return acc;
  }

  async function generateAll() {
    if (sendingRef.current) return;
    for (let i = 0; i < TOC_SECTIONS.length; i++) {
      const sec = TOC_SECTIONS[i];
      if (stashSectionKeys.has(sec.key)) continue;
      setGenAllLabel(`${i + 1}/${TOC_SECTIONS.length}`);
      const content = await sendMessage(buildSectionPrompt(sec, meta), sec);
      if (content && content.trim()) {
        await addToStash(content, {
          title: `${sec.index}. ${sec.title}`,
          source: {
            kind: "assistant_message",
            sectionKey: sec.key,
            sectionTitle: sec.title,
            sectionIndex: sec.index,
          },
        });
      }
    }
    setGenAllLabel(null);
  }

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant" && m.content.trim());

  async function addToStash(content: string, opts?: { title?: string; source?: Record<string, unknown> }) {
    const text = (content ?? "").trim();
    if (!text) return;
    if (stashBusy) return;
    setStashBusy(true);
    setStashMsg(null);
    try {
      const res = await apiFetch<{ itemId: string; alreadyExists?: boolean }>(`/api/report/${sessionId}/stash`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ content: text, title: opts?.title, source: opts?.source }),
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
      await apiFetch(`/api/report/${sessionId}/stash/${id}`, { method: "DELETE" });
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
      const ordered = [...stash].sort((a, b) => {
        const ai = stashSectionIndex(a);
        const bi = stashSectionIndex(b);
        if (ai != null && bi != null) return ai - bi;
        if (ai != null) return -1;
        if (bi != null) return 1;
        return (a.createdAt || "").localeCompare(b.createdAt || "");
      });

      const now = new Date();
      const stamp = now.toISOString().slice(0, 16).replace("T", " ");
      const baseTitle = meta?.companyName ? `투자심사 보고서 - ${meta.companyName}` : meta?.title || "투자심사 보고서";
      const title = activeDraftId.trim()
        ? `초안 확정(${stash.length}파트) · ${stamp}`
        : `${baseTitle} · 초안 확정(${stash.length}파트)`;

      const res = await apiFetch<{ draftId: string }>(`/api/report/${sessionId}/stash/commit`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ draftId: activeDraftId.trim() || undefined, title, itemIds: ordered.map((it) => it.itemId) }),
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
      const res = await apiFetch<{ versionId: string; alreadyImported?: boolean }>(`/api/drafts/${draftId}/import-evidence`, {
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

  const stashSectionKeys = React.useMemo(() => {
    const keys = new Set<string>();
    for (const it of stash) {
      const key = stashSectionKey(it);
      if (key) keys.add(key);
    }
    return keys;
  }, [stash]);

  const orderedStash = React.useMemo(() => {
    return [...stash].sort((a, b) => {
      const ai = stashSectionIndex(a);
      const bi = stashSectionIndex(b);
      if (ai != null && bi != null) return ai - bi;
      if (ai != null) return -1;
      if (bi != null) return 1;
      return (a.createdAt || "").localeCompare(b.createdAt || "");
    });
  }, [stash]);

  const streamingAssistantIndex = sending ? messages.findLastIndex((m) => m.role === "assistant") : -1;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[12px] font-semibold uppercase tracking-widest text-[#8B95A1]">Investment Report</div>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <h1 className="min-w-0 truncate text-2xl font-black tracking-tight text-[#191F28]">
              {meta?.title ?? "투자심사 보고서"}
            </h1>
            <Badge tone="accent">스트리밍</Badge>
          </div>
          <div className="mt-1 text-[13px] text-[#8B95A1]">
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
          <Button variant="secondary" onClick={togglePanel} title={panelOpen ? "패널 접기" : "패널 열기"}>
            {panelOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
          </Button>
          <Button
            variant="primary"
            onClick={() =>
              lastAssistant
                ? addToStash(lastAssistant.content, {
                    title: sectionLabel(lastAssistant.section) || "마지막 답변",
                    source: {
                      kind: "last_assistant",
                      ...(lastAssistant.section
                        ? {
                            sectionKey: lastAssistant.section.key,
                            sectionTitle: lastAssistant.section.title,
                            ...(typeof lastAssistant.section.index === "number" ? { sectionIndex: lastAssistant.section.index } : {}),
                          }
                        : {}),
                      ...(lastAssistant.createdAt ? { assistantCreatedAt: lastAssistant.createdAt } : {}),
                    },
                  })
                : null
            }
            disabled={busy || stashBusy || sending || !lastAssistant}
          >
            <FileText className="h-4 w-4" />
            마지막 답변 초안 확정
          </Button>
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="rounded-2xl bg-white p-5" style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px #E5E8EB" }} id="step-info">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[14px] font-bold text-[#191F28]">세션 정보</div>
            <div className="mt-0.5 text-[12px] text-[#8B95A1]">
              팀 히스토리는 AWS(DynamoDB)에 저장됩니다.
            </div>
          </div>
          <div className="min-w-[14rem]">
            <PresenceBar sessionId={sessionId} />
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <Button variant="ghost" size="sm" onClick={() => scrollTo("step-info")}>1. 정보</Button>
          <Button variant="ghost" size="sm" onClick={() => scrollTo("step-evidence")}>2. 근거</Button>
          <Button variant="ghost" size="sm" onClick={() => scrollTo("step-write")}>3. 작성</Button>
          <Button variant="ghost" size="sm" onClick={() => scrollTo("step-confirm")}>4. 확정</Button>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className="rounded-xl border border-[#E5E8EB] bg-[#F8F9FA] p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-[#8B95A1]">기업</div>
            <div className="mt-1.5 text-[14px] font-semibold text-[#191F28]">{meta?.companyName || "—"}</div>
            {meta?.companyId ? (
              <div className="mt-2 text-[12px]">
                <Link href={`/companies/${meta.companyId}${meta.fundId ? `?fundId=${encodeURIComponent(meta.fundId)}` : ""}`} className="text-[#3182F6] underline underline-offset-4 hover:no-underline">
                  기업 상세 열기
                </Link>
              </div>
            ) : null}
          </div>
          <div className="rounded-xl border border-[#E5E8EB] bg-[#F8F9FA] p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-[#8B95A1]">메타데이터</div>
            <div className="mt-1.5 grid gap-1 text-[12px]">
              <div><span className="text-[#8B95A1]">작성자 </span><span className="font-medium text-[#191F28]">{meta?.author || "—"}</span></div>
              <div><span className="text-[#8B95A1]">작성일 </span><span className="font-medium text-[#191F28]">{meta?.reportDate || "—"}</span></div>
              <div><span className="text-[#8B95A1]">파일 제목 </span><span className="font-medium text-[#191F28]">{meta?.fileTitle || meta?.title || "—"}</span></div>
              <div><span className="text-[#8B95A1]">펀드 </span><span className="font-medium text-[#191F28]">{meta?.fundName || meta?.fundId || "—"}</span></div>
            </div>
          </div>
        </div>
      </div>

      <div className={panelOpen ? "grid gap-6 lg:grid-cols-[2fr_1fr]" : ""}>
        <div className="rounded-2xl bg-white p-0 overflow-hidden" style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px #E5E8EB" }} id="step-write">
          <div className="border-b border-[#F2F4F6] px-5 py-4">
            <div className="text-[14px] font-bold text-[#191F28]">대화</div>
            <div className="mt-0.5 text-[12px] text-[#8B95A1]">답변은 Markdown 초안 형태로 생성됩니다.</div>
          </div>

          <div className="border-b border-[#F2F4F6] px-5 py-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-[12px] font-bold text-[#191F28]">목차별 생성</div>
              <div className="text-[11.5px] text-[#8B95A1]">섹션을 하나씩 생성하고, 마음에 들면 &quot;초안 확정&quot;으로 담으세요.</div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {TOC_SECTIONS.map((sec) => {
                const confirmed = stashSectionKeys.has(sec.key);
                return (
                  <Button
                    key={sec.key}
                    variant={confirmed ? "ghost" : "secondary"}
                    size="sm"
                    onClick={() => sendMessage(buildSectionPrompt(sec, meta), sec)}
                    disabled={sending}
                  >
                    {sec.index}. {sec.title}
                    {confirmed ? <Badge tone="success">확정됨</Badge> : null}
                  </Button>
                );
              })}
              <Button
                variant="primary"
                size="sm"
                onClick={generateAll}
                disabled={sending || genAllLabel !== null}
              >
                {genAllLabel ? `생성 중 ${genAllLabel}` : "전체 초안 생성"}
              </Button>
            </div>
          </div>

          <div className="max-h-[calc(100vh-22rem)] min-h-[400px] space-y-3 overflow-auto px-5 py-5">
            {messages.length ? (
              messages.map((m, idx) => (
                <div key={idx} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
                  <div
                    className={
                      m.role === "user"
                        ? "max-w-[84%] rounded-2xl bg-[#EBF3FF] border border-[#C0D8FF] px-4 py-3 text-sm text-[#191F28]"
                        : "max-w-[84%] rounded-2xl border border-[#E5E8EB] bg-white px-4 py-3 text-sm text-[#191F28]"
                    }
                  >
                    {m.role === "assistant" ? (
                      <>
                        {m.section ? (
                          <div className="mb-2 text-[11px] font-semibold text-[#8B95A1]">
                            {sectionLabel(m.section) || ""}
                          </div>
                        ) : null}
                        {sending && idx === streamingAssistantIndex ? (
                          <div className="whitespace-pre-wrap">{m.content}</div>
                        ) : (
                          <article className="prose prose-zinc max-w-none prose-p:text-[#191F28] prose-li:text-[#191F28] prose-strong:text-[#191F28] prose-a:text-[#3182F6] prose-a:underline prose-a:underline-offset-4 hover:prose-a:no-underline">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                          </article>
                        )}
                      </>
                    ) : (
                      <>
                        {m.section ? (
                          <div className="mb-2 text-[11px] font-semibold text-[#3182F6]">
                            {sectionLabel(m.section) || ""}
                          </div>
                        ) : null}
                        <div className="whitespace-pre-wrap">{m.content}</div>
                      </>
                    )}
                    {m.role === "assistant" && m.content.trim() ? (
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            addToStash(m.content, {
                              title: sectionLabel(m.section) || "초안",
                              source: {
                                kind: "assistant_message",
                                ...(m.section
                                  ? {
                                      sectionKey: m.section.key,
                                      sectionTitle: m.section.title,
                                      ...(typeof m.section.index === "number" ? { sectionIndex: m.section.index } : {}),
                                    }
                                  : {}),
                                ...(m.createdAt ? { assistantCreatedAt: m.createdAt } : {}),
                              },
                            })
                          }
                          disabled={stashBusy || busy || sending}
                        >
                          초안 확정
                        </Button>
                        {m.section && stashSectionKeys.has(m.section.key) ? (
                          <Badge tone="success">확정됨</Badge>
                        ) : stash.some((it) => it.content.trim() === m.content.trim()) ? (
                          <Badge tone="neutral">바구니 담김</Badge>
                        ) : null}
                      </div>
                    ) : null}
                    <div className="mt-2 text-[10px] text-[#B0B8C1]">
                      {m.role === "user" ? "you" : "merry"} · {m.createdAt?.slice(0, 16).replace("T", " ") || ""}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-xl border border-[#E5E8EB] bg-[#F8F9FA] p-4 text-sm text-[#8B95A1]">
                시작 프롬프트 예시를 눌러 대화를 시작하세요.
              </div>
            )}
          </div>

          <div className="border-t border-[#F2F4F6] px-5 py-4">
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
        </div>

        {panelOpen ? <div className="space-y-4">
          <FactsAssumptionsPanel sessionId={sessionId} companyName={meta?.companyName} evidenceJobs={evidenceJobs} />

          <div className="rounded-2xl bg-white p-5" style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px #E5E8EB" }}>
            <div className="text-[14px] font-bold text-[#191F28]" id="step-confirm">초안 바구니</div>
            <div className="mt-0.5 text-[12px] text-[#8B95A1]">
              확정된 초안을 모아 한 번에 드래프트로 옮기고, 커서식 리뷰(수정/좋음/대안)를 시작합니다.
            </div>

            <div className="mt-4 space-y-3">
              <div className="rounded-xl border border-[#E5E8EB] p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-[12px] font-bold text-[#191F28]">확정된 초안</div>
                  <Button variant="ghost" size="sm" onClick={loadStash} disabled={stashBusy}>
                    새로고침
                  </Button>
                </div>

                {stashMsg ? (
                  <div className="mt-3 rounded-lg border border-[#E5E8EB] bg-[#F8F9FA] px-3 py-2 text-[11.5px] text-[#4E5968]">
                    {stashMsg}
                  </div>
                ) : null}

                <div className="mt-3 space-y-2">
                  {!stash.length ? (
                    <div className="text-[12px] text-[#8B95A1]">
                      아직 바구니에 담긴 초안이 없습니다. 대화 메시지에서 &quot;초안 확정&quot;을 눌러 담아보세요.
                    </div>
                  ) : (
                    orderedStash.map((it) => (
                      <div key={it.itemId} className="rounded-xl border border-[#E5E8EB] bg-[#F8F9FA] p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-[13px] font-semibold text-[#191F28]">{it.title}</div>
                            <div className="mt-0.5 flex items-center justify-between gap-2 text-[11px] text-[#8B95A1]">
                              <span className="font-mono">{it.itemId}</span>
                              <span>{(it.createdAt || "").slice(0, 16).replace("T", " ")}</span>
                            </div>
                            <div className="mt-1.5 line-clamp-3 text-[11.5px] text-[#4E5968]">
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
                  <div className="text-[11.5px] text-[#8B95A1]">{stash.length ? `${stash.length}개 파트 확정됨` : "0개"}</div>
                  <Button variant="primary" size="sm" disabled={!stash.length || busy || stashBusy} onClick={commitStashToDraft}>
                    드래프트로 옮기기
                  </Button>
                </div>
              </div>

              <div className="rounded-xl border border-[#E5E8EB] p-4" id="step-draft">
                <div className="text-[12px] font-bold text-[#191F28]">대상 드래프트</div>
                <div className="mt-2 grid gap-2">
                  <select
                    className="h-11 w-full rounded-xl border border-[#E5E8EB] bg-white px-3 text-sm text-[#191F28] outline-none focus:border-[#3182F6] focus:ring-2 focus:ring-[#3182F6]/15"
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
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11.5px] text-[#8B95A1]">
                    <span>근거 결과는 새 버전으로 저장됩니다.</span>
                    {activeDraftId ? (
                      <Link href={`/drafts/${activeDraftId}`} className="text-[#3182F6] underline underline-offset-4 hover:no-underline">
                        드래프트 열기
                      </Link>
                    ) : null}
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-[#E5E8EB] p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-[12px] font-bold text-[#191F28]">PDF 근거 → 드래프트 버전</div>
                  <Button variant="ghost" size="sm" onClick={loadJobs} disabled={recBusy}>
                    새로고침
                  </Button>
                </div>

                <div className="mt-2 flex items-center gap-2 text-[11.5px] text-[#8B95A1]">
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-[#E5E8EB] accent-[#3182F6]"
                      checked={autoImportEvidence}
                      onChange={(e) => setAutoImportEvidence(e.target.checked)}
                      disabled={!activeDraftId}
                    />
                    완료 시 자동 저장
                  </label>
                  <span>·</span>
                  <Link href="/analysis" className="text-[#3182F6] underline underline-offset-4 hover:no-underline">
                    근거 추출 잡 실행
                  </Link>
                </div>

                {recMsg ? (
                  <div className="mt-3 rounded-lg border border-[#E5E8EB] bg-[#F8F9FA] px-3 py-2 text-[11.5px] text-[#4E5968]">
                    {recMsg}
                  </div>
                ) : null}

                <div className="mt-3 space-y-2">
                  {!evidenceJobs.length ? (
                    <div className="text-[12px] text-[#8B95A1]">최근 PDF 근거 추출 잡이 없습니다. 먼저 잡을 생성하세요.</div>
                  ) : (
                    evidenceJobs.map((j) => {
                      const ready =
                        j.status === "succeeded" &&
                        (j.artifacts || []).some((a) => a.artifactId === "pdf_evidence_json");
                      return (
                        <div key={j.jobId} className="rounded-xl border border-[#E5E8EB] bg-[#F8F9FA] p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-[13px] font-semibold text-[#191F28]">{j.title}</div>
                              <div className="mt-0.5 flex items-center justify-between gap-2 text-[11px] text-[#8B95A1]">
                                <span className="font-mono">{j.jobId}</span>
                                {badgeForJobStatus(j.status)}
                              </div>
                            </div>
                            <Button variant="secondary" size="sm" disabled={!ready || recBusy || !activeDraftId} onClick={() => importEvidenceToDraft(j)}>
                              드래프트 저장
                            </Button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>

              <div className="rounded-xl border border-[#E5E8EB] bg-[#F8F9FA] p-4">
                <div className="text-[12px] font-bold text-[#191F28]">다음 연결</div>
                <div className="mt-2 text-[12px] text-[#8B95A1] leading-relaxed">
                  - PDF/엑셀 업로드 → 근거 추출<br />
                  - DART 인수인의견 데이터셋 검색<br />
                  - 심화 의견(딥 옵피니언) 파이프라인<br />
                  - 결과를 자동으로 드래프트 버전으로 저장
                </div>
              </div>
            </div>
          </div>
        </div> : null}
      </div>
    </div>
  );
}
