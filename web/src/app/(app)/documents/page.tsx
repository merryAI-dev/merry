"use client";

import * as React from "react";
import {
  ArrowRight,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  Plus,
  Sparkles,
  Trash2,
  Upload,
  XCircle,
} from "lucide-react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ReportSessionModal } from "@/components/report/ReportSessionModal";

/* ── Types ── */

type VisualDescription = {
  document_type?: string;
  readable_text?: string;
  structure_notes?: string;
  error?: string;
};

type ParseResult = {
  ok: boolean;
  error?: string;
  text?: string;
  pages?: number;
  method?: "pymupdf" | "nova_hybrid" | "nova_presentation" | "nova_error" | "nova_pro" | "xlsx";
  text_quality?: number;
  is_poor?: boolean;
  is_fragmented?: boolean;
  text_structure?: "document" | "presentation" | "image";
  doc_type?: string | null;
  confidence?: number;
  detection_method?: string;
  description?: string | null;
  visual_description?: VisualDescription | null;
  company_name?: string | null;
};

type ConditionCheck = {
  condition: string;
  result: boolean;
  evidence: string;
};

type CheckResult = {
  ok: boolean;
  error?: string;
  company_name?: string | null;
  conditions?: ConditionCheck[];
  parse_warning?: string;
  raw_response?: string;
};

type FileEntry = {
  id: string;
  file: File;
  previewUrl: string;
  status: "pending" | "parsing" | "done" | "error";
  result: ParseResult | null;
};

/* ── Constants ── */

const DOC_TYPE_LABELS: Record<string, string> = {
  business_reg: "사업자등록증",
  financial_stmt: "재무제표",
  shareholder: "주주명부",
  investment_review: "투자검토자료",
  employee_list: "임직원명부",
  certificate: "인증서",
  startup_cert: "창업기업확인서",
  articles: "정관",
  corp_registry: "법인등기부등본",
  spreadsheet: "스프레드시트",
};

const MAX_CONDITIONS = 6;

/* ── Helpers ── */

let fileIdCounter = 0;
function nextId() {
  return `f_${++fileIdCounter}_${Date.now()}`;
}

function isSupportedDocument(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith(".pdf") || name.endsWith(".xlsx") || name.endsWith(".xls");
}

function formatPageLabel(result: ParseResult): string | null {
  if (!result.pages) return null;
  if (result.method === "xlsx") return `${result.pages} sheet${result.pages > 1 ? "s" : ""}`;
  return `${result.pages}p`;
}

/** Check if a string has meaningful content (not just whitespace/invisible chars) */
function hasMeaningfulContent(s?: string | null): boolean {
  if (!s) return false;
  // Strip all whitespace, control chars, zero-width chars
  const stripped = s.replace(/[\s\u200B-\u200D\uFEFF\u00A0]/g, "");
  return stripped.length > 20;
}

function buildMarkdown(result: ParseResult): string {
  if (!result.ok) return `오류: ${result.error ?? "알 수 없는 오류"}`;

  const lines: string[] = [];

  // Document type header
  const docLabel = result.doc_type
    ? (DOC_TYPE_LABELS[result.doc_type] ?? result.doc_type)
    : result.visual_description?.document_type || "미분류 문서";

  lines.push(`## 문서 종류 : ${docLabel}`);
  if (!result.doc_type && result.description) {
    lines.push(`\n${result.description}`);
  }

  // Metadata summary bar
  const metaParts: string[] = [];
  const pageLabel = formatPageLabel(result);
  if (pageLabel) metaParts.push(pageLabel);
  if (result.method) metaParts.push(`방법: ${result.method}`);
  if (typeof result.text_quality === "number") metaParts.push(`품질: ${(result.text_quality * 100).toFixed(0)}%`);
  if (result.is_fragmented) metaParts.push("⚠ 파편화");
  if (result.text_structure) metaParts.push(`구조: ${result.text_structure}`);
  if (metaParts.length > 0) {
    lines.push(`\n> ${metaParts.join(" · ")}`);
  }
  lines.push("");

  // Determine which text source is better
  const vd = result.visual_description;
  const vdText = vd?.readable_text;
  const rawText = result.text;
  const vdUseful = hasMeaningfulContent(vdText);
  const rawUseful = hasMeaningfulContent(rawText);

  // Prefer the richer text source
  const rawLen = rawText?.replace(/\s/g, "").length ?? 0;
  const vdLen = vdText?.replace(/[\s\u200B-\u200D\uFEFF\u00A0]/g, "").length ?? 0;

  if (vdUseful && rawUseful) {
    // Both available — use whichever is richer, show other as fallback
    if (rawLen >= vdLen * 0.8) {
      // Raw text is comparable or better
      if (vd?.structure_notes?.trim()) lines.push(`*${vd.structure_notes.trim()}*\n`);
      lines.push(rawText!.trim());
      if (vdLen > rawLen * 1.2) {
        lines.push("\n---\n");
        lines.push("**Visual 추출 결과**\n");
        lines.push(vdText!.trim());
      }
    } else {
      // VD is significantly richer
      if (vd?.structure_notes?.trim()) lines.push(`*${vd.structure_notes.trim()}*\n`);
      lines.push(vdText!.trim());
      lines.push("\n---\n");
      lines.push("**원문 텍스트**\n");
      lines.push(rawText!.trim());
    }
  } else if (rawUseful) {
    // Only raw text is useful
    lines.push(rawText!.trim());
  } else if (vdUseful) {
    // Only VD is useful
    if (vd?.structure_notes?.trim()) lines.push(`*${vd.structure_notes.trim()}*\n`);
    lines.push(vdText!.trim());
  } else {
    lines.push("*추출된 텍스트가 없습니다.*");
  }

  return lines.join("\n");
}

function getExtractedText(result: ParseResult): string {
  const vd = result.visual_description;
  const parts: string[] = [];
  // Prefer the richer source first
  const rawUseful = hasMeaningfulContent(result.text);
  const vdUseful = hasMeaningfulContent(vd?.readable_text);
  if (rawUseful) parts.push(result.text!.trim());
  if (vdUseful && vd?.readable_text) parts.push(vd.readable_text.trim());
  return parts.join("\n\n");
}

function formatCost(method?: string, pages?: number): string {
  if (method === "nova_presentation") return `~$${((pages ?? 7) * 0.002).toFixed(3)}`;
  if (method === "nova_hybrid") return "~$0.003";
  if (method === "nova_pro") return "~$0.006";
  return "$0.00";
}

/* ── Component ── */

export default function DocumentsPage() {
  const router = useRouter();
  const [entries, setEntries] = React.useState<FileEntry[]>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [tab, setTab] = React.useState<"markdown" | "raw" | "check">("markdown");

  // condition check state
  const [conditions, setConditions] = React.useState<string[]>([""]);
  const [checkResult, setCheckResult] = React.useState<CheckResult | null>(null);
  const [checkBusy, setCheckBusy] = React.useState(false);

  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const selected = entries.find((e) => e.id === selectedId) ?? null;
  const doneCount = entries.filter((e) => e.status === "done").length;
  const errorCount = entries.filter((e) => e.status === "error").length;
  const parsingCount = entries.filter((e) => e.status === "parsing").length;

  // Cleanup preview URLs
  React.useEffect(() => {
    return () => {
      entries.forEach((e) => URL.revokeObjectURL(e.previewUrl));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── File handling ── */

  function addFiles(fileList: File[]) {
    const supported = fileList.filter(isSupportedDocument);
    if (supported.length === 0) return;

    const newEntries: FileEntry[] = supported.map((f) => ({
      id: nextId(),
      file: f,
      previewUrl: URL.createObjectURL(f),
      status: "pending" as const,
      result: null,
    }));

    setEntries((prev) => [...prev, ...newEntries]);

    // Auto-select first if none selected
    if (!selectedId && newEntries.length > 0) {
      setSelectedId(newEntries[0].id);
    }

    // Start parsing each file
    for (const entry of newEntries) {
      parseFile(entry.id, entry.file);
    }
  }

  async function callParse(file: File, forcePro: boolean): Promise<ParseResult> {
    // Step 1: Get presigned URL from S3
    const presignRes = await fetch("/api/uploads/presign", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: file.name,
        contentType: file.type || "application/pdf",
        sizeBytes: file.size,
      }),
    });
    if (!presignRes.ok) {
      const err = await presignRes.json().catch(() => ({ error: "PRESIGN_FAILED" }));
      throw new Error(err.error ?? `Presign failed: ${presignRes.status}`);
    }
    const presign = await presignRes.json();

    // Step 2: Upload directly to S3 (bypasses Vercel 4.5MB limit)
    const putRes = await fetch(presign.upload.url, {
      method: "PUT",
      headers: presign.upload.headers,
      body: file,
    });
    if (!putRes.ok) throw new Error(`S3 upload failed: ${putRes.status}`);

    // Step 3: Confirm upload
    await fetch("/api/uploads/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fileId: presign.file.fileId }),
    });

    // Step 4: Parse via S3 key (no file in body — just reference)
    const res = await fetch("/api/ralph/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        s3Key: presign.file.key,
        s3Bucket: presign.file.bucket,
        filename: file.name,
        force_pro: forcePro,
      }),
    });

    const contentType = res.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      const text = await res.text().catch(() => "");
      throw new Error(text.slice(0, 100) || `HTTP ${res.status}`);
    }

    return (await res.json()) as ParseResult;
  }

  async function parseFile(id: string, file: File, forcePro = false) {
    setEntries((prev) =>
      prev.map((e) => (e.id === id ? { ...e, status: "parsing", result: null } : e)),
    );

    try {
      let data = await callParse(file, forcePro);

      // Auto-retry with Nova Pro if quality is poor or text looks broken
      const needsRetry =
        data.ok &&
        !forcePro &&
        (data.is_poor ||
          data.is_fragmented ||
          (typeof data.text_quality === "number" && data.text_quality < 0.5) ||
          data.text_structure === "image" ||
          data.text_structure === "presentation");

      if (needsRetry) {
        try {
          const retried = await callParse(file, true);
          if (retried.ok) data = retried;
        } catch {
          // keep original data if retry fails
        }
      }

      setEntries((prev) =>
        prev.map((e) =>
          e.id === id ? { ...e, status: data.ok ? "done" : "error", result: data } : e,
        ),
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "UNKNOWN";

      // If initial attempt failed entirely, try once with Nova Pro
      if (!forcePro) {
        try {
          const retryData = await callParse(file, true);
          setEntries((prev) =>
            prev.map((e) =>
              e.id === id
                ? { ...e, status: retryData.ok ? "done" : "error", result: retryData }
                : e,
            ),
          );
          return;
        } catch {
          // Fall through to original error
        }
      }

      setEntries((prev) =>
        prev.map((e) =>
          e.id === id ? { ...e, status: "error", result: { ok: false, error: msg } } : e,
        ),
      );
    }
  }

  function removeEntry(id: string) {
    setEntries((prev) => {
      const entry = prev.find((e) => e.id === id);
      if (entry) URL.revokeObjectURL(entry.previewUrl);
      return prev.filter((e) => e.id !== id);
    });
    if (selectedId === id) {
      setSelectedId((prev) => {
        const remaining = entries.filter((e) => e.id !== id);
        return remaining.length > 0 ? remaining[0].id : null;
      });
    }
  }

  function handleForcePro(entry: FileEntry) {
    parseFile(entry.id, entry.file, true);
  }

  /* ── Condition check ── */

  function handleCheck() {
    if (!selected?.result?.ok) return;
    const filled = conditions.filter((c) => c.trim());
    if (!filled.length) return;

    setCheckResult(null);
    setCheckBusy(true);

    const text = getExtractedText(selected.result);
    const form = new FormData();
    form.append("text", text);
    filled.forEach((c) => form.append("conditions", c));

    fetch("/api/ralph/check", { method: "POST", body: form })
      .then((r) => r.json())
      .then((data: CheckResult) => setCheckResult(data))
      .catch((e: Error) => setCheckResult({ ok: false, error: e.message }))
      .finally(() => setCheckBusy(false));
  }

  /* ── Download combined markdown ── */

  function downloadMarkdown() {
    const doneEntries = entries.filter((e) => e.status === "done" && e.result?.ok);
    if (doneEntries.length === 0) return;

    const parts: string[] = [];
    parts.push("# 문서 추출 합본\n");
    parts.push(`> 추출일시: ${new Date().toLocaleString("ko-KR")}`);
    parts.push(`> 총 ${doneEntries.length}건\n`);
    parts.push("---\n");

    // TOC
    parts.push("## 목차\n");
    doneEntries.forEach((entry, i) => {
      const docType = entry.result?.doc_type
        ? (DOC_TYPE_LABELS[entry.result.doc_type] ?? entry.result.doc_type)
        : "미분류";
      parts.push(`${i + 1}. **${entry.file.name}** — ${docType}`);
    });
    parts.push("\n---\n");

    // Content per file
    doneEntries.forEach((entry, i) => {
      parts.push(`# ${i + 1}. ${entry.file.name}\n`);
      parts.push(buildMarkdown(entry.result!));
      parts.push("\n---\n");
    });

    const blob = new Blob([parts.join("\n")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `문서추출_합본_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  /* ── Start investment review with extracted data ── */

  const [showStartModal, setShowStartModal] = React.useState(false);

  function buildExtractedContext(): { context: string; companyName: string } {
    const doneEntries = entries.filter((e) => e.status === "done" && e.result?.ok);
    const context = doneEntries
      .map((entry) => {
        const docType = entry.result?.doc_type
          ? (DOC_TYPE_LABELS[entry.result.doc_type] ?? entry.result.doc_type)
          : "미분류";
        const text = getExtractedText(entry.result!).slice(0, 2000);
        return `### ${entry.file.name} (${docType})\n${text}`;
      })
      .join("\n\n---\n\n");

    // 사업자등록증/투자검토서에서 기업명 힌트 추출
    const bizEntry = doneEntries.find(
      (e) => e.result?.doc_type === "business_registration" || e.result?.doc_type === "investment_review",
    );
    const companyName = bizEntry?.result?.company_name ?? "";

    return { context, companyName };
  }

  function startReportWithExtraction() {
    const doneEntries = entries.filter((e) => e.status === "done" && e.result?.ok);
    if (doneEntries.length === 0) return;
    setShowStartModal(true);
  }

  /* ── Drag/drop/input ── */

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    addFiles(Array.from(e.dataTransfer.files));
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    addFiles(Array.from(e.target.files ?? []));
    e.target.value = "";
  }

  const TABS = [
    { id: "markdown" as const, label: "추출 결과" },
    { id: "raw" as const, label: "Raw JSON" },
    { id: "check" as const, label: "조건 검사" },
  ];

  const canCheck =
    selected?.result?.ok && !checkBusy && conditions.some((c) => c.trim());

  const { context: extractedContext, companyName: extractedCompanyName } = React.useMemo(
    () => buildExtractedContext(),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [entries],
  );

  return (
    <>
    {showStartModal && (
      <ReportSessionModal
        onClose={() => setShowStartModal(false)}
        extractedContext={extractedContext}
        initialCompanyName={extractedCompanyName}
      />
    )}
    <div className="flex h-[calc(100vh-5rem)] flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest" style={{ color: "var(--muted)" }}>
            RALPH
          </div>
          <h1 className="mt-0.5 text-2xl font-black tracking-tight" style={{ color: "var(--ink)" }}>
            문서 추출
          </h1>
          <p className="mt-1 text-sm" style={{ color: "var(--ink-light)" }}>
            PDF를 올리면 자동으로 문서 종류를 판별하고 내용을 추출합니다. 여러 파일을 한 번에 처리할 수 있어요.
          </p>
        </div>
        {doneCount > 0 && (
          <div className="flex items-center gap-2">
            <button
              onClick={downloadMarkdown}
              className="flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-colors"
              style={{
                background: "var(--bg-subtle)",
                border: "1px solid var(--card-border)",
                color: "var(--ink)",
              }}
            >
              <Download className="h-4 w-4" />
              합본 MD ({doneCount})
            </button>
            <button
              onClick={startReportWithExtraction}
              className="flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors"
              style={{
                background: "var(--accent)",
                color: "#FFFFFF",
              }}
            >
              <>
                투자심사 시작
                <ArrowRight className="h-4 w-4" />
              </>
            </button>
          </div>
        )}
      </div>

      {/* Main split panel */}
      <div className="flex min-h-0 flex-1 gap-4">
        {/* ── Left: File list + Preview ── */}
        <div
          className="flex w-72 shrink-0 flex-col overflow-hidden rounded-2xl"
          style={{ border: "1px solid var(--card-border)", background: "var(--card)" }}
        >
          {/* File list header */}
          <div
            className="flex items-center justify-between px-4 py-3"
            style={{ borderBottom: "1px solid var(--line)" }}
          >
            <span className="text-xs font-semibold" style={{ color: "var(--ink-light)" }}>
              파일 ({entries.length})
              {parsingCount > 0 && (
                <span style={{ color: "var(--accent)" }}> · {parsingCount}개 분석중</span>
              )}
            </span>
            <label
              htmlFor="doc-file-input"
              className="flex cursor-pointer items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium transition-colors"
              style={{ color: "var(--accent)" }}
            >
              <Plus className="h-3.5 w-3.5" />
              추가
            </label>
          </div>

          {/* File list */}
          <div
            className="flex-1 overflow-y-auto"
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
          >
            {entries.length === 0 ? (
              <label
                htmlFor="doc-file-input"
                className="flex flex-1 cursor-pointer flex-col items-center justify-center gap-3 p-6 text-center h-full"
              >
                <Upload className="h-8 w-8" style={{ color: "var(--card-border)" }} />
                <p className="text-sm" style={{ color: "var(--ink-light)" }}>
                  PDF 또는 Excel을 드래그하거나<br />클릭하여 업로드
                </p>
              </label>
            ) : (
              <div className="p-2 space-y-1">
                {entries.map((entry) => (
                  <button
                    key={entry.id}
                    onClick={() => {
                      setSelectedId(entry.id);
                      setCheckResult(null);
                    }}
                    className="group flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left transition-all"
                    style={{
                      background:
                        selectedId === entry.id ? "var(--bg-subtle)" : "transparent",
                      border:
                        selectedId === entry.id
                          ? "1px solid var(--card-border)"
                          : "1px solid transparent",
                    }}
                  >
                    {/* Status icon */}
                    {entry.status === "parsing" ? (
                      <Loader2
                        className="h-4 w-4 shrink-0 animate-spin"
                        style={{ color: "var(--accent)" }}
                      />
                    ) : entry.status === "done" ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                    ) : entry.status === "error" ? (
                      <XCircle className="h-4 w-4 shrink-0 text-rose-500" />
                    ) : (
                      <FileText
                        className="h-4 w-4 shrink-0"
                        style={{ color: "var(--muted)" }}
                      />
                    )}

                    <div className="min-w-0 flex-1">
                      <div
                        className="truncate text-sm font-medium"
                        style={{ color: "var(--ink)" }}
                      >
                        {entry.file.name}
                      </div>
                      <div className="flex items-center gap-1.5 text-[11px]" style={{ color: "var(--muted)" }}>
                        {entry.result?.doc_type && (
                          <span style={{ color: "var(--accent)" }}>
                            {DOC_TYPE_LABELS[entry.result.doc_type] ?? entry.result.doc_type}
                          </span>
                        )}
                        {entry.result && formatPageLabel(entry.result) && (
                          <span>{formatPageLabel(entry.result)}</span>
                        )}
                        {entry.result?.method && (
                          <span>{formatCost(entry.result.method, entry.result.pages)}</span>
                        )}
                      </div>
                    </div>

                    {/* Remove button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeEntry(entry.id);
                      }}
                      className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                      style={{ color: "var(--muted)" }}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Stats footer */}
          {entries.length > 0 && (
            <div
              className="flex items-center justify-between px-4 py-2 text-[11px]"
              style={{ borderTop: "1px solid var(--line)", color: "var(--muted)" }}
            >
              <span>
                {doneCount} 완료{errorCount > 0 && ` · ${errorCount} 실패`}
              </span>
              <span>
                {(entries.reduce((s, e) => s + e.file.size, 0) / 1024).toFixed(0)} KB
              </span>
            </div>
          )}
        </div>

        {/* ── Right: Result panel ── */}
        <div
          className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl"
          style={{ border: "1px solid var(--card-border)", background: "var(--card)" }}
        >
          {selected ? (
            <>
              {/* Tabs */}
              <div className="flex" style={{ borderBottom: "1px solid var(--line)" }}>
                <div className="flex flex-1 px-4">
                  {TABS.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setTab(t.id)}
                      className="px-3 py-3 text-sm font-medium transition-colors"
                      style={{
                        borderBottom: `2px solid ${tab === t.id ? "var(--ink)" : "transparent"}`,
                        color: tab === t.id ? "var(--ink)" : "var(--muted)",
                      }}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
                {/* Force Pro button */}
                {selected.result?.ok &&
                  selected.result.method !== "nova_presentation" &&
                  selected.result.method !== "nova_pro" &&
                  selected.result.method !== "xlsx" &&
                  selected.status !== "parsing" && (
                    <button
                      onClick={() => handleForcePro(selected)}
                      className="flex items-center gap-1 px-4 text-xs transition-colors"
                      style={{ color: "var(--muted)" }}
                    >
                      <Sparkles className="h-3 w-3" />
                      Nova Pro 재분석
                    </button>
                  )}
              </div>

              {/* Content */}
              <div className="min-h-0 flex-1 overflow-auto p-6">
                {tab === "check" ? (
                  /* ── 조건 검사 ── */
                  <div className="flex flex-col gap-5">
                    <div className="flex flex-col gap-2">
                      <p
                        className="text-xs font-medium uppercase tracking-widest"
                        style={{ color: "var(--muted)" }}
                      >
                        검사 조건
                      </p>
                      {conditions.map((cond, i) => (
                        <div key={i} className="flex items-center gap-2">
                          <span
                            className="w-4 shrink-0 text-right text-xs"
                            style={{ color: "var(--muted)" }}
                          >
                            {i + 1}
                          </span>
                          <input
                            type="text"
                            value={cond}
                            onChange={(e) =>
                              setConditions((prev) =>
                                prev.map((c, idx) => (idx === i ? e.target.value : c)),
                              )
                            }
                            placeholder="예: 창업 3년 미만인가?"
                            className="flex-1 rounded-lg px-3 py-2 text-sm outline-none"
                            style={{
                              border: "1px solid var(--card-border)",
                              color: "var(--ink)",
                              background: "var(--bg)",
                            }}
                          />
                          <button
                            onClick={() =>
                              setConditions((prev) =>
                                prev.length > 1 ? prev.filter((_, idx) => idx !== i) : [""],
                              )
                            }
                            className="transition-colors hover:text-rose-500"
                            style={{ color: "var(--muted)" }}
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      ))}
                      {conditions.length < MAX_CONDITIONS && (
                        <button
                          onClick={() => setConditions((prev) => [...prev, ""])}
                          className="flex items-center gap-1 text-sm transition-colors"
                          style={{ color: "var(--muted)" }}
                        >
                          <Plus className="h-4 w-4" />
                          조건 추가
                        </button>
                      )}
                    </div>

                    <button
                      onClick={handleCheck}
                      disabled={!canCheck}
                      className="flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium text-white transition-colors disabled:cursor-not-allowed disabled:opacity-40"
                      style={{ background: "var(--ink)" }}
                    >
                      {checkBusy ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          검사 중…
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4 w-4" />
                          Nova Pro로 조건 검사
                        </>
                      )}
                    </button>

                    {!selected.result?.ok && selected.status !== "parsing" && (
                      <p className="text-sm" style={{ color: "var(--muted)" }}>
                        먼저 PDF 또는 Excel 파일을 업로드하세요.
                      </p>
                    )}

                    {checkResult && (
                      <div className="flex flex-col gap-3">
                        {checkResult.ok ? (
                          <>
                            {checkResult.parse_warning && (
                              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
                                <p className="text-sm font-medium text-amber-900">
                                  모델 응답을 완전히 JSON으로 읽지 못해 복구된 결과를 표시합니다.
                                </p>
                              </div>
                            )}
                            {checkResult.company_name && (
                              <div
                                className="rounded-xl px-4 py-3"
                                style={{ background: "var(--bg-subtle)" }}
                              >
                                <span className="text-xs" style={{ color: "var(--muted)" }}>
                                  기업명
                                </span>
                                <p
                                  className="mt-0.5 text-base font-semibold"
                                  style={{ color: "var(--ink)" }}
                                >
                                  {checkResult.company_name}
                                </p>
                              </div>
                            )}
                            {checkResult.conditions?.map((c, i) => (
                              <div
                                key={i}
                                className={`flex gap-3 rounded-xl border px-4 py-3 ${
                                  c.result
                                    ? "border-emerald-200 bg-emerald-50"
                                    : "border-rose-200 bg-rose-50"
                                }`}
                              >
                                <span
                                  className={`mt-0.5 shrink-0 text-base font-bold ${
                                    c.result ? "text-emerald-600" : "text-rose-600"
                                  }`}
                                >
                                  {c.result ? "✓" : "✗"}
                                </span>
                                <div className="min-w-0">
                                  <p className="text-sm font-medium" style={{ color: "var(--ink)" }}>
                                    {c.condition}
                                  </p>
                                  <p className="mt-1 text-xs" style={{ color: "var(--ink-light)" }}>
                                    {c.evidence}
                                  </p>
                                </div>
                              </div>
                            ))}
                          </>
                        ) : (
                          <p className="text-sm text-rose-600">오류: {checkResult.error}</p>
                        )}
                      </div>
                    )}
                  </div>
                ) : selected.status === "parsing" ? (
                  <div
                    className="flex items-center gap-2 text-sm"
                    style={{ color: "var(--ink-light)" }}
                  >
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>{selected.file.name} 분석 중…</span>
                  </div>
                ) : selected.result ? (
                  tab === "markdown" ? (
                    <article className="prose prose-sm max-w-none prose-headings:text-[var(--ink)] prose-p:text-[var(--ink)] prose-li:text-[var(--ink)] prose-strong:text-[var(--ink)]">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {buildMarkdown(selected.result)}
                      </ReactMarkdown>
                    </article>
                  ) : (
                    <pre
                      className="whitespace-pre-wrap break-all font-mono text-xs"
                      style={{ color: "var(--ink)" }}
                    >
                      {JSON.stringify(selected.result, null, 2)}
                    </pre>
                  )
                ) : (
                  <p className="text-sm" style={{ color: "var(--muted)" }}>
                    왼쪽에서 파일을 선택하세요.
                  </p>
                )}
              </div>

              {/* Footer info */}
              {selected.result?.ok && (
                <div
                  className="flex items-center justify-between px-4 py-2 text-xs"
                  style={{ borderTop: "1px solid var(--line)", color: "var(--muted)" }}
                >
                  <span>
                    {formatPageLabel(selected.result) ?? "-"}
                    {selected.result.detection_method &&
                      selected.result.detection_method !== "none" &&
                      ` · ${selected.result.detection_method}`}
                    {selected.result.confidence !== undefined &&
                      selected.result.confidence > 0 &&
                      ` · 신뢰도 ${(selected.result.confidence * 100).toFixed(0)}%`}
                  </span>
                  <span>{formatCost(selected.result.method, selected.result.pages)}</span>
                </div>
              )}
            </>
          ) : (
            /* Empty state */
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
              <FileText className="h-10 w-10" style={{ color: "var(--card-border)" }} />
              <p className="text-sm" style={{ color: "var(--ink-light)" }}>
                PDF 또는 Excel 파일을 업로드하면 자동으로 분석이 시작됩니다
              </p>
              <label
                htmlFor="doc-file-input"
                className="flex cursor-pointer items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium text-white transition-colors"
                style={{ background: "var(--ink)" }}
              >
                <Upload className="h-4 w-4" />
                파일 업로드
              </label>
            </div>
          )}
        </div>
      </div>

      {/* Hidden file input */}
      <input
        id="doc-file-input"
        ref={fileInputRef}
        type="file"
        accept=".pdf,.xlsx,.xls"
        multiple
        className="hidden"
        onChange={handleInputChange}
      />
    </div>
    </>
  );
}
