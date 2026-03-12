"use client";

import Link from "next/link";
import * as React from "react";
import { useParams } from "next/navigation";
import { ArrowRight, GitBranch, PanelRightClose, PanelRightOpen, RefreshCw, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  DecisionTree,
  buildDecisionContext,
  parseDecisionsFromMessages,
  formatDecisionMessage,
  formatCustomBranchMessage,
  type DecisionRecord,
  type DecisionQuestion,
} from "@/components/report/DecisionTree";
import { PresenceBar } from "@/components/report/PresenceBar";
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

function sectionLabel(section?: { title: string; index?: number }): string | null {
  if (!section || !section.title) return null;
  const idx = typeof section.index === "number" ? `${section.index}. ` : "";
  return `${idx}${section.title}`.trim();
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

const DECISION_PREFIX = "[의사결정]";
const BRANCH_PREFIX = "[새분기]";

function isDecisionMessage(content: string): boolean {
  return content.startsWith(DECISION_PREFIX);
}

function isBranchMessage(content: string): boolean {
  return content.startsWith(BRANCH_PREFIX);
}

function isSystemMessage(content: string): boolean {
  return isDecisionMessage(content) || isBranchMessage(content);
}

export default function ReportSessionPage() {
  const params = useParams<{ slug: string }>();
  const slug = (params.slug ?? "").trim();
  const sessionId = `report_${slug}`;

  const [meta, setMeta] = React.useState<ReportSessionMeta | null>(null);
  const [messages, setMessages] = React.useState<ReportMessage[]>([]);
  const [prompt, setPrompt] = React.useState("");
  const [sending, setSending] = React.useState(false);
  const sendingRef = React.useRef(false);
  const [error, setError] = React.useState<string | null>(null);
  const bottomRef = React.useRef<HTMLDivElement>(null);

  // Decision tree state
  const [showTree, setShowTree] = React.useState(false);
  const [decisions, setDecisions] = React.useState<DecisionRecord[]>([]);
  const [customQuestions, setCustomQuestions] = React.useState<DecisionQuestion[]>([]);
  const [rememberedToast, setRememberedToast] = React.useState<string | null>(null);

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
      const msgs = res.messages || [];
      setMessages(msgs);
      // Extract decisions and custom branches from message history
      const parsed = parseDecisionsFromMessages(msgs);
      setDecisions(parsed.decisions);
      setCustomQuestions(parsed.customQuestions);
    } catch {
      setError("메시지를 불러오지 못했습니다.");
    }
  }, [sessionId]);

  React.useEffect(() => {
    loadMeta();
    loadMessages();
  }, [loadMeta, loadMessages]);

  // Auto-scroll to bottom on new messages
  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Toast auto-dismiss
  React.useEffect(() => {
    if (!rememberedToast) return;
    const t = setTimeout(() => setRememberedToast(null), 3000);
    return () => clearTimeout(t);
  }, [rememberedToast]);

  async function sendMessage(message: string, section?: TocSection) {
    const text = message.trim();
    if (!text || sendingRef.current) return;

    sendingRef.current = true;
    setSending(true);
    setError(null);

    const sectionMeta = section
      ? { key: section.key, title: section.title, index: section.index }
      : undefined;

    // Inject decision context into the message if decisions exist
    const decisionCtx = buildDecisionContext(decisions);
    const enrichedMessage = decisionCtx && !isSystemMessage(text)
      ? `${text}\n\n---\n${decisionCtx}`
      : text;

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
        body: JSON.stringify({ sessionId, message: enrichedMessage, section: sectionMeta }),
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
      setError("전송/생성에 실패했습니다. LLM 환경변수와 모델 접근 권한을 확인하세요.");
    } finally {
      sendingRef.current = false;
      setSending(false);
    }
  }

  // Fetch next autoregressive branch question from LLM
  async function fetchNextBranch(allDecisions: DecisionRecord[]) {
    try {
      const res = await fetch("/api/report/next-branch", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          sessionId,
          decisions: allDecisions.map((d) => ({ question: d.question, answer: d.answer })),
          companyName: meta?.companyName,
          fundName: meta?.fundName,
        }),
      });
      if (!res.ok) return;
      const data = await res.json();
      if (!data.ok || !data.question) return;

      const qId = `auto_${Date.now()}`;
      const newQ: DecisionQuestion = {
        id: qId,
        question: data.question,
        merryComment: data.merryComment || "메리가 추천하는 다음 질문이에요.",
        options: (data.options || []).map((label: string) => ({ label, value: label })),
        allowCustom: true,
        userCreated: false,
      };
      setCustomQuestions((prev) => [...prev, newQ]);

      // Persist the auto-generated branch so it's restored on reload
      const msg = formatCustomBranchMessage(qId, data.question, data.options || []);
      // Save silently — don't trigger full chat flow, just persist
      await fetch("/api/report/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId, message: msg }),
      });
    } catch {
      // Silently fail — autoregressive branch is optional
    }
  }

  // Decision tree handler
  function handleDecision(
    questionId: string,
    question: string,
    answer: string,
    _value: string,
    custom?: boolean,
    userCreated?: boolean,
  ) {
    const record: DecisionRecord = {
      questionId,
      question,
      answer,
      value: _value,
      custom,
      userCreated,
      timestamp: new Date().toISOString(),
    };

    const updatedDecisions = [...decisions, record];
    setDecisions(updatedDecisions);

    // Show "remembered" toast
    setRememberedToast(answer);

    // Send as a message so it persists and the LLM sees it
    const msg = formatDecisionMessage(questionId, question, answer, custom);
    sendMessage(msg);

    // Auto-generate next branch question after a short delay
    // (give sendMessage time to start so we don't conflict)
    setTimeout(() => fetchNextBranch(updatedDecisions), 1500);
  }

  // Custom branch creation handler (manual)
  function handleAddBranch(question: string, options: string[]) {
    const qId = `custom_${Date.now()}`;
    const newQ: DecisionQuestion = {
      id: qId,
      question,
      merryComment: "심사역이 추가한 커스텀 분기에요.",
      options: options.map((label) => ({ label, value: label })),
      allowCustom: true,
      userCreated: true,
    };
    setCustomQuestions((prev) => [...prev, newQ]);

    // Persist as a message so it's restored on reload
    const msg = formatCustomBranchMessage(qId, question, options);
    sendMessage(msg);
  }

  const streamingAssistantIndex = sending ? messages.findLastIndex((m) => m.role === "assistant") : -1;
  const hasDecisions = decisions.length > 0;

  return (
    <div className="flex h-full">
      {/* ── Main chat area ── */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* ── Header ── */}
        <div className="shrink-0 border-b border-[var(--line)] px-6 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <h1 className="truncate text-lg font-bold" style={{ color: "var(--ink)" }}>
                {meta?.title ?? "투자심사 보고서"}
              </h1>
              <div className="mt-0.5 flex items-center gap-3 text-xs" style={{ color: "var(--ink-light)" }}>
                {meta?.companyName && <span>{meta.companyName}</span>}
                {meta?.author && <span>· {meta.author}</span>}
                <PresenceBar sessionId={sessionId} />
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Decision tree toggle */}
              <Button
                variant={showTree ? "primary" : "secondary"}
                size="sm"
                onClick={() => setShowTree((v) => !v)}
                title="의사결정 트리"
              >
                <GitBranch className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">분기 심사</span>
                {hasDecisions && !showTree && (
                  <span
                    className="ml-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-bold"
                    style={{ background: "var(--accent)", color: "#fff" }}
                  >
                    {decisions.length}
                  </span>
                )}
              </Button>
              <Link href="/report" className="inline-flex">
                <Button variant="secondary" size="sm">세션 목록</Button>
              </Link>
              <Button variant="secondary" size="sm" onClick={() => { loadMeta(); loadMessages(); }}>
                <RefreshCw className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

          {/* TOC quick-generate buttons */}
          <div className="mt-3 flex flex-wrap gap-1.5">
            {TOC_SECTIONS.map((sec) => (
              <button
                key={sec.key}
                onClick={() => sendMessage(buildSectionPrompt(sec, meta), sec)}
                disabled={sending}
                className="rounded-full px-3 py-1 text-xs font-medium transition-colors disabled:opacity-40"
                style={{
                  background: "var(--bg-subtle)",
                  border: "1px solid var(--card-border)",
                  color: "var(--ink-light)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "var(--accent)";
                  e.currentTarget.style.color = "var(--ink)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--card-border)";
                  e.currentTarget.style.color = "var(--ink-light)";
                }}
              >
                {sec.index}. {sec.title}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="mx-6 mt-3 rounded-lg px-4 py-2.5 text-xs font-medium" style={{ background: "#FEF2F2", border: "1px solid #FECACA", color: "#DC2626" }}>
            {error}
          </div>
        )}

        {/* ── Messages ── */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.length ? (
              messages.map((m, idx) => {
                // Hide branch definition messages (internal bookkeeping)
                if (m.role === "user" && isBranchMessage(m.content)) {
                  return null;
                }

                // Render decision messages differently
                if (m.role === "user" && isDecisionMessage(m.content)) {
                  const body = m.content.slice(DECISION_PREFIX.length).trim();
                  const pipeIdx = body.indexOf("|");
                  const rest = pipeIdx >= 0 ? body.slice(pipeIdx + 1).trim() : body;
                  const colonIdx = rest.indexOf(":");
                  const question = colonIdx >= 0 ? rest.slice(0, colonIdx).trim() : "";
                  const answer = colonIdx >= 0 ? rest.slice(colonIdx + 1).trim() : rest;

                  return (
                    <div key={idx} className="flex justify-end">
                      <div
                        className="max-w-[75%] rounded-2xl px-4 py-2.5 text-sm"
                        style={{
                          background: "var(--accent-dim)",
                          border: "1.5px solid var(--accent)",
                          color: "var(--ink)",
                        }}
                      >
                        <div className="flex items-center gap-1.5 text-[11px] font-semibold" style={{ color: "var(--accent)" }}>
                          <GitBranch className="h-3 w-3" />
                          의사결정
                        </div>
                        <div className="mt-1 text-[12px]" style={{ color: "var(--ink-light)" }}>
                          {question}
                        </div>
                        <div className="mt-0.5 text-[13px] font-semibold" style={{ color: "var(--ink)" }}>
                          {answer}
                        </div>
                        <div className="mt-1.5 text-[10px] opacity-50">
                          you ·{" "}
                          {m.createdAt
                            ? new Date(m.createdAt).toLocaleString("ko-KR", {
                                timeZone: "Asia/Seoul",
                                month: "2-digit",
                                day: "2-digit",
                                hour: "2-digit",
                                minute: "2-digit",
                              })
                            : ""}
                        </div>
                      </div>
                    </div>
                  );
                }

                return (
                  <div key={idx} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
                    <div
                      className="max-w-[85%] rounded-2xl px-4 py-3 text-sm"
                      style={
                        m.role === "user"
                          ? { background: "var(--accent)", color: "#FFFFFF" }
                          : { background: "var(--bg-subtle)", border: "1px solid var(--card-border)", color: "var(--ink)" }
                      }
                    >
                      {m.role === "assistant" ? (
                        <>
                          {m.section && (
                            <div className="mb-2 text-[11px] font-semibold" style={{ color: "var(--accent)" }}>
                              {sectionLabel(m.section)}
                            </div>
                          )}
                          {sending && idx === streamingAssistantIndex ? (
                            <div className="whitespace-pre-wrap">{m.content || "..."}</div>
                          ) : (
                            <article className="prose prose-sm max-w-none prose-headings:text-[var(--ink)] prose-p:text-[var(--ink)] prose-li:text-[var(--ink)] prose-strong:text-[var(--ink)] prose-a:text-[var(--accent)] prose-a:underline prose-a:underline-offset-4">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                            </article>
                          )}
                        </>
                      ) : (
                        <>
                          {m.section && (
                            <div className="mb-1.5 text-[11px] font-semibold opacity-80">
                              {sectionLabel(m.section)}
                            </div>
                          )}
                          <div className="whitespace-pre-wrap">{m.content}</div>
                        </>
                      )}
                      <div className="mt-2 text-[10px] opacity-50">
                        {m.role === "user" ? "you" : "merry"} ·{" "}
                        {m.createdAt
                          ? new Date(m.createdAt).toLocaleString("ko-KR", {
                              timeZone: "Asia/Seoul",
                              month: "2-digit",
                              day: "2-digit",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : ""}
                      </div>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <div className="text-4xl mb-4">💬</div>
                <p className="text-sm font-medium" style={{ color: "var(--ink)" }}>대화를 시작하세요</p>
                <p className="mt-1 text-xs" style={{ color: "var(--ink-light)" }}>
                  위의 목차 버튼을 누르거나, 아래에 직접 질문을 입력하세요.
                </p>
                <button
                  onClick={() => setShowTree(true)}
                  className="mt-4 flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all hover:scale-[1.02]"
                  style={{
                    background: "var(--accent-dim)",
                    border: "1.5px solid var(--accent)",
                    color: "var(--accent)",
                  }}
                >
                  <GitBranch className="h-4 w-4" />
                  분기 심사로 시작하기
                </button>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* ── Input area ── */}
        <div className="shrink-0 border-t border-[var(--line)] px-6 py-4">
          <div className="mx-auto max-w-3xl">
            {/* Quick prompts */}
            <div className="mb-3 flex flex-wrap gap-1.5">
              {[
                { label: "시장규모 근거", msg: "시장규모/성장률 근거를 정리해줘. 근거가 없으면 필요한 자료를 질문해줘." },
                { label: "인수인의견 초안", msg: "인수인의견 스타일로 투자심사 보고서 초안 문단을 작성해줘. 부족한 정보는 질문해줘." },
                { label: "리스크 강화", msg: "리스크 섹션을 더 날카롭게 써줘. 법무/재무/사업/시장 측면으로 나눠줘." },
              ].map(({ label, msg }) => (
                <button
                  key={label}
                  onClick={() => sendMessage(msg)}
                  disabled={sending}
                  className="rounded-full px-3 py-1 text-xs font-medium transition-colors disabled:opacity-40"
                  style={{
                    background: "var(--bg-subtle)",
                    border: "1px solid var(--card-border)",
                    color: "var(--ink-light)",
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="flex gap-3">
              <Textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && prompt.trim()) {
                    e.preventDefault();
                    sendMessage(prompt);
                  }
                }}
                placeholder="보고서 작성 관련 질문..."
                className="min-h-[48px] flex-1 resize-none"
                disabled={sending}
                rows={1}
              />
              <Button
                variant="primary"
                onClick={() => sendMessage(prompt)}
                disabled={sending || !prompt.trim()}
                className="shrink-0 self-end"
              >
                {sending ? (
                  <Sparkles className="h-4 w-4 animate-pulse" />
                ) : (
                  <ArrowRight className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Decision Tree Panel (right) ── */}
      {showTree && (
        <div
          className="hidden w-[340px] shrink-0 border-l md:flex md:flex-col"
          style={{
            borderColor: "var(--line)",
            background: "var(--bg)",
          }}
        >
          {/* Panel close button */}
          <div className="flex items-center justify-between border-b px-3 py-2" style={{ borderColor: "var(--line)" }}>
            <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--ink-light)" }}>
              Decision Tree
            </span>
            <button
              onClick={() => setShowTree(false)}
              className="rounded-md p-1 transition-colors hover:bg-[var(--bg-subtle)]"
            >
              <PanelRightClose className="h-4 w-4" style={{ color: "var(--ink-light)" }} />
            </button>
          </div>

          <DecisionTree
            decisions={decisions}
            customQuestions={customQuestions}
            onDecision={handleDecision}
            onAddBranch={handleAddBranch}
            sending={sending}
            meta={{
              title: meta?.title,
              companyName: meta?.companyName,
              date: meta?.reportDate,
            }}
          />
        </div>
      )}

      {/* ── "Remembered" toast ── */}
      {rememberedToast && (
        <div
          className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 animate-[fadeInUp_0.3s_ease-out]"
        >
          <div
            className="flex items-center gap-2 rounded-xl px-4 py-2.5 shadow-lg"
            style={{
              background: "var(--ink)",
              color: "#fff",
            }}
          >
            <Sparkles className="h-3.5 w-3.5" style={{ color: "var(--accent)" }} />
            <span className="text-[13px] font-medium">
              메리가 이것을 기억할 것입니다
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
