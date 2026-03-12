"use client";

import * as React from "react";
import { Check, ChevronRight, Download, GitBranch, Image, MessageCircle, Plus, Sparkles, X } from "lucide-react";

/* ── Decision tree schema ── */

export type DecisionOption = {
  label: string;
  value: string;
};

export type DecisionQuestion = {
  id: string;
  question: string;
  merryComment: string;
  options: DecisionOption[];
  allowCustom?: boolean;
  userCreated?: boolean; // 사용자가 직접 만든 분기
};

export type DecisionRecord = {
  questionId: string;
  question: string;
  answer: string;
  value: string;
  custom?: boolean;
  userCreated?: boolean;
  timestamp: string;
};

const DEFAULT_QUESTIONS: DecisionQuestion[] = [
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
    allowCustom: true,
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
    allowCustom: true,
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
    (d) =>
      `- ${d.question}: ${d.answer}${d.custom ? " (심사역 직접 입력)" : ""}${d.userCreated ? " [커스텀 분기]" : ""}`
  );
  return (
    "[의사결정 분기 기록]\n" +
    "심사역이 아래와 같이 판단했습니다. 이후 답변에 반드시 반영하세요.\n" +
    lines.join("\n")
  );
}

/* ── Helper: parse decisions from message history ── */
const DECISION_PREFIX = "[의사결정]";
const CUSTOM_BRANCH_PREFIX = "[새분기]";

export function parseDecisionsFromMessages(
  messages: { role: string; content: string }[]
): { decisions: DecisionRecord[]; customQuestions: DecisionQuestion[] } {
  const decisions: DecisionRecord[] = [];
  const customQuestions: DecisionQuestion[] = [];

  for (const m of messages) {
    if (m.role !== "user") continue;

    // Parse custom branch definitions
    if (m.content.startsWith(CUSTOM_BRANCH_PREFIX)) {
      const body = m.content.slice(CUSTOM_BRANCH_PREFIX.length).trim();
      // Format: [새분기] questionId | question | opt1, opt2, opt3
      const parts = body.split("|").map((s) => s.trim());
      if (parts.length >= 2) {
        const qId = parts[0];
        const question = parts[1];
        const optLabels = parts[2] ? parts[2].split(",").map((s) => s.trim()).filter(Boolean) : [];
        customQuestions.push({
          id: qId,
          question,
          merryComment: "메리가 추가한 커스텀 분기에요.",
          options: optLabels.map((label) => ({ label, value: label })),
          allowCustom: true,
          userCreated: true,
        });
      }
      continue;
    }

    // Parse decisions
    if (!m.content.startsWith(DECISION_PREFIX)) continue;
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
    const isUserCreated = questionId.startsWith("custom_");
    decisions.push({
      questionId,
      question,
      answer: isCustom ? answer.replace("(직접입력)", "").trim() : answer,
      value: answer,
      custom: isCustom,
      userCreated: isUserCreated,
      timestamp: new Date().toISOString(),
    });
  }

  return { decisions, customQuestions };
}

export function formatDecisionMessage(
  questionId: string,
  question: string,
  answer: string,
  custom?: boolean
): string {
  return `${DECISION_PREFIX} ${questionId} | ${question}: ${answer}${custom ? " (직접입력)" : ""}`;
}

export function formatCustomBranchMessage(
  questionId: string,
  question: string,
  options: string[]
): string {
  return `${CUSTOM_BRANCH_PREFIX} ${questionId} | ${question} | ${options.join(", ")}`;
}

/* ── SVG Generation ── */

function escSvg(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/** Wrap text into lines of maxChars width */
function wrapText(text: string, maxChars: number): string[] {
  const words = text.split(" ");
  const lines: string[] = [];
  let cur = "";
  for (const w of words) {
    if (cur && cur.length + 1 + w.length > maxChars) {
      lines.push(cur);
      cur = w;
    } else {
      cur = cur ? `${cur} ${w}` : w;
    }
  }
  if (cur) lines.push(cur);
  return lines;
}

export function generateDecisionTreeSvg(
  decisions: DecisionRecord[],
  allQuestions: DecisionQuestion[],
  meta?: { title?: string; companyName?: string; date?: string },
): string {
  const answered = decisions.filter((d) => allQuestions.some((q) => q.id === d.questionId));
  if (!answered.length) return "";

  const nodeW = 320;
  const nodeH = 72;
  const gapY = 32;
  const padX = 40;
  const padTop = 80;
  const padBottom = 40;
  const connectorH = gapY;

  const totalH = padTop + answered.length * (nodeH + connectorH) - connectorH + padBottom;
  const totalW = nodeW + padX * 2;

  const accent = "#00C805";
  const accentDim = "#E8FAE8";
  const ink = "#1A1D21";
  const inkLight = "#6F7780";
  const bg = "#FFFFFF";
  const cardBorder = "#E3E5E8";
  const bgSubtle = "#F7F8F9";

  let nodes = "";
  answered.forEach((d, i) => {
    const x = padX;
    const y = padTop + i * (nodeH + connectorH);
    const q = allQuestions.find((aq) => aq.id === d.questionId);
    const qNum = q ? allQuestions.indexOf(q) + 1 : i + 1;
    const isCustom = d.userCreated || d.questionId.startsWith("custom_") || d.questionId.startsWith("auto_");

    const questionLines = wrapText(d.question, 36);
    const answerLines = wrapText(d.answer, 40);

    // Connector line (except first)
    if (i > 0) {
      const lineX = padX + 24;
      const lineY1 = y - connectorH;
      const lineY2 = y;
      nodes += `<line x1="${lineX}" y1="${lineY1}" x2="${lineX}" y2="${lineY2}" stroke="${accent}" stroke-width="2" stroke-dasharray="4,3"/>`;
    }

    // Node background
    nodes += `<rect x="${x}" y="${y}" width="${nodeW}" height="${nodeH}" rx="14" fill="${bgSubtle}" stroke="${cardBorder}" stroke-width="1"/>`;

    // Number circle
    const cx = x + 24;
    const cy = y + 22;
    nodes += `<circle cx="${cx}" cy="${cy}" r="12" fill="${accent}"/>`;
    nodes += `<text x="${cx}" y="${cy + 1}" text-anchor="middle" dominant-baseline="central" fill="white" font-size="11" font-weight="700" font-family="-apple-system,BlinkMacSystemFont,sans-serif">${qNum}</text>`;

    // Custom badge
    if (isCustom) {
      nodes += `<rect x="${x + nodeW - 52}" y="${y + 8}" width="40" height="16" rx="4" fill="${accentDim}"/>`;
      nodes += `<text x="${x + nodeW - 32}" y="${y + 18}" text-anchor="middle" fill="${accent}" font-size="8" font-weight="600" font-family="-apple-system,BlinkMacSystemFont,sans-serif">커스텀</text>`;
    }

    // Question text
    const textX = x + 46;
    questionLines.forEach((line, li) => {
      nodes += `<text x="${textX}" y="${y + 18 + li * 14}" fill="${ink}" font-size="11" font-weight="600" font-family="-apple-system,BlinkMacSystemFont,sans-serif">${escSvg(line)}</text>`;
    });

    // Answer with arrow
    const answerY = y + 18 + questionLines.length * 14 + 6;
    nodes += `<text x="${textX}" y="${answerY}" fill="${accent}" font-size="12" font-weight="700" font-family="-apple-system,BlinkMacSystemFont,sans-serif">→ ${escSvg(answerLines[0] || "")}</text>`;
    answerLines.slice(1).forEach((line, li) => {
      nodes += `<text x="${textX + 14}" y="${answerY + (li + 1) * 14}" fill="${accent}" font-size="12" font-weight="700" font-family="-apple-system,BlinkMacSystemFont,sans-serif">${escSvg(line)}</text>`;
    });
  });

  // Title area
  const titleText = meta?.title || "투자심사 의사결정 트리";
  const subtitle = [meta?.companyName, meta?.date].filter(Boolean).join(" · ") || "";

  const header =
    `<text x="${padX}" y="32" fill="${ink}" font-size="16" font-weight="800" font-family="-apple-system,BlinkMacSystemFont,sans-serif">${escSvg(titleText)}</text>` +
    (subtitle
      ? `<text x="${padX}" y="50" fill="${inkLight}" font-size="11" font-family="-apple-system,BlinkMacSystemFont,sans-serif">${escSvg(subtitle)}</text>`
      : "") +
    `<text x="${padX}" y="${padTop - 14}" fill="${inkLight}" font-size="10" font-family="-apple-system,BlinkMacSystemFont,sans-serif">${answered.length}개 의사결정 · MERRY 투자심사</text>`;

  return [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${totalW}" height="${totalH}" viewBox="0 0 ${totalW} ${totalH}">`,
    `<rect width="${totalW}" height="${totalH}" fill="${bg}" rx="16"/>`,
    header,
    nodes,
    `</svg>`,
  ].join("\n");
}

export function downloadSvg(svgString: string, filename: string) {
  const blob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadPng(svgString: string, filename: string, scale = 2) {
  const blob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const img = new window.Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = img.width * scale;
    canvas.height = img.height * scale;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(scale, scale);
    ctx.drawImage(img, 0, 0);
    canvas.toBlob((pngBlob) => {
      if (!pngBlob) return;
      const pngUrl = URL.createObjectURL(pngBlob);
      const a = document.createElement("a");
      a.href = pngUrl;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(pngUrl);
    }, "image/png");
    URL.revokeObjectURL(url);
  };
  img.src = url;
}

/* ── Props ── */
type Props = {
  decisions: DecisionRecord[];
  customQuestions: DecisionQuestion[];
  onDecision: (questionId: string, question: string, answer: string, value: string, custom?: boolean, userCreated?: boolean) => void;
  onAddBranch: (question: string, options: string[]) => void;
  onStartDebate?: () => void;
  sending?: boolean;
  debating?: boolean;
  maxAutoReached?: boolean;
  meta?: { title?: string; companyName?: string; date?: string };
};

/* ── Component ── */
export function DecisionTree({ decisions, customQuestions, onDecision, onAddBranch, onStartDebate, sending, debating, maxAutoReached, meta }: Props) {
  const [customInput, setCustomInput] = React.useState("");
  const [showCustom, setShowCustom] = React.useState(false);
  const [showPreview, setShowPreview] = React.useState(false);

  // New branch creation state
  const [showNewBranch, setShowNewBranch] = React.useState(false);
  const [newQuestion, setNewQuestion] = React.useState("");
  const [newOptions, setNewOptions] = React.useState<string[]>([""]);

  // Merge default + custom questions
  const allQuestions = React.useMemo(
    () => [...DEFAULT_QUESTIONS, ...customQuestions],
    [customQuestions]
  );

  const answeredIds = new Set(decisions.map((d) => d.questionId));
  const nextQuestion = allQuestions.find((q) => !answeredIds.has(q.id));
  const allDefaultDone = DEFAULT_QUESTIONS.every((q) => answeredIds.has(q.id));
  const allDone = allQuestions.every((q) => answeredIds.has(q.id));
  const progress = decisions.length;
  const total = allQuestions.length;

  function handleSelect(q: DecisionQuestion, opt: DecisionOption) {
    setShowCustom(false);
    setCustomInput("");
    onDecision(q.id, q.question, opt.label, opt.value, false, q.userCreated);
  }

  function handleCustomSubmit(q: DecisionQuestion) {
    if (!customInput.trim()) return;
    onDecision(q.id, q.question, customInput.trim(), customInput.trim(), true, q.userCreated);
    setCustomInput("");
    setShowCustom(false);
  }

  function handleAddOption() {
    setNewOptions((prev) => [...prev, ""]);
  }

  function handleRemoveOption(idx: number) {
    setNewOptions((prev) => prev.filter((_, i) => i !== idx));
  }

  function handleSubmitBranch() {
    const q = newQuestion.trim();
    const opts = newOptions.map((o) => o.trim()).filter(Boolean);
    if (!q) return;
    onAddBranch(q, opts);
    setNewQuestion("");
    setNewOptions([""]);
    setShowNewBranch(false);
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="shrink-0 border-b px-4 py-3" style={{ borderColor: "var(--line)" }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4" style={{ color: "var(--accent)" }} />
            <span className="text-sm font-bold" style={{ color: "var(--ink)" }}>
              의사결정 트리
            </span>
          </div>

          {/* Export buttons — only show when there are decisions */}
          {decisions.length > 0 && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => setShowPreview((v) => !v)}
                className="rounded-md p-1.5 transition-colors hover:bg-[var(--bg-subtle)]"
                title="미리보기"
              >
                <Image className="h-3.5 w-3.5" style={{ color: showPreview ? "var(--accent)" : "var(--ink-light)" }} />
              </button>
              <button
                onClick={() => {
                  const svg = generateDecisionTreeSvg(decisions, allQuestions, meta);
                  if (svg) downloadSvg(svg, `decision-tree-${Date.now()}.svg`);
                }}
                className="rounded-md p-1.5 transition-colors hover:bg-[var(--bg-subtle)]"
                title="SVG 다운로드"
              >
                <Download className="h-3.5 w-3.5" style={{ color: "var(--ink-light)" }} />
              </button>
              <button
                onClick={() => {
                  const svg = generateDecisionTreeSvg(decisions, allQuestions, meta);
                  if (svg) downloadPng(svg, `decision-tree-${Date.now()}.png`, 3);
                }}
                className="rounded-md px-2 py-1 text-[10px] font-semibold transition-colors hover:bg-[var(--bg-subtle)]"
                style={{ color: "var(--ink-light)" }}
                title="PNG 다운로드 (고해상도)"
              >
                PNG
              </button>
            </div>
          )}
        </div>
        <div className="mt-1.5 flex items-center gap-2">
          <div
            className="h-1.5 flex-1 rounded-full overflow-hidden"
            style={{ background: "var(--bg-overlay)" }}
          >
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: total > 0 ? `${(progress / total) * 100}%` : "0%",
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

      {/* SVG Preview */}
      {showPreview && decisions.length > 0 && (
        <div className="shrink-0 border-b overflow-auto p-3" style={{ borderColor: "var(--line)", background: "var(--bg-subtle)", maxHeight: 320 }}>
          <div
            className="mx-auto"
            style={{ maxWidth: 400 }}
            dangerouslySetInnerHTML={{ __html: generateDecisionTreeSvg(decisions, allQuestions, meta) }}
          />
        </div>
      )}

      {/* Tree nodes */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="space-y-1">
          {allQuestions.map((q, i) => {
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
                      <div className="flex items-center gap-1.5">
                        <span
                          className="text-[12.5px] font-semibold leading-snug"
                          style={{ color: isFuture ? "var(--muted)" : "var(--ink)" }}
                        >
                          {q.question}
                        </span>
                        {q.userCreated && (
                          <span
                            className="shrink-0 rounded px-1 py-0.5 text-[9px] font-medium"
                            style={{ background: "var(--accent-dim)", color: "var(--accent)" }}
                          >
                            커스텀
                          </span>
                        )}
                      </div>

                      {/* Answered */}
                      {decision && (
                        <div className="mt-1 flex items-center gap-1.5">
                          <ChevronRight className="h-3 w-3 shrink-0" style={{ color: "var(--accent)" }} />
                          <span className="text-[12px] font-medium" style={{ color: "var(--accent)" }}>
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

                      {/* Custom input for answer */}
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
                                style={{ background: "var(--accent)", color: "#fff" }}
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

        {/* ── Add custom branch ── */}
        <div className="mt-4">
          {showNewBranch ? (
            <div
              className="rounded-xl p-3.5 space-y-3"
              style={{
                background: "var(--bg-subtle)",
                border: "1.5px dashed var(--accent)",
              }}
            >
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-bold" style={{ color: "var(--ink)" }}>
                  새 분기 추가
                </span>
                <button
                  onClick={() => {
                    setShowNewBranch(false);
                    setNewQuestion("");
                    setNewOptions([""]);
                  }}
                  className="rounded p-0.5"
                >
                  <X className="h-3.5 w-3.5" style={{ color: "var(--ink-light)" }} />
                </button>
              </div>

              {/* Question input */}
              <div>
                <label className="block text-[11px] font-medium mb-1" style={{ color: "var(--ink-light)" }}>
                  질문
                </label>
                <input
                  value={newQuestion}
                  onChange={(e) => setNewQuestion(e.target.value)}
                  placeholder="예: 이 기업의 핵심 경쟁우위는?"
                  className="w-full rounded-lg px-2.5 py-2 text-[12px] outline-none"
                  style={{
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--card-border)",
                    color: "var(--ink)",
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "var(--card-border)"; }}
                />
              </div>

              {/* Options */}
              <div>
                <label className="block text-[11px] font-medium mb-1" style={{ color: "var(--ink-light)" }}>
                  선택지 (없으면 자유입력만 가능)
                </label>
                <div className="space-y-1.5">
                  {newOptions.map((opt, idx) => (
                    <div key={idx} className="flex gap-1.5">
                      <input
                        value={opt}
                        onChange={(e) => {
                          const next = [...newOptions];
                          next[idx] = e.target.value;
                          setNewOptions(next);
                        }}
                        placeholder={`선택지 ${idx + 1}`}
                        className="flex-1 rounded-lg px-2.5 py-1.5 text-[12px] outline-none"
                        style={{
                          background: "var(--bg-elevated)",
                          border: "1px solid var(--card-border)",
                          color: "var(--ink)",
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            handleAddOption();
                          }
                        }}
                      />
                      {newOptions.length > 1 && (
                        <button
                          onClick={() => handleRemoveOption(idx)}
                          className="rounded p-1 hover:bg-[var(--bg-overlay)]"
                        >
                          <X className="h-3 w-3" style={{ color: "var(--ink-light)" }} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <button
                  onClick={handleAddOption}
                  className="mt-1.5 flex items-center gap-1 text-[11px] font-medium"
                  style={{ color: "var(--ink-light)" }}
                >
                  <Plus className="h-3 w-3" />
                  선택지 추가
                </button>
              </div>

              {/* Submit */}
              <button
                onClick={handleSubmitBranch}
                disabled={!newQuestion.trim()}
                className="w-full rounded-lg py-2 text-[12px] font-bold disabled:opacity-40 transition-all"
                style={{
                  background: "var(--accent)",
                  color: "#fff",
                }}
              >
                분기 추가하기
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowNewBranch(true)}
              className="flex w-full items-center justify-center gap-1.5 rounded-xl py-2.5 text-[12px] font-medium transition-all hover:scale-[1.01]"
              style={{
                border: "1.5px dashed var(--card-border)",
                color: "var(--ink-light)",
                background: "transparent",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--accent)";
                e.currentTarget.style.color = "var(--accent)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--card-border)";
                e.currentTarget.style.color = "var(--ink-light)";
              }}
            >
              <Plus className="h-3.5 w-3.5" />
              새 분기 추가
            </button>
          )}
        </div>

        {/* Completion — when all done or max auto branches reached */}
        {(allDone || maxAutoReached) && !showNewBranch && (
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
                분기 심사 완료!
              </span>
            </div>
            <p className="mt-1.5 text-[11px]" style={{ color: "var(--ink-light)" }}>
              메리가 {decisions.length}개 의사결정을 기억하고 있어요.
            </p>

            {/* Debate start button */}
            {onStartDebate && (
              <button
                onClick={onStartDebate}
                disabled={debating}
                className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl py-2.5 text-[13px] font-bold transition-all hover:scale-[1.01] disabled:opacity-50"
                style={{
                  background: debating ? "var(--card-border)" : "var(--ink)",
                  color: "#fff",
                }}
              >
                {debating ? (
                  <>
                    <Sparkles className="h-4 w-4 animate-pulse" />
                    투자 토론 진행 중...
                  </>
                ) : (
                  <>
                    <MessageCircle className="h-4 w-4" />
                    🟢 긍정 vs 🔴 비관 투자 토론 시작
                  </>
                )}
              </button>
            )}

            <p className="mt-2 text-[10px]" style={{ color: "var(--muted)" }}>
              새 분기를 추가하면 더 세밀한 심사도 가능해요.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
