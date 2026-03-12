"use client";

import Link from "next/link";
import * as React from "react";
import { useParams } from "next/navigation";
import { ArrowRight, BookOpen, Check, ClipboardCopy, Download, FileText, GitBranch, PanelRightClose, RefreshCw, Sparkles, X } from "lucide-react";
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
  const reportDate = meta?.reportDate ? `- 작성일: ${meta.reportDate}\n` : "";
  const fileTitle = meta?.fileTitle ? `- 파일 제목: ${meta.fileTitle}\n` : "";
  const fund = meta?.fundName ? `- 펀드: ${meta.fundName}\n` : meta?.fundId ? `- 펀드: ${meta.fundId}\n` : "";
  const context = `${company}${author}${reportDate}${fileTitle}${fund}`.trim();

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

function isDecisionMessage(content: string): boolean {
  return content.startsWith(DECISION_PREFIX);
}

function isBranchMessage(content: string): boolean {
  return content.startsWith(BRANCH_PREFIX);
}

function isSystemMessage(content: string): boolean {
  return isDecisionMessage(content) || isBranchMessage(content);
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
  onClose,
}: {
  messages: ReportMessage[];
  meta: ReportSessionMeta | null;
  decisions: DecisionRecord[];
  onClose: () => void;
}) {
  const compiled = compileReport(messages, meta, decisions);
  const filename = `${meta?.companyName || "report"}_투자심사보고서`;

  // Editable section contents — initialized from compiled
  const [editSections, setEditSections] = React.useState<Record<string, string>>(() => {
    const map: Record<string, string> = {};
    for (const s of compiled.sections) {
      map[s.key] = s.content;
    }
    return map;
  });

  const [editingKey, setEditingKey] = React.useState<string | null>(null);
  const [copied, setCopied] = React.useState(false);

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
      const done = !!editSections[sec.key];
      lines.push(`${done ? "- [x]" : "- [ ]"} ${sec.index}. ${sec.title}`);
    }
    lines.push("");
    lines.push("---");
    lines.push("");

    // Sections
    for (const sec of TOC_SECTIONS) {
      const content = editSections[sec.key];
      if (content) {
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
  const completedCount = Object.values(editSections).filter(Boolean).length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.4)" }} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div
        className="relative mx-4 flex max-h-[90vh] w-full max-w-3xl flex-col rounded-2xl shadow-2xl"
        style={{ background: "var(--bg)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4" style={{ borderColor: "var(--line)" }}>
          <div>
            <h2 className="text-base font-bold" style={{ color: "var(--ink)" }}>합본 생성</h2>
            <p className="mt-0.5 text-[12px]" style={{ color: "var(--ink-light)" }}>
              {completedCount}/{TOC_SECTIONS.length} 섹션 · 클릭하여 편집, 다운로드로 내보내기
            </p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 hover:bg-[var(--bg-subtle)]">
            <X className="h-4 w-4" style={{ color: "var(--ink-light)" }} />
          </button>
        </div>

        {/* Section editor */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {TOC_SECTIONS.map((sec) => {
            const content = editSections[sec.key] || "";
            const isEditing = editingKey === sec.key;
            const hasContent = !!content.trim();

            return (
              <div
                key={sec.key}
                className="rounded-xl transition-all"
                style={{
                  border: isEditing
                    ? "1.5px solid var(--accent)"
                    : hasContent
                      ? "1px solid var(--card-border)"
                      : "1px dashed var(--card-border)",
                  background: isEditing ? "var(--accent-dim)" : hasContent ? "var(--bg)" : "var(--bg-subtle)",
                }}
              >
                {/* Section header */}
                <div
                  className="flex items-center justify-between px-4 py-2.5 cursor-pointer"
                  onClick={() => {
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
                        background: hasContent ? "var(--accent)" : "var(--card-border)",
                        color: hasContent ? "#fff" : "var(--ink-light)",
                      }}
                    >
                      {hasContent ? <Check className="h-3 w-3" /> : sec.index}
                    </div>
                    <span
                      className="text-[13px] font-semibold"
                      style={{ color: hasContent ? "var(--ink)" : "var(--muted)" }}
                    >
                      {sec.index}. {sec.title}
                    </span>
                  </div>
                  {hasContent && (
                    <span className="text-[10px]" style={{ color: "var(--ink-light)" }}>
                      {isEditing ? "편집 중" : "클릭하여 편집"}
                    </span>
                  )}
                  {!hasContent && (
                    <span className="text-[10px]" style={{ color: "var(--muted)" }}>미작성</span>
                  )}
                </div>

                {/* Editor */}
                {isEditing && (
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
                        style={{ color: "var(--accent-pink)" }}
                      >
                        섹션 제거
                      </button>
                    </div>
                  </div>
                )}

                {/* Collapsed preview */}
                {!isEditing && hasContent && (
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
            onClick={() => downloadFile(editedMd, `${filename}.md`, "text/markdown")}
          >
            <Download className="h-3.5 w-3.5" />
            Markdown
          </Button>
          <Button
            variant="secondary"
            size="sm"
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
            {compiled.missingSections.length > 0 && (
              <span>미작성 {compiled.missingSections.length}개</span>
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

      {/* ── Compile modal ── */}
      {showCompile && <CompileModal
        messages={messages}
        meta={meta}
        decisions={decisions}
        onClose={() => setShowCompile(false)}
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
