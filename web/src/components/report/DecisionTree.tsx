"use client";

import * as React from "react";
import { Check, ChevronRight, GitBranch, MessageCircle, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/Button";

/* ── Decision tree schema ── */

export type DecisionOption = {
  label: string;
  value: string;
};

export type DecisionQuestion = {
  id: string;
  question: string;
  merryComment: string; // Merry's personality comment
  options: DecisionOption[];
  allowCustom?: boolean;
};

export type DecisionRecord = {
  questionId: string;
  question: string;
  answer: string;
  value: string;
  custom?: boolean;
  timestamp: string;
};

export const DECISION_QUESTIONS: DecisionQuestion[] = [
  {
    id: "startup_type",
    question: "이 스타트업의 주요 특성은 무엇인가요?",
    merryComment: "첫 번째 분기점이에요. 기업의 DNA를 파악하면 심사 방향이 달라져요.",
    options: [
      { label: "임팩트 중심 (사회적 가치 우선)", value: "impact" },
      { label: "기술 기반 (딥테크/특허)", value: "tech" },
      { label: "부트스트래핑 (초기 매출 확보)", value: "bootstrap" },
      { label: "플랫폼/네트워크 효과", value: "platform" },
    ],
    allowCustom: true,
  },
  {
    id: "stage",
    question: "현재 투자 단계는?",
    merryComment: "투자 스테이지에 따라 기대 수익률과 리스크 허용 범위가 완전히 달라요.",
    options: [
      { label: "Pre-Seed / Seed", value: "seed" },
      { label: "Series A", value: "series_a" },
      { label: "Series B 이상", value: "series_b_plus" },
    ],
  },
  {
    id: "impact_area",
    question: "주요 임팩트 영역은?",
    merryComment: "MYSC 펀드별 임팩트 테마와의 fit을 확인할게요.",
    options: [
      { label: "환경/기후", value: "environment" },
      { label: "교육/인적자본", value: "education" },
      { label: "헬스케어/웰빙", value: "healthcare" },
      { label: "금융 포용", value: "financial_inclusion" },
      { label: "지역/커뮤니티", value: "community" },
    ],
    allowCustom: true,
  },
  {
    id: "revenue_model",
    question: "수익 모델은?",
    merryComment: "수익 모델에 따라 재무 프로젝션 방식이 달라져요.",
    options: [
      { label: "B2B SaaS", value: "b2b_saas" },
      { label: "B2G (정부/공공)", value: "b2g" },
      { label: "B2C 구독", value: "b2c_sub" },
      { label: "거래 수수료", value: "transaction" },
      { label: "혼합/기타", value: "mixed" },
    ],
    allowCustom: true,
  },
  {
    id: "exit_strategy",
    question: "예상 Exit 경로는?",
    merryComment: "Exit 전략이 밸류에이션과 투자 구조를 결정해요.",
    options: [
      { label: "IPO", value: "ipo" },
      { label: "M&A (대기업 인수)", value: "ma" },
      { label: "세컨더리 매각", value: "secondary" },
      { label: "아직 불명확", value: "unclear" },
    ],
  },
  {
    id: "risk_priority",
    question: "가장 우려되는 리스크는?",
    merryComment: "여기서 선택한 리스크를 중심으로 심사 보고서를 강화할게요.",
    options: [
      { label: "시장 규모/성장성", value: "market" },
      { label: "팀/실행력", value: "team" },
      { label: "기술/IP 리스크", value: "tech_risk" },
      { label: "규제/법률 리스크", value: "regulatory" },
      { label: "재무/번레이트", value: "financial" },
    ],
    allowCustom: true,
  },
];

/* ── Helper: build context string from decisions ── */
export function buildDecisionContext(decisions: DecisionRecord[]): string {
  if (!decisions.length) return "";
  const lines = decisions.map(
    (d) => `- ${d.question}: ${d.answer}${d.custom ? " (심사역 직접 입력)" : ""}`
  );
  return (
    "[의사결정 분기 기록]\n" +
    "심사역이 아래와 같이 판단했습니다. 이후 답변에 반드시 반영하세요.\n" +
    lines.join("\n")
  );
}

/* ── Helper: parse decisions from message history ── */
const DECISION_PREFIX = "[의사결정]";

export function parseDecisionsFromMessages(
  messages: { role: string; content: string }[]
): DecisionRecord[] {
  const records: DecisionRecord[] = [];
  for (const m of messages) {
    if (m.role !== "user" || !m.content.startsWith(DECISION_PREFIX)) continue;
    // Format: [의사결정] questionId | question: answer
    const body = m.content.slice(DECISION_PREFIX.length).trim();
    const pipeIdx = body.indexOf("|");
    if (pipeIdx < 0) continue;
    const questionId = body.slice(0, pipeIdx).trim();
    const rest = body.slice(pipeIdx + 1).trim();
    const colonIdx = rest.indexOf(":");
    if (colonIdx < 0) continue;
    const question = rest.slice(0, colonIdx).trim();
    const answer = rest.slice(colonIdx + 1).trim();
    const isCustom = answer.endsWith("(직접입력)");
    records.push({
      questionId,
      question,
      answer: isCustom ? answer.replace("(직접입력)", "").trim() : answer,
      value: answer,
      custom: isCustom,
      timestamp: new Date().toISOString(),
    });
  }
  return records;
}

export function formatDecisionMessage(
  questionId: string,
  question: string,
  answer: string,
  custom?: boolean
): string {
  return `${DECISION_PREFIX} ${questionId} | ${question}: ${answer}${custom ? " (직접입력)" : ""}`;
}

/* ── Props ── */
type Props = {
  decisions: DecisionRecord[];
  onDecision: (questionId: string, question: string, answer: string, value: string, custom?: boolean) => void;
  sending?: boolean;
  compact?: boolean;
};

/* ── Component ── */
export function DecisionTree({ decisions, onDecision, sending, compact }: Props) {
  const [customInput, setCustomInput] = React.useState("");
  const [showCustom, setShowCustom] = React.useState(false);

  const answeredIds = new Set(decisions.map((d) => d.questionId));
  const nextQuestion = DECISION_QUESTIONS.find((q) => !answeredIds.has(q.id));
  const allDone = !nextQuestion;
  const progress = decisions.length;
  const total = DECISION_QUESTIONS.length;

  function handleSelect(q: DecisionQuestion, opt: DecisionOption) {
    setShowCustom(false);
    setCustomInput("");
    onDecision(q.id, q.question, opt.label, opt.value, false);
  }

  function handleCustomSubmit(q: DecisionQuestion) {
    if (!customInput.trim()) return;
    onDecision(q.id, q.question, customInput.trim(), customInput.trim(), true);
    setCustomInput("");
    setShowCustom(false);
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="shrink-0 border-b px-4 py-3" style={{ borderColor: "var(--line)" }}>
        <div className="flex items-center gap-2">
          <GitBranch className="h-4 w-4" style={{ color: "var(--accent)" }} />
          <span className="text-sm font-bold" style={{ color: "var(--ink)" }}>
            의사결정 트리
          </span>
        </div>
        <div className="mt-1.5 flex items-center gap-2">
          <div
            className="h-1.5 flex-1 rounded-full overflow-hidden"
            style={{ background: "var(--bg-overlay)" }}
          >
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${(progress / total) * 100}%`,
                background: allDone
                  ? "var(--accent)"
                  : "linear-gradient(90deg, var(--accent), #34D399)",
              }}
            />
          </div>
          <span className="text-[11px] font-medium tabular-nums" style={{ color: "var(--ink-light)" }}>
            {progress}/{total}
          </span>
        </div>
      </div>

      {/* Tree nodes */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="space-y-1">
          {DECISION_QUESTIONS.map((q, i) => {
            const decision = decisions.find((d) => d.questionId === q.id);
            const isNext = nextQuestion?.id === q.id;
            const isFuture = !decision && !isNext;

            return (
              <div key={q.id}>
                {/* Connector line */}
                {i > 0 && (
                  <div className="flex justify-start pl-[15px]">
                    <div
                      className="w-px"
                      style={{
                        height: 16,
                        background: decision
                          ? "var(--accent)"
                          : isNext
                            ? "var(--card-border)"
                            : "var(--line)",
                      }}
                    />
                  </div>
                )}

                {/* Node */}
                <div
                  className="rounded-xl px-3 py-2.5 transition-all"
                  style={{
                    background: isNext
                      ? "var(--accent-dim)"
                      : decision
                        ? "var(--bg-subtle)"
                        : "transparent",
                    border: isNext
                      ? "1.5px solid var(--accent)"
                      : decision
                        ? "1px solid var(--card-border)"
                        : "1px solid transparent",
                    opacity: isFuture ? 0.4 : 1,
                  }}
                >
                  {/* Question header */}
                  <div className="flex items-start gap-2">
                    <div
                      className="mt-0.5 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
                      style={{
                        background: decision
                          ? "var(--accent)"
                          : isNext
                            ? "var(--ink)"
                            : "var(--card-border)",
                        color: decision || isNext ? "#fff" : "var(--ink-light)",
                      }}
                    >
                      {decision ? <Check className="h-3 w-3" /> : i + 1}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div
                        className="text-[12.5px] font-semibold leading-snug"
                        style={{ color: isFuture ? "var(--muted)" : "var(--ink)" }}
                      >
                        {q.question}
                      </div>

                      {/* Answered */}
                      {decision && (
                        <div className="mt-1 flex items-center gap-1.5">
                          <ChevronRight className="h-3 w-3 shrink-0" style={{ color: "var(--accent)" }} />
                          <span
                            className="text-[12px] font-medium"
                            style={{ color: "var(--accent)" }}
                          >
                            {decision.answer}
                          </span>
                          {decision.custom && (
                            <span
                              className="rounded px-1 py-0.5 text-[9px]"
                              style={{ background: "var(--bg-overlay)", color: "var(--ink-light)" }}
                            >
                              직접입력
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Active question: show options */}
                  {isNext && !sending && (
                    <div className="mt-3 space-y-2 pl-[30px]">
                      {/* Merry comment */}
                      <div className="flex items-start gap-1.5 mb-2">
                        <MessageCircle className="mt-0.5 h-3 w-3 shrink-0" style={{ color: "var(--ink-light)" }} />
                        <p className="text-[11px] leading-relaxed" style={{ color: "var(--ink-light)" }}>
                          {q.merryComment}
                        </p>
                      </div>

                      {/* Option buttons */}
                      <div className="flex flex-wrap gap-1.5">
                        {q.options.map((opt) => (
                          <button
                            key={opt.value}
                            onClick={() => handleSelect(q, opt)}
                            className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition-all hover:scale-[1.02] active:scale-[0.98]"
                            style={{
                              background: "var(--bg-elevated)",
                              border: "1px solid var(--card-border)",
                              color: "var(--ink)",
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.borderColor = "var(--accent)";
                              e.currentTarget.style.background = "var(--accent-dim)";
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.borderColor = "var(--card-border)";
                              e.currentTarget.style.background = "var(--bg-elevated)";
                            }}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>

                      {/* Custom input */}
                      {q.allowCustom && (
                        <div className="mt-1">
                          {showCustom ? (
                            <div className="flex gap-1.5">
                              <input
                                value={customInput}
                                onChange={(e) => setCustomInput(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") handleCustomSubmit(q);
                                  if (e.key === "Escape") {
                                    setShowCustom(false);
                                    setCustomInput("");
                                  }
                                }}
                                placeholder="직접 입력..."
                                className="flex-1 rounded-lg px-2.5 py-1.5 text-[12px] outline-none"
                                style={{
                                  background: "var(--bg-elevated)",
                                  border: "1px solid var(--accent)",
                                  color: "var(--ink)",
                                }}
                                autoFocus
                              />
                              <button
                                onClick={() => handleCustomSubmit(q)}
                                disabled={!customInput.trim()}
                                className="rounded-lg px-2.5 py-1.5 text-[11px] font-medium disabled:opacity-40"
                                style={{
                                  background: "var(--accent)",
                                  color: "#fff",
                                }}
                              >
                                확인
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setShowCustom(true)}
                              className="text-[11px] font-medium underline underline-offset-2"
                              style={{ color: "var(--ink-light)" }}
                            >
                              직접 입력하기
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {isNext && sending && (
                    <div className="mt-2 pl-[30px]">
                      <div className="flex items-center gap-2 text-[11px]" style={{ color: "var(--ink-light)" }}>
                        <Sparkles className="h-3 w-3 animate-pulse" style={{ color: "var(--accent)" }} />
                        메리가 기록하는 중...
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Completion */}
        {allDone && (
          <div
            className="mt-4 rounded-xl px-4 py-3 text-center"
            style={{
              background: "var(--accent-dim)",
              border: "1px solid var(--accent)",
            }}
          >
            <div className="flex items-center justify-center gap-2">
              <Sparkles className="h-4 w-4" style={{ color: "var(--accent)" }} />
              <span className="text-[13px] font-bold" style={{ color: "var(--accent)" }}>
                분기 완료!
              </span>
            </div>
            <p className="mt-1.5 text-[11px]" style={{ color: "var(--ink-light)" }}>
              메리가 모든 의사결정을 기억하고 있어요.
              <br />
              보고서 작성에 반영할게요.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
