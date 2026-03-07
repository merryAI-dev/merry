"use client";

import * as React from "react";
import { Loader2, Plus, Sparkles, Trash2, Upload } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
  method?: "pymupdf" | "nova_hybrid" | "nova_presentation" | "nova_error" | "nova_pro";
  text_quality?: number;
  is_poor?: boolean;
  is_fragmented?: boolean;
  text_structure?: "document" | "presentation" | "image";
  doc_type?: string | null;
  confidence?: number;
  detection_method?: string;
  description?: string | null;
  visual_description?: VisualDescription | null;
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
};

const MAX_CONDITIONS = 6;

/* ── Helpers ── */

function buildMarkdown(result: ParseResult): string {
  if (!result.ok) return `오류가 발생했습니다: ${result.error ?? "알 수 없는 오류"}`;

  const lines: string[] = [];

  const docLabel = result.doc_type
    ? (DOC_TYPE_LABELS[result.doc_type] ?? result.doc_type)
    : "미분류 문서";

  lines.push(`## 문서 종류 : ${docLabel}`);

  if (!result.doc_type && result.description) {
    lines.push(`\n${result.description}`);
  }

  lines.push("");

  const vd = result.visual_description;
  if (vd && !vd.error) {
    if (vd.structure_notes?.trim()) {
      lines.push(`*${vd.structure_notes.trim()}*\n`);
    }
    if (vd.readable_text?.trim()) {
      lines.push(vd.readable_text.trim());
    }
    lines.push("");
    if (result.text_structure === "presentation" && result.text?.trim()) {
      lines.push("\n---\n");
      lines.push("**원문 텍스트 (PyMuPDF)**\n");
      lines.push(result.text.trim());
    }
  } else if (result.text?.trim()) {
    lines.push(result.text.trim());
  } else {
    lines.push("*추출된 텍스트가 없습니다.*");
  }

  return lines.join("\n");
}

function getExtractedText(result: ParseResult): string {
  const vd = result.visual_description;
  const parts: string[] = [];
  if (vd && !vd.error && vd.readable_text?.trim()) {
    parts.push(vd.readable_text.trim());
  }
  if (result.text?.trim()) {
    parts.push(result.text.trim());
  }
  return parts.join("\n\n");
}

function formatCost(method?: string, pages?: number): string {
  if (method === "nova_presentation") {
    const p = pages ?? 7;
    return `~$${(p * 0.002).toFixed(3)}`;
  }
  if (method === "nova_hybrid") return "~$0.003";
  if (method === "nova_pro") return "~$0.006";
  return "$0.00";
}

/* ── Component ── */

export default function PlaygroundPage() {
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);
  const [filename, setFilename] = React.useState<string>("");
  const [currentFile, setCurrentFile] = React.useState<File | null>(null);
  const [result, setResult] = React.useState<ParseResult | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [tab, setTab] = React.useState<"markdown" | "raw" | "check">("markdown");

  // 조건 검사
  const [conditions, setConditions] = React.useState<string[]>([""]);
  const [checkResult, setCheckResult] = React.useState<CheckResult | null>(null);
  const [checkBusy, setCheckBusy] = React.useState(false);

  const fileInputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleFile = React.useCallback((f: File) => {
    if (!f.name.toLowerCase().endsWith(".pdf")) return;

    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(f);
    });

    setFilename(f.name);
    setCurrentFile(f);
    setResult(null);
    setCheckResult(null);
    setBusy(true);

    const form = new FormData();
    form.append("file", f);

    fetch("/api/ralph/parse", { method: "POST", body: form })
      .then((r) => r.json())
      .then((data: ParseResult) => setResult(data))
      .catch((e: Error) => setResult({ ok: false, error: e.message }))
      .finally(() => setBusy(false));
  }, []);

  const handleForcePro = React.useCallback(() => {
    if (!currentFile) return;
    setResult(null);
    setCheckResult(null);
    setBusy(true);
    const form = new FormData();
    form.append("file", currentFile);
    form.append("force_pro", "true");
    fetch("/api/ralph/parse", { method: "POST", body: form })
      .then((r) => r.json())
      .then((data: ParseResult) => setResult(data))
      .catch((e: Error) => setResult({ ok: false, error: e.message }))
      .finally(() => setBusy(false));
  }, [currentFile]);

  const handleCheck = React.useCallback(() => {
    if (!result?.ok) return;
    const filled = conditions.filter((c) => c.trim());
    if (!filled.length) return;

    setCheckResult(null);
    setCheckBusy(true);

    const text = getExtractedText(result);
    const form = new FormData();
    form.append("text", text);
    filled.forEach((c) => form.append("conditions", c));

    fetch("/api/ralph/check", { method: "POST", body: form })
      .then((r) => r.json())
      .then((data: CheckResult) => setCheckResult(data))
      .catch((e: Error) => setCheckResult({ ok: false, error: e.message }))
      .finally(() => setCheckBusy(false));
  }, [result, conditions]);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
    e.target.value = "";
  };

  const updateCondition = (i: number, val: string) => {
    setConditions((prev) => prev.map((c, idx) => (idx === i ? val : c)));
  };

  const addCondition = () => {
    if (conditions.length < MAX_CONDITIONS) {
      setConditions((prev) => [...prev, ""]);
    }
  };

  const removeCondition = (i: number) => {
    setConditions((prev) => prev.length > 1 ? prev.filter((_, idx) => idx !== i) : [""]);
  };

  const markdownContent = React.useMemo(
    () => (result ? buildMarkdown(result) : ""),
    [result],
  );

  const canCheck = result?.ok && !checkBusy && !busy && conditions.some((c) => c.trim());

  const TABS = [
    { id: "markdown" as const, label: "Markdown Viewer" },
    { id: "raw" as const, label: "Raw Conversion Result" },
    { id: "check" as const, label: "조건 검사" },
  ];

  return (
    <div className="flex h-[calc(100vh-5rem)] flex-col gap-4">
      {/* Header */}
      <div>
        <div className="text-xs font-semibold uppercase tracking-widest text-[#8B95A1]">RALPH</div>
        <h1 className="mt-0.5 text-2xl font-black tracking-tight text-[#191F28]">Playground</h1>
        <p className="mt-1 text-sm text-[#8B95A1]">
          문서를 업로드하면 레이아웃을 분석하고, 이미지 내 정보를 인식하며, RAG 전처리까지 한 번에 처리합니다.
        </p>
      </div>

      {/* Split Panel */}
      <div className="flex min-h-0 flex-1 gap-4">

        {/* ── Left: PDF Preview ── */}
        <div
          className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-[#E5E8EB] bg-white"
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
        >
          {previewUrl ? (
            <>
              <div className="flex items-center border-b border-[#E5E8EB] px-4 py-2">
                <span className="truncate text-sm text-[#8B95A1]">{filename}</span>
              </div>
              <iframe
                src={previewUrl}
                className="min-h-0 w-full flex-1"
                title="PDF Preview"
              />
            </>
          ) : (
            <label
              htmlFor="pdf-file-input"
              className="flex flex-1 cursor-pointer select-none flex-col items-center justify-center gap-3 text-center"
            >
              <Upload className="h-10 w-10 text-[#D1D5DC]" />
              <p className="text-sm text-[#8B95A1]">PDF를 여기에 놓거나 클릭하여 업로드하세요</p>
            </label>
          )}
        </div>

        {/* ── Right: Parse Result ── */}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-[#E5E8EB] bg-white">

          {/* Tabs */}
          <div className="flex border-b border-[#E5E8EB] px-4">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`border-b-2 px-3 py-3 text-sm font-medium transition-colors ${
                  tab === t.id
                    ? "border-[#191F28] text-[#191F28]"
                    : "border-transparent text-[#8B95A1] hover:text-[#191F28]"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="min-h-0 flex-1 overflow-auto p-6">
            {tab === "check" ? (
              /* ── 조건 검사 탭 ── */
              <div className="flex flex-col gap-5">
                {/* 조건 입력 */}
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-medium uppercase tracking-widest text-[#8B95A1]">
                    검사 조건
                  </p>
                  {conditions.map((cond, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className="w-4 shrink-0 text-right text-xs text-[#B0B8C1]">{i + 1}</span>
                      <input
                        type="text"
                        value={cond}
                        onChange={(e) => updateCondition(i, e.target.value)}
                        placeholder={`예: 창업 3년 미만인가?`}
                        className="flex-1 rounded-lg border border-[#E5E8EB] px-3 py-2 text-sm text-[#191F28] placeholder-[#D1D5DC] focus:border-[#191F28] focus:outline-none"
                      />
                      <button
                        onClick={() => removeCondition(i)}
                        className="text-[#D1D5DC] transition-colors hover:text-[#FF4B4B]"
                        title="조건 삭제"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                  {conditions.length < MAX_CONDITIONS && (
                    <button
                      onClick={addCondition}
                      className="flex items-center gap-1 text-sm text-[#8B95A1] transition-colors hover:text-[#191F28]"
                    >
                      <Plus className="h-4 w-4" />
                      조건 추가
                    </button>
                  )}
                </div>

                {/* 검사 버튼 */}
                <button
                  onClick={handleCheck}
                  disabled={!canCheck}
                  className="flex items-center justify-center gap-2 rounded-xl bg-[#191F28] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#2D3540] disabled:cursor-not-allowed disabled:opacity-40"
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

                {!result?.ok && !busy && (
                  <p className="text-sm text-[#B0B8C1]">먼저 PDF를 업로드하세요.</p>
                )}

                {/* 검사 결과 */}
                {checkResult && (
                  <div className="flex flex-col gap-3">
                    {checkResult.ok ? (
                      <>
                        {checkResult.parse_warning && (
                          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
                            <p className="text-sm font-medium text-amber-900">
                              모델 응답을 완전히 JSON으로 읽지 못해 복구된 결과를 표시하고 있습니다.
                            </p>
                            {checkResult.raw_response && (
                              <details className="mt-2">
                                <summary className="cursor-pointer text-xs text-amber-800">
                                  원본 응답 일부 보기
                                </summary>
                                <pre className="mt-2 whitespace-pre-wrap break-all rounded-lg bg-white/70 p-3 text-[11px] text-amber-950">
                                  {checkResult.raw_response}
                                </pre>
                              </details>
                            )}
                          </div>
                        )}
                        {checkResult.company_name && (
                          <div className="rounded-xl bg-[#F8F9FA] px-4 py-3">
                            <span className="text-xs text-[#8B95A1]">기업명</span>
                            <p className="mt-0.5 text-base font-semibold text-[#191F28]">
                              {checkResult.company_name}
                            </p>
                          </div>
                        )}
                        <div className="flex flex-col gap-2">
                          {checkResult.conditions?.map((c, i) => (
                            <div
                              key={i}
                              className={`flex gap-3 rounded-xl border px-4 py-3 ${
                                c.result
                                  ? "border-[#D1FAE5] bg-[#F0FDF4]"
                                  : "border-[#FEE2E2] bg-[#FFF5F5]"
                              }`}
                            >
                              <span
                                className={`mt-0.5 shrink-0 text-base font-bold ${
                                  c.result ? "text-[#16A34A]" : "text-[#DC2626]"
                                }`}
                              >
                                {c.result ? "✓" : "✗"}
                              </span>
                              <div className="min-w-0">
                                <p className="text-sm font-medium text-[#191F28]">{c.condition}</p>
                                <p className="mt-1 text-xs text-[#8B95A1]">{c.evidence}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </>
                    ) : (
                      <p className="text-sm text-[#DC2626]">
                        오류: {checkResult.error ?? "알 수 없는 오류"}
                      </p>
                    )}
                  </div>
                )}
              </div>
            ) : busy ? (
              <div className="flex items-center gap-2 text-sm text-[#8B95A1]">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>분석 중…</span>
              </div>
            ) : result ? (
              tab === "markdown" ? (
                <div className="prose prose-sm max-w-none text-[#191F28]">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {markdownContent}
                  </ReactMarkdown>
                </div>
              ) : (
                <pre className="whitespace-pre-wrap break-all font-mono text-xs text-[#191F28]">
                  {JSON.stringify(result, null, 2)}
                </pre>
              )
            ) : (
              <p className="text-sm text-[#8B95A1]">
                PDF를 업로드하면 파싱 결과가 여기에 표시됩니다.
              </p>
            )}
          </div>

          {/* Footer */}
          {result?.ok && (
            <div className="flex items-center justify-between border-t border-[#E5E8EB] px-4 py-2">
              <span className="text-xs text-[#B0B8C1]">
                {result.pages}p
                {result.detection_method && result.detection_method !== "none" && ` · ${result.detection_method}`}
                {result.confidence !== undefined && result.confidence > 0 && ` · 신뢰도 ${(result.confidence * 100).toFixed(0)}%`}
              </span>
              <div className="flex items-center gap-3">
                <span className="text-xs text-[#B0B8C1]">
                  {formatCost(result.method, result.pages)}
                </span>
                {result.method !== "nova_presentation" && result.method !== "nova_pro" && currentFile && !busy && (
                  <button
                    onClick={handleForcePro}
                    className="flex items-center gap-1 text-xs text-[#8B95A1] transition-colors hover:text-[#191F28]"
                  >
                    <Sparkles className="h-3 w-3" />
                    Nova Pro로 재분석
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom bar */}
      <div className="flex justify-end">
        <label
          htmlFor="pdf-file-input"
          className="flex cursor-pointer items-center gap-2 rounded-xl bg-[#191F28] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#2D3540]"
        >
          <Upload className="h-4 w-4" />
          Upload New File
        </label>
      </div>

      <input
        id="pdf-file-input"
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={handleInputChange}
      />
    </div>
  );
}
