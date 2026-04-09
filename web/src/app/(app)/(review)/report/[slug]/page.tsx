"use client";

import Link from "next/link";
import * as React from "react";
import { useParams } from "next/navigation";
import { ArrowRight, BookOpen, Check, ClipboardCopy, Download, FileText, GitBranch, Loader2, MessageCircle, Paperclip, PanelRightClose, RefreshCw, RotateCcw, Search, Sparkles, ThumbsDown, X } from "lucide-react";
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
  perspective?: "optimistic" | "pessimistic" | "synthesis";
};

type TocSection = {
  key: string;
  index: number;
  title: string;
  hint?: string;
};

const TOC_SECTIONS: TocSection[] = [
  { key: "executive_summary", index: 1, title: "Executive Summary" },
  { key: "company_overview", index: 2, title: "회사 개요" },
  { key: "market_competition", index: 3, title: "시장/경쟁" },
  { key: "business_financials", index: 4, title: "사업 모델 및 재무" },
  { key: "team_org", index: 5, title: "팀 및 조직" },
  { key: "risks_issues", index: 6, title: "리스크 및 이슈" },
  { key: "valuation", index: 7, title: "밸류에이션" },
  { key: "impact_analysis", index: 8, title: "임팩트 분석" },
  { key: "investment_opinion", index: 9, title: "투자 의견" },
];

function sectionLabel(section?: { title: string; index?: number }): string | null {
  if (!section || !section.title) return null;
  const idx = typeof section.index === "number" ? `${section.index}. ` : "";
  return `${idx}${section.title}`.trim();
}

function buildSectionPrompt(section: TocSection, meta: ReportSessionMeta | null): string {
  const company = meta?.companyName ? `- 회사명: ${meta.companyName}\n` : "";
  const author = meta?.author ? `- 작성자: ${meta.author}\n` : "";
  const today = new Date().toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul", year: "numeric", month: "long", day: "numeric" });
  const reportDate = meta?.reportDate ? `- 작성일: ${meta.reportDate}\n` : `- 작성일: ${today}\n`;
  const fileTitle = meta?.fileTitle ? `- 파일 제목: ${meta.fileTitle}\n` : "";
  const fund = meta?.fundName ? `- 펀드: ${meta.fundName}\n` : meta?.fundId ? `- 펀드: ${meta.fundId}\n` : "";
  const context = `${company}${author}${reportDate}- 오늘 날짜: ${today}\n${fileTitle}${fund}`.trim();

  const extras: Record<string, string> = {
    impact_analysis:
      "\n반드시 아래 3가지 프레임워크를 포함하여 작성:\n" +
      "### 8-1. SDGs 기반 분석\n" +
      "- 해당 기업이 기여하는 UN SDGs 목표 (1~17번 중 해당되는 것)\n" +
      "- 각 SDGs별 기여 경로 및 근거\n" +
      "- SDGs 타겟 레벨까지 매핑 (예: SDG 3.4)\n\n" +
      "### 8-2. 이해관계자 분석\n" +
      "- 핵심 이해관계자 식별 (수혜자, 고객, 지역사회, 투자자, 정부 등)\n" +
      "- 이해관계자별 임팩트 경로 (어떤 변화가, 어떻게 발생하는지)\n" +
      "- 의도하지 않은 부정적 영향 가능성\n\n" +
      "### 8-3. IRIS+ 지표 분석\n" +
      "- GIIN IRIS+ 카탈로그에서 해당 기업에 적용 가능한 핵심 지표 선정\n" +
      "- 각 지표별 현재 측정 가능 여부 및 데이터 확보 방안\n" +
      "- 임팩트 측정 프레임워크 제안 (IMP 5 Dimensions 참고)\n",
    risks_issues:
      "\n아래 영역별로 구분하여 작성:\n" +
      "- 법무 리스크 (규제, IP, 계약)\n" +
      "- 재무 리스크 (번레이트, 유동성, 자금조달)\n" +
      "- 사업 리스크 (경쟁, 기술, 시장변화)\n" +
      "- 시장 리스크 (거시경제, 산업 사이클)\n",
    valuation:
      "\n아래 항목을 포함:\n" +
      "- 밸류에이션 방법론 (PER, PSR, DCF 등 적용 가능한 것)\n" +
      "- Peer 기업 비교 기반 적정 밸류에이션 범위\n" +
      "- 투자 라운드 조건 대비 적정성 평가\n",
  };
  const extra = extras[section.key] || "";

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
const DEBATE_PREFIX = "[토론]";

/** Max autoregressive branch questions before transitioning to debate */
const MAX_AUTO_BRANCHES = 5;

function isDecisionMessage(content: string): boolean {
  return content.startsWith(DECISION_PREFIX);
}

function isBranchMessage(content: string): boolean {
  return content.startsWith(BRANCH_PREFIX);
}

function isDebateMessage(content: string): boolean {
  return content.startsWith(DEBATE_PREFIX);
}

function isSystemMessage(content: string): boolean {
  return isDecisionMessage(content) || isBranchMessage(content) || isDebateMessage(content);
}

/* ── 합본 생성 ── */

type CompiledSection = {
  key: string;
  index: number;
  title: string;
  content: string;
};

function compileReport(
  messages: ReportMessage[],
  meta: ReportSessionMeta | null,
  decisions: DecisionRecord[],
): { markdown: string; sections: CompiledSection[]; missingSections: TocSection[] } {
  // For each TOC section, find the LAST assistant message tagged with that section
  const sectionMap = new Map<string, string>();
  for (const m of messages) {
    if (m.role !== "assistant" || !m.section?.key || !m.content.trim()) continue;
    sectionMap.set(m.section.key, m.content);
  }

  const sections: CompiledSection[] = [];
  const missingSections: TocSection[] = [];

  for (const sec of TOC_SECTIONS) {
    const content = sectionMap.get(sec.key);
    if (content) {
      sections.push({ key: sec.key, index: sec.index, title: sec.title, content });
    } else {
      missingSections.push(sec);
    }
  }

  // Build markdown document
  const lines: string[] = [];

  // Title page
  const title = meta?.title || "투자심사 보고서";
  lines.push(`# ${title}`);
  lines.push("");
  if (meta?.companyName) lines.push(`**대상 기업:** ${meta.companyName}`);
  if (meta?.fundName) lines.push(`**펀드:** ${meta.fundName}`);
  if (meta?.author) lines.push(`**작성자:** ${meta.author}`);
  if (meta?.reportDate) lines.push(`**작성일:** ${meta.reportDate}`);
  lines.push(`**생성일:** ${new Date().toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul" })}`);
  lines.push("");
  lines.push("---");
  lines.push("");

  // Table of contents
  lines.push("## 목차");
  lines.push("");
  for (const sec of TOC_SECTIONS) {
    const done = sectionMap.has(sec.key);
    lines.push(`${done ? "- [x]" : "- [ ]"} ${sec.index}. ${sec.title}`);
  }
  lines.push("");
  lines.push("---");
  lines.push("");

  // Section contents
  for (const sec of sections) {
    lines.push(sec.content.trim());
    lines.push("");
    lines.push("---");
    lines.push("");
  }

  // Decision summary (if any)
  if (decisions.length > 0) {
    lines.push("## 부록: 의사결정 분기 기록");
    lines.push("");
    lines.push("| # | 질문 | 답변 |");
    lines.push("|---|------|------|");
    for (let i = 0; i < decisions.length; i++) {
      const d = decisions[i];
      lines.push(`| ${i + 1} | ${d.question} | **${d.answer}**${d.custom ? " (직접입력)" : ""} |`);
    }
    lines.push("");
  }

  lines.push("---");
  lines.push(`*MERRY 투자심사 AI · ${new Date().toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })}*`);

  return { markdown: lines.join("\n"), sections, missingSections };
}

function downloadFile(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function markdownToHtml(md: string, title: string): string {
  // Simple markdown → HTML for .doc export
  let html = md
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/^- \[x\] (.+)$/gm, "<li>✅ $1</li>")
    .replace(/^- \[ \] (.+)$/gm, "<li>⬜ $1</li>")
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/^\|(.+)\|$/gm, (row) => {
      const cells = row.split("|").filter(Boolean).map((c) => c.trim());
      if (cells.every((c) => /^-+$/.test(c))) return "";
      const tag = cells.some((c) => c.startsWith("**")) ? "td" : "td";
      return "<tr>" + cells.map((c) => `<${tag}>${c}</${tag}>`).join("") + "</tr>";
    })
    .replace(/^---$/gm, "<hr/>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br/>");

  return `<!DOCTYPE html>
<html><head>
<meta charset="utf-8"/>
<title>${title}</title>
<style>
  body { font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; line-height: 1.7; font-size: 11pt; }
  h1 { font-size: 22pt; margin-bottom: 8px; }
  h2 { font-size: 16pt; margin-top: 28px; border-bottom: 2px solid #00C805; padding-bottom: 4px; }
  h3 { font-size: 13pt; margin-top: 20px; }
  table { border-collapse: collapse; width: 100%; margin: 12px 0; }
  td, th { border: 1px solid #ddd; padding: 8px 12px; text-align: left; font-size: 10pt; }
  tr:nth-child(even) { background: #f9f9f9; }
  hr { border: none; border-top: 1px solid #e0e0e0; margin: 24px 0; }
  li { margin: 4px 0; }
  strong { color: #00C805; }
</style>
</head><body><p>${html}</p></body></html>`;
}

/* ── Compile Modal Component ── */

function CompileModal({
  messages,
  meta,
  decisions,
  sessionId,
  onClose,
  onMessagesUpdate,
}: {
  messages: ReportMessage[];
  meta: ReportSessionMeta | null;
  decisions: DecisionRecord[];
  sessionId: string;
  onClose: () => void;
  onMessagesUpdate: () => Promise<void>;
}) {
  const filename = `${meta?.companyName || "report"}_투자심사보고서`;

  // Editable section contents — initialized from existing messages
  const [editSections, setEditSections] = React.useState<Record<string, string>>(() => {
    const map: Record<string, string> = {};
    for (const m of messages) {
      if (m.role !== "assistant" || !m.section?.key || !m.content.trim()) continue;
      // Skip LLM error messages
      if (m.content.startsWith("[LLM ERROR]")) continue;
      map[m.section.key] = m.content;
    }
    return map;
  });

  const [editingKey, setEditingKey] = React.useState<string | null>(null);
  const [copied, setCopied] = React.useState(false);
  const [generating, setGenerating] = React.useState(false);
  const [generatingKeys, setGeneratingKeys] = React.useState<Set<string>>(new Set());
  const [genProgress, setGenProgress] = React.useState<string | null>(null);

  // Generate a single section via streaming chat API
  async function generateSection(sec: TocSection): Promise<string | null> {
    const prompt = buildSectionPrompt(sec, meta);
    const sectionMeta = { key: sec.key, title: sec.title, index: sec.index };

    // Build decision context
    const decisionCtx = buildDecisionContext(decisions);
    const enrichedMessage = decisionCtx ? `${prompt}\n\n---\n${decisionCtx}` : prompt;

    try {
      const res = await fetch("/api/review/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId, message: enrichedMessage, section: sectionMeta }),
      });

      if (!res.ok) return null;

      const reader = res.body?.getReader();
      if (!reader) return null;

      const decoder = new TextDecoder("utf-8");
      let acc = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        acc += decoder.decode(value, { stream: true });
        // Live update in the modal
        setEditSections((prev) => ({ ...prev, [sec.key]: acc }));
      }

      return acc;
    } catch {
      return null;
    }
  }

  // Generate ALL missing sections sequentially
  async function generateAll() {
    const missing = TOC_SECTIONS.filter((sec) => !editSections[sec.key]?.trim());
    if (missing.length === 0) return;

    setGenerating(true);

    for (let i = 0; i < missing.length; i++) {
      const sec = missing[i];
      setGenProgress(`${sec.index}. ${sec.title} 생성 중... (${i + 1}/${missing.length})`);
      setGeneratingKeys((prev) => new Set(prev).add(sec.key));

      const result = await generateSection(sec);

      setGeneratingKeys((prev) => {
        const next = new Set(prev);
        next.delete(sec.key);
        return next;
      });

      if (!result) {
        // If one fails, continue to next
        setEditSections((prev) => ({
          ...prev,
          [sec.key]: prev[sec.key] || "[생성 실패] 다시 시도해주세요.",
        }));
      }
    }

    setGenProgress(null);
    setGenerating(false);

    // Reload messages so they're persisted
    await onMessagesUpdate();
  }

  // Generate a single missing section
  async function generateOne(sec: TocSection) {
    setGenerating(true);
    setGenProgress(`${sec.index}. ${sec.title} 생성 중...`);
    setGeneratingKeys((prev) => new Set(prev).add(sec.key));

    await generateSection(sec);

    setGeneratingKeys((prev) => {
      const next = new Set(prev);
      next.delete(sec.key);
      return next;
    });
    setGenProgress(null);
    setGenerating(false);

    await onMessagesUpdate();
  }

  // Rebuild markdown from edited sections
  function buildEditedMarkdown(): string {
    const lines: string[] = [];
    const title = meta?.title || "투자심사 보고서";
    lines.push(`# ${title}`);
    lines.push("");
    if (meta?.companyName) lines.push(`**대상 기업:** ${meta.companyName}`);
    if (meta?.fundName) lines.push(`**펀드:** ${meta.fundName}`);
    if (meta?.author) lines.push(`**작성자:** ${meta.author}`);
    if (meta?.reportDate) lines.push(`**작성일:** ${meta.reportDate}`);
    lines.push(`**생성일:** ${new Date().toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul" })}`);
    lines.push("");
    lines.push("---");
    lines.push("");

    // TOC
    lines.push("## 목차");
    lines.push("");
    for (const sec of TOC_SECTIONS) {
      const done = !!editSections[sec.key]?.trim();
      lines.push(`${done ? "- [x]" : "- [ ]"} ${sec.index}. ${sec.title}`);
    }
    lines.push("");
    lines.push("---");
    lines.push("");

    // Sections
    for (const sec of TOC_SECTIONS) {
      const content = editSections[sec.key];
      if (content?.trim()) {
        lines.push(content.trim());
        lines.push("");
        lines.push("---");
        lines.push("");
      }
    }

    // Decisions
    if (decisions.length > 0) {
      lines.push("## 부록: 의사결정 분기 기록");
      lines.push("");
      lines.push("| # | 질문 | 답변 |");
      lines.push("|---|------|------|");
      for (let i = 0; i < decisions.length; i++) {
        const d = decisions[i];
        lines.push(`| ${i + 1} | ${d.question} | **${d.answer}**${d.custom ? " (직접입력)" : ""} |`);
      }
      lines.push("");
    }

    lines.push("---");
    lines.push(`*MERRY 투자심사 AI · ${new Date().toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })}*`);
    return lines.join("\n");
  }

  const editedMd = buildEditedMarkdown();
  const completedCount = TOC_SECTIONS.filter((s) => editSections[s.key]?.trim()).length;
  const missingCount = TOC_SECTIONS.length - completedCount;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.4)" }} onClick={(e) => { if (e.target === e.currentTarget && !generating) onClose(); }}>
      <div
        className="relative mx-4 flex max-h-[90vh] w-full max-w-3xl flex-col rounded-2xl shadow-2xl"
        style={{ background: "var(--bg)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4" style={{ borderColor: "var(--line)" }}>
          <div>
            <h2 className="text-base font-bold" style={{ color: "var(--ink)" }}>합본 생성</h2>
            <p className="mt-0.5 text-[12px]" style={{ color: "var(--ink-light)" }}>
              {completedCount}/{TOC_SECTIONS.length} 섹션 완료
              {genProgress && (
                <span className="ml-2" style={{ color: "var(--accent)" }}>
                  · {genProgress}
                </span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {missingCount > 0 && (
              <button
                onClick={generateAll}
                disabled={generating}
                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-semibold transition-all disabled:opacity-50"
                style={{
                  background: "var(--accent)",
                  color: "#fff",
                }}
              >
                {generating ? (
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Sparkles className="h-3.5 w-3.5" />
                )}
                {generating ? "생성 중..." : `전체 생성 (${missingCount}개)`}
              </button>
            )}
            <button onClick={() => { if (!generating) onClose(); }} className="rounded-lg p-1.5 hover:bg-[var(--bg-subtle)]">
              <X className="h-4 w-4" style={{ color: "var(--ink-light)" }} />
            </button>
          </div>
        </div>

        {/* Section editor */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {TOC_SECTIONS.map((sec) => {
            const content = editSections[sec.key] || "";
            const isEditing = editingKey === sec.key;
            const hasContent = !!content.trim() && !content.startsWith("[생성 실패]");
            const isGeneratingThis = generatingKeys.has(sec.key);

            return (
              <div
                key={sec.key}
                className="rounded-xl transition-all"
                style={{
                  border: isEditing
                    ? "1.5px solid var(--accent)"
                    : isGeneratingThis
                      ? "1.5px solid var(--accent)"
                      : hasContent
                        ? "1px solid var(--card-border)"
                        : "1px dashed var(--card-border)",
                  background: isEditing
                    ? "var(--bg-subtle)"
                    : isGeneratingThis
                      ? "var(--bg-subtle)"
                      : hasContent
                        ? "var(--bg)"
                        : "var(--bg-subtle)",
                }}
              >
                {/* Section header */}
                <div
                  className="flex items-center justify-between px-4 py-2.5 cursor-pointer"
                  onClick={() => {
                    if (generating) return;
                    if (isEditing) {
                      setEditingKey(null);
                    } else if (hasContent) {
                      setEditingKey(sec.key);
                    }
                  }}
                >
                  <div className="flex items-center gap-2">
                    <div
                      className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold"
                      style={{
                        background: isGeneratingThis
                          ? "var(--accent)"
                          : hasContent
                            ? "var(--accent)"
                            : "var(--card-border)",
                        color: isGeneratingThis || hasContent ? "#fff" : "var(--ink-light)",
                      }}
                    >
                      {isGeneratingThis ? (
                        <RefreshCw className="h-3 w-3 animate-spin" />
                      ) : hasContent ? (
                        <Check className="h-3 w-3" />
                      ) : (
                        sec.index
                      )}
                    </div>
                    <span
                      className="text-[13px] font-semibold"
                      style={{ color: hasContent || isGeneratingThis ? "var(--ink)" : "var(--muted)" }}
                    >
                      {sec.index}. {sec.title}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {isGeneratingThis && (
                      <span className="text-[10px] animate-pulse" style={{ color: "var(--accent)" }}>생성 중...</span>
                    )}
                    {!isGeneratingThis && hasContent && (
                      <span className="text-[10px]" style={{ color: "var(--ink-light)" }}>
                        {isEditing ? "편집 중" : "클릭하여 편집"}
                      </span>
                    )}
                    {!isGeneratingThis && !hasContent && !generating && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          generateOne(sec);
                        }}
                        className="flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-medium transition-colors"
                        style={{
                          background: "var(--accent-dim)",
                          color: "var(--accent)",
                          border: "1px solid var(--accent)",
                        }}
                      >
                        <Sparkles className="h-2.5 w-2.5" />
                        생성
                      </button>
                    )}
                    {!isGeneratingThis && !hasContent && generating && (
                      <span className="text-[10px]" style={{ color: "var(--muted)" }}>대기 중</span>
                    )}
                  </div>
                </div>

                {/* Streaming preview while generating */}
                {isGeneratingThis && content && (
                  <div
                    className="px-4 pb-3 text-[11.5px] leading-relaxed line-clamp-4 animate-pulse"
                    style={{ color: "var(--ink-light)" }}
                  >
                    {content.slice(-300).replace(/^#{1,3}\s.+/gm, "").trim()}...
                  </div>
                )}

                {/* Editor */}
                {isEditing && !isGeneratingThis && (
                  <div className="px-4 pb-3">
                    <textarea
                      value={content}
                      onChange={(e) =>
                        setEditSections((prev) => ({ ...prev, [sec.key]: e.target.value }))
                      }
                      className="w-full rounded-lg px-3 py-2.5 text-[12.5px] leading-relaxed outline-none resize-y font-mono"
                      style={{
                        background: "var(--bg)",
                        border: "1px solid var(--card-border)",
                        color: "var(--ink)",
                        minHeight: 200,
                        maxHeight: 500,
                      }}
                      onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                      onBlur={(e) => { e.currentTarget.style.borderColor = "var(--card-border)"; }}
                    />
                    <div className="mt-2 flex items-center gap-2">
                      <button
                        onClick={() => setEditingKey(null)}
                        className="rounded-lg px-3 py-1.5 text-[11px] font-medium"
                        style={{ background: "var(--accent)", color: "#fff" }}
                      >
                        완료
                      </button>
                      <button
                        onClick={() => {
                          setEditSections((prev) => ({ ...prev, [sec.key]: "" }));
                          setEditingKey(null);
                        }}
                        className="rounded-lg px-3 py-1.5 text-[11px] font-medium"
                        style={{ color: "#DC2626" }}
                      >
                        섹션 제거
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingKey(null);
                          generateOne(sec);
                        }}
                        className="rounded-lg px-3 py-1.5 text-[11px] font-medium"
                        style={{ color: "var(--accent)" }}
                      >
                        다시 생성
                      </button>
                    </div>
                  </div>
                )}

                {/* Collapsed preview */}
                {!isEditing && !isGeneratingThis && hasContent && (
                  <div
                    className="px-4 pb-3 text-[11.5px] leading-relaxed line-clamp-3"
                    style={{ color: "var(--ink-light)" }}
                  >
                    {content.slice(0, 200).replace(/^#{1,3}\s.+/gm, "").trim()}
                    {content.length > 200 && "..."}
                  </div>
                )}
              </div>
            );
          })}

          {/* Decision summary */}
          {decisions.length > 0 && (
            <div
              className="rounded-xl px-4 py-3"
              style={{ background: "var(--accent-dim)", border: "1px solid var(--accent)" }}
            >
              <div className="flex items-center gap-2 text-[12px] font-semibold" style={{ color: "var(--accent)" }}>
                <GitBranch className="h-3.5 w-3.5" />
                부록: 의사결정 분기 ({decisions.length}건)
              </div>
              <div className="mt-1 text-[11px]" style={{ color: "var(--ink-light)" }}>
                합본에 자동 포함됩니다
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-wrap items-center gap-2 border-t px-6 py-4" style={{ borderColor: "var(--line)" }}>
          <Button
            variant="primary"
            size="sm"
            disabled={generating || completedCount === 0}
            onClick={() => {
              const html = markdownToHtml(editedMd, meta?.title || "투자심사 보고서");
              downloadFile(html, `${filename}.doc`, "application/msword");
            }}
          >
            <FileText className="h-3.5 w-3.5" />
            Word (.doc)
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={generating || completedCount === 0}
            onClick={() => downloadFile(editedMd, `${filename}.md`, "text/markdown")}
          >
            <Download className="h-3.5 w-3.5" />
            Markdown
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={generating || completedCount === 0}
            onClick={async () => {
              await navigator.clipboard.writeText(editedMd);
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            }}
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <ClipboardCopy className="h-3.5 w-3.5" />}
            {copied ? "복사됨!" : "복사"}
          </Button>
          <div className="ml-auto text-[11px]" style={{ color: "var(--ink-light)" }}>
            {missingCount > 0 && !generating && (
              <span>미작성 {missingCount}개</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
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
  const [showCompile, setShowCompile] = React.useState(false);
  const [copied, setCopied] = React.useState(false);
  const [debating, setDebating] = React.useState(false);
  const [debateStarted, setDebateStarted] = React.useState(false);

  // File upload state
  type UploadingFile = {
    file: File;
    status: "uploading" | "parsing" | "done" | "error";
    fileId?: string;
    error?: string;
  };
  const [uploadingFiles, setUploadingFiles] = React.useState<UploadingFile[]>([]);
  const [dragging, setDragging] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const [searchOpen, setSearchOpen] = React.useState(false);
  const [searching, setSearching] = React.useState(false);

  async function handleMarketSearch(type: "news" | "signals") {
    setSearchOpen(false);
    setSearching(true);
    try {
      const endpoint = type === "news" ? "/api/review/news" : "/api/review/signals";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sector: meta?.companyName }),
      });
      if (!res.ok) throw new Error("검색 실패");
      const data = await res.json();

      // Format result as a system message
      let summary = "";
      if (type === "news" && data.clusters?.length) {
        summary = `📰 뉴스 다이제스트 (${data.totalArticles}건 분석)\n\n` +
          data.clusters.slice(0, 5).map((c: { grade: string; company: string; event: string; coverageScore: number; sources: string[] }) =>
            `[${c.grade}] ${c.company} — ${c.event} (Coverage ${c.coverageScore}, ${c.sources.join(", ")})`
          ).join("\n");
      } else if (type === "signals" && data.signals?.length) {
        const byCat = data.byCategory as Record<string, Array<{ strength: string; description: string }>>;
        const catLabels: Record<string, string> = { funding: "펀딩", talent: "인재", social: "소셜", media: "미디어", regulation: "규제" };
        summary = `📡 시그널 레이더 (${data.signals.length}건)\n\n` +
          Object.entries(byCat).filter(([, v]) => v.length > 0).map(([k, v]) => {
            const icon = v.some((s) => s.strength === "strong") ? "🔴" : "🟡";
            return `${icon} ${catLabels[k] ?? k}: ${v.slice(0, 3).map((s) => s.description).join("; ").slice(0, 100)}`;
          }).join("\n");
      } else {
        summary = type === "news" ? "📰 관련 뉴스를 찾지 못했어요." : "📡 관련 시그널을 찾지 못했어요.";
      }

      const sysMsg: ReportMessage = {
        role: "user",
        content: `[시장검색] ${summary}`,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, sysMsg]);
    } catch {
      setError("시장 검색에 실패했어요. 잠시 후 다시 시도해주세요.");
    } finally {
      setSearching(false);
    }
  }

  const loadMeta = React.useCallback(async () => {
    try {
      const res = await apiFetch<{ session: ReportSessionMeta }>(`/api/review/${sessionId}/meta`);
      setMeta(res.session);
    } catch {
      setMeta(null);
    }
  }, [sessionId]);

  const loadMessages = React.useCallback(async () => {
    setError(null);
    try {
      const res = await apiFetch<{ messages: ReportMessage[] }>(`/api/review/${sessionId}/messages`);
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

  async function sendMessage(message: string, section?: TocSection, perspective?: "optimistic" | "pessimistic" | "synthesis") {
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
      perspective,
    };
    const optimisticAssistant: ReportMessage = {
      role: "assistant",
      content: "",
      createdAt: new Date().toISOString(),
      section: sectionMeta,
      perspective,
    };
    setMessages((prev) => [...prev, optimisticUser, optimisticAssistant]);
    setPrompt("");

    let acc = "";
    try {
      const res = await fetch("/api/review/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId, message: enrichedMessage, section: sectionMeta, perspective }),
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
    // Stop after MAX_AUTO_BRANCHES auto-generated questions
    const autoCount = customQuestions.filter((q) => !q.userCreated).length;
    if (autoCount >= MAX_AUTO_BRANCHES) return;

    try {
      const res = await fetch("/api/review/next-branch", {
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
      await fetch("/api/review/chat", {
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
      merryComment: "메리가 추가한 커스텀 분기에요.",
      options: options.map((label) => ({ label, value: label })),
      allowCustom: true,
      userCreated: true,
    };
    setCustomQuestions((prev) => [...prev, newQ]);

    // Persist as a message so it's restored on reload
    const msg = formatCustomBranchMessage(qId, question, options);
    sendMessage(msg);
  }

  // Auto branches count for max check
  const autoBranchCount = customQuestions.filter((q) => !q.userCreated).length;
  const maxAutoReached = autoBranchCount >= MAX_AUTO_BRANCHES;

  // ── File upload handler ──
  const ALLOWED_EXTENSIONS = [
    ".pdf", ".xlsx", ".xls", ".docx",
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".txt", ".md", ".csv", ".json", ".tsv", ".log", ".xml", ".html", ".htm", ".yaml", ".yml",
  ];
  const MIME_MAP: Record<string, string> = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".tsv": "text/tab-separated-values",
    ".log": "text/plain",
    ".xml": "application/xml",
    ".html": "text/html",
    ".htm": "text/html",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
  };

  function getFileExt(name: string): string {
    const dot = name.lastIndexOf(".");
    return dot >= 0 ? name.slice(dot).toLowerCase() : "";
  }

  async function handleFileUpload(file: File) {
    const ext = getFileExt(file.name);
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`지원하지 않는 파일 형식이에요. (${ALLOWED_EXTENSIONS.join(", ")}만 가능)`);
      return;
    }

    const entry: UploadingFile = { file, status: "uploading" };
    setUploadingFiles((prev) => [...prev, entry]);

    const updateEntry = (update: Partial<UploadingFile>) => {
      setUploadingFiles((prev) =>
        prev.map((f) => (f.file === file ? { ...f, ...update } : f)),
      );
    };

    try {
      // Step 1: Presign
      const contentType = MIME_MAP[ext] || "application/octet-stream";
      const presignRes = await fetch("/api/uploads/presign", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          filename: file.name,
          contentType,
          sizeBytes: file.size,
        }),
      });
      if (!presignRes.ok) throw new Error("업로드 준비 실패");
      const presignData = await presignRes.json();
      const { fileId, key: s3Key, bucket: s3Bucket } = presignData.file;
      const { url: uploadUrl } = presignData.upload;

      updateEntry({ fileId });

      // Step 2: Upload to S3
      const putRes = await fetch(uploadUrl, {
        method: "PUT",
        headers: { "content-type": contentType },
        body: file,
      });
      if (!putRes.ok) throw new Error("S3 업로드 실패");

      // Step 3: Complete upload
      await fetch("/api/uploads/complete", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ fileId }),
      });

      // Step 4: Parse & store context
      updateEntry({ status: "parsing" });
      const parseRes = await fetch("/api/review/chat/upload", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          sessionId,
          fileId,
          s3Key,
          s3Bucket,
          originalName: file.name,
        }),
      });

      if (!parseRes.ok) {
        const errData = await parseRes.json().catch(() => ({}));
        throw new Error(errData?.detail || "문서 분석 실패");
      }

      updateEntry({ status: "done" });

      // Add a system-style message to the chat
      const systemMsg: ReportMessage = {
        role: "user",
        content: `[첨부] ${file.name} 문서를 추가했어요. 이 문서에 대해 질문해보세요!`,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, systemMsg]);

      // Auto-remove from uploading list after 3s
      setTimeout(() => {
        setUploadingFiles((prev) => prev.filter((f) => f.file !== file));
      }, 3000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "업로드 실패";
      updateEntry({ status: "error", error: msg });
      setError(msg);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files);
    for (const f of files) handleFileUpload(f);
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    setDragging(true);
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
  }

  // Debate flow — 3 rounds: optimistic → pessimistic → optimistic rebuttal
  async function startDebate() {
    if (debating) return;
    setDebating(true);
    setDebateStarted(true);
    setShowTree(false); // Close tree panel to focus on debate

    const decisionSummary = decisions
      .map((d, i) => `${i + 1}. ${d.question} → ${d.answer}`)
      .join("\n");
    const companyCtx = meta?.companyName ? `\n기업: ${meta.companyName}` : "";
    const fundCtx = meta?.fundName ? `\n펀드: ${meta.fundName}` : "";

    // Round 1: Optimistic Merry
    const round1 = `${DEBATE_PREFIX} [긍정 메리 분석]\n\n의사결정 기록:\n${decisionSummary}${companyCtx}${fundCtx}\n\n위 의사결정 기록을 바탕으로 이 투자건의 긍정적 관점에서 핵심 분석을 해줘.\n- 왜 이 투자가 매력적인지\n- 핵심 성장 동력과 시장 기회\n- 팀/기술 강점\n간결하게 핵심 포인트 3-5개로 정리해줘.`;
    await sendMessage(round1, undefined, "optimistic");

    // Small delay before round 2
    await new Promise((r) => setTimeout(r, 500));

    // Round 2: Pessimistic Merry
    const round2 = `${DEBATE_PREFIX} [비관 메리 반론]\n\n긍정 메리의 분석을 읽었어. 이제 비관적 관점에서 반론과 리스크를 분석해줘.\n- 긍정 메리가 간과한 리스크\n- 시장/경쟁/재무 위험\n- 실행 리스크와 최악의 시나리오\n간결하게 핵심 포인트 3-5개로 정리해줘.`;
    await sendMessage(round2, undefined, "pessimistic");

    await new Promise((r) => setTimeout(r, 500));

    // Round 3: Optimistic rebuttal + synthesis
    const round3 = `${DEBATE_PREFIX} [긍정 메리 재반박]\n\n비관 메리의 반론을 읽었어. 핵심 우려 사항에 대해 재반박하고, 리스크를 줄이기 위한 투자 조건(milestone, 안전장치)을 제안해줘.\n간결하게 정리해줘.`;
    await sendMessage(round3, undefined, "optimistic");

    setDebating(false);
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
              {/* Compile report */}
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowCompile(true)}
                title="합본 생성"
              >
                <BookOpen className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">합본</span>
              </Button>
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
              <Link href="/review" className="inline-flex">
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
        <div
          className="relative flex-1 overflow-y-auto px-6 py-5"
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {/* Drag overlay */}
          {dragging && (
            <div className="absolute inset-0 z-30 flex items-center justify-center rounded-lg border-2 border-dashed" style={{ borderColor: "var(--accent)", background: "rgba(var(--accent-rgb, 99,102,241), 0.05)" }}>
              <div className="flex flex-col items-center gap-2">
                <Paperclip className="h-8 w-8" style={{ color: "var(--accent)" }} />
                <span className="text-sm font-medium" style={{ color: "var(--accent)" }}>파일을 여기에 놓아주세요</span>
                <span className="text-xs" style={{ color: "var(--ink-light)" }}>PDF, XLSX, DOCX, 이미지, TXT, MD, CSV 등</span>
              </div>
            </div>
          )}
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.length ? (
              messages.map((m, idx) => {
                // Hide branch definition messages and debate prompts (internal bookkeeping)
                if (m.role === "user" && isBranchMessage(m.content)) {
                  return null;
                }
                if (m.role === "user" && isDebateMessage(m.content)) {
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

                // Perspective-aware styling for debate messages
                const isOptimistic = m.perspective === "optimistic";
                const isPessimistic = m.perspective === "pessimistic";
                const isSynthesis = m.perspective === "synthesis";
                const hasDebatePerspective = isOptimistic || isPessimistic || isSynthesis;

                const perspectiveStyles = hasDebatePerspective && m.role === "assistant"
                  ? {
                      background: isSynthesis ? "#F5F3FF" : isOptimistic ? "#F0FDF4" : "#FEF2F2",
                      border: isSynthesis ? "1.5px solid #8B5CF6" : isOptimistic ? "1.5px solid #22C55E" : "1.5px solid #EF4444",
                      color: "var(--ink)",
                    }
                  : m.role === "assistant"
                    ? { background: "var(--bg-subtle)", border: "1px solid var(--card-border)", color: "var(--ink)" }
                    : { background: "var(--accent)", color: "#FFFFFF" };

                return (
                  <div key={idx} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
                    <div
                      className={`rounded-2xl px-4 py-3 text-sm ${hasDebatePerspective && m.role === "assistant" ? "max-w-[92%]" : "max-w-[85%]"}`}
                      style={perspectiveStyles}
                    >
                      {m.role === "assistant" ? (
                        <>
                          {/* Debate perspective label */}
                          {hasDebatePerspective && (
                            <div
                              className="mb-2 flex items-center gap-1.5 text-[12px] font-bold"
                              style={{ color: isSynthesis ? "#7C3AED" : isOptimistic ? "#16A34A" : "#DC2626" }}
                            >
                              <span>{isSynthesis ? "🟣" : isOptimistic ? "🟢" : "🔴"}</span>
                              {isSynthesis ? "통합 메리" : isOptimistic ? "긍정 메리" : "비관 메리"}
                            </div>
                          )}
                          {m.section && !hasDebatePerspective && (
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
                      <div className="mt-2 flex items-center gap-2 text-[10px] opacity-50">
                        <span>
                          {hasDebatePerspective && m.role === "assistant"
                            ? (isSynthesis ? "통합 메리" : isOptimistic ? "긍정 메리" : "비관 메리")
                            : m.role === "user" ? "you" : "merry"} ·{" "}
                          {m.createdAt
                            ? new Date(m.createdAt).toLocaleString("ko-KR", {
                                timeZone: "Asia/Seoul",
                                month: "2-digit",
                                day: "2-digit",
                                hour: "2-digit",
                                minute: "2-digit",
                              })
                            : ""}
                        </span>
                        {m.role === "assistant" && !sending && (
                          <span className="flex items-center gap-1 ml-auto">
                            <button
                              onClick={async () => {
                                const desc = window.prompt("어떤 부분이 틀렸나요? (간단히 설명)");
                                if (!desc) return;
                                await fetch("/api/review/feedback", {
                                  method: "POST",
                                  headers: { "content-type": "application/json" },
                                  body: JSON.stringify({ sessionId, category: "analysis", description: desc, correction: "" }),
                                });
                                setRememberedToast("피드백이 기록됐어요");
                              }}
                              className="rounded p-0.5 transition-colors hover:bg-[var(--bg-subtle)]"
                              title="피드백 (틀린 부분 알려주기)"
                            >
                              <ThumbsDown className="h-3 w-3" />
                            </button>
                            <button
                              onClick={async () => {
                                const res = await fetch("/api/review/critique", {
                                  method: "POST",
                                  headers: { "content-type": "application/json" },
                                  body: JSON.stringify({ draft: m.content, refine: true }),
                                });
                                if (!res.ok) return;
                                const data = await res.json();
                                if (data.refinedDraft) {
                                  const refined: ReportMessage = {
                                    role: "assistant",
                                    content: `**[자체 개선안]**\n\n${data.critique}\n\n---\n\n${data.refinedDraft}`,
                                    createdAt: new Date().toISOString(),
                                    perspective: m.perspective,
                                    section: m.section,
                                  };
                                  setMessages((prev) => {
                                    const next = [...prev];
                                    next.splice(idx + 1, 0, refined);
                                    return next;
                                  });
                                }
                              }}
                              className="rounded p-0.5 transition-colors hover:bg-[var(--bg-subtle)]"
                              title="자체 개선안 보기 (GOLF Self-Critique)"
                            >
                              <RotateCcw className="h-3 w-3" />
                            </button>
                          </span>
                        )}
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
            {/* Debate completion — user picks perspective */}
            {debateStarted && !debating && !sending && (
              <div
                className="mx-auto max-w-md rounded-2xl px-5 py-4 text-center"
                style={{
                  background: "var(--bg-subtle)",
                  border: "1.5px solid var(--card-border)",
                }}
              >
                <p className="text-[13px] font-bold" style={{ color: "var(--ink)" }}>
                  어떤 관점이 더 설득력 있나요?
                </p>
                <p className="mt-1 text-[11px]" style={{ color: "var(--ink-light)" }}>
                  선택한 관점을 기반으로 보고서를 작성할 수 있어요
                </p>
                <div className="mt-3 flex gap-2 justify-center">
                  <button
                    onClick={() => {
                      sendMessage("긍정 메리의 관점을 기반으로 투자심사 보고서를 작성해줘. 긍정적 요소를 중심으로 하되 리스크도 함께 언급해줘.", undefined, "optimistic");
                      setDebateStarted(false);
                    }}
                    className="flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-[12px] font-bold transition-all hover:scale-[1.02]"
                    style={{ background: "#22C55E", color: "#fff" }}
                  >
                    🟢 긍정 관점 선택
                  </button>
                  <button
                    onClick={() => {
                      sendMessage("비관 메리의 관점을 기반으로 투자심사 보고서를 작성해줘. 리스크와 우려를 중심으로 하되 극복 방안도 함께 언급해줘.", undefined, "pessimistic");
                      setDebateStarted(false);
                    }}
                    className="flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-[12px] font-bold transition-all hover:scale-[1.02]"
                    style={{ background: "#EF4444", color: "#fff" }}
                  >
                    🔴 비관 관점 선택
                  </button>
                  <button
                    onClick={() => {
                      sendMessage("긍정 메리와 비관 메리의 분석을 변증법적으로 통합해줘. 양쪽의 근거 있는 주장만 채택하고, Bull/Bear Case를 병렬로 정리하고, Kill Scenario를 도출해줘.", undefined, "synthesis");
                      setDebateStarted(false);
                    }}
                    className="flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-[12px] font-bold transition-all hover:scale-[1.02]"
                    style={{ background: "#8B5CF6", color: "#fff" }}
                  >
                    🟣 양쪽 통합 합성
                  </button>
                </div>
                <button
                  onClick={() => setDebateStarted(false)}
                  className="mt-2 text-[11px] underline"
                  style={{ color: "var(--ink-light)" }}
                >
                  선택하지 않고 자유 대화 계속
                </button>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* ── Input area ── */}
        <div className="shrink-0 border-t border-[var(--line)] px-6 py-4">
          <div className="mx-auto max-w-3xl">
            {/* Upload status bar */}
            {uploadingFiles.length > 0 && (
              <div className="mb-2 space-y-1">
                {uploadingFiles.map((uf, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs"
                    style={{
                      background: uf.status === "error" ? "#FEF2F2" : "var(--bg-subtle)",
                      border: `1px solid ${uf.status === "error" ? "#FECACA" : "var(--card-border)"}`,
                      color: uf.status === "error" ? "#DC2626" : "var(--ink-light)",
                    }}
                  >
                    {uf.status === "done" ? (
                      <Check className="h-3.5 w-3.5 text-green-500" />
                    ) : uf.status === "error" ? (
                      <X className="h-3.5 w-3.5" />
                    ) : (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    )}
                    <FileText className="h-3.5 w-3.5" />
                    <span className="truncate">{uf.file.name}</span>
                    <span className="ml-auto shrink-0">
                      {uf.status === "uploading" && "업로드 중..."}
                      {uf.status === "parsing" && "분석 중..."}
                      {uf.status === "done" && "완료!"}
                      {uf.status === "error" && (uf.error || "실패")}
                    </span>
                  </div>
                ))}
              </div>
            )}
            <div className="flex gap-3">
              {/* File upload button */}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.xlsx,.xls,.docx,.png,.jpg,.jpeg,.gif,.webp,.txt,.md,.csv,.json,.tsv,.log,.xml,.html,.htm,.yaml,.yml"
                className="hidden"
                onChange={(e) => {
                  const files = Array.from(e.target.files ?? []);
                  for (const f of files) handleFileUpload(f);
                  e.target.value = "";
                }}
              />
              <Button
                variant="secondary"
                onClick={() => fileInputRef.current?.click()}
                disabled={sending}
                className="shrink-0 self-end"
                title="파일 첨부 (PDF, XLSX, DOCX)"
              >
                <Paperclip className="h-4 w-4" />
              </Button>
              {/* Market search button */}
              <div className="relative shrink-0 self-end">
                <Button
                  variant="secondary"
                  onClick={() => setSearchOpen((v) => !v)}
                  disabled={sending || searching}
                  title="시장 검색 (뉴스, 시그널)"
                >
                  {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                </Button>
                {searchOpen && (
                  <div
                    className="absolute bottom-full left-0 mb-1 rounded-lg border shadow-lg"
                    style={{ background: "var(--bg)", borderColor: "var(--card-border)", minWidth: 160 }}
                  >
                    <button
                      onClick={() => handleMarketSearch("news")}
                      className="block w-full px-4 py-2 text-left text-sm hover:bg-[var(--bg-subtle)]"
                      style={{ color: "var(--ink)" }}
                    >
                      📰 뉴스 다이제스트
                    </button>
                    <button
                      onClick={() => handleMarketSearch("signals")}
                      className="block w-full px-4 py-2 text-left text-sm hover:bg-[var(--bg-subtle)]"
                      style={{ color: "var(--ink)" }}
                    >
                      📡 시그널 레이더
                    </button>
                  </div>
                )}
              </div>
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
            onStartDebate={startDebate}
            sending={sending}
            debating={debating}
            maxAutoReached={maxAutoReached}
            meta={{
              title: meta?.title,
              companyName: meta?.companyName,
              date: meta?.reportDate,
            }}
          />
        </div>
      )}

      {/* ── Compile modal ── */}
      {showCompile && <CompileModal
        messages={messages}
        meta={meta}
        decisions={decisions}
        sessionId={sessionId}
        onClose={() => setShowCompile(false)}
        onMessagesUpdate={loadMessages}
      />}

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
