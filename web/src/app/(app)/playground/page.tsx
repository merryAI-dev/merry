"use client";

import * as React from "react";
import { Loader2, Upload } from "lucide-react";
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
  method?: "pymupdf" | "nova_hybrid" | "nova_presentation" | "nova_error";
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

/* ── Markdown builder — 사용자 콘텐츠만, 기술 메타데이터 없음 ── */

function buildMarkdown(result: ParseResult): string {
  if (!result.ok) return `오류가 발생했습니다: ${result.error ?? "알 수 없는 오류"}`;

  const lines: string[] = [];

  // 문서 종류 헤더
  const docLabel = result.doc_type
    ? (DOC_TYPE_LABELS[result.doc_type] ?? result.doc_type)
    : "미분류 문서";

  lines.push(`## 문서 종류 : ${docLabel}`);

  if (!result.doc_type && result.description) {
    lines.push(`\n${result.description}`);
  }

  lines.push("");

  // Nova 시각 인식 결과 (스캔 또는 슬라이드 문서)
  const vd = result.visual_description;
  if (vd && !vd.error) {
    if (vd.structure_notes?.trim()) {
      lines.push(`*${vd.structure_notes.trim()}*\n`);
    }
    if (vd.readable_text?.trim()) {
      lines.push(vd.readable_text.trim());
    }
    lines.push("");
    // 발표자료는 Nova 구조화 결과 우선, PyMuPDF 원문은 하단에 추가 참고
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

/* ── Cost helper ── */

function formatCost(method?: string, pages?: number): string {
  if (method === "nova_presentation") {
    // Nova Pro: ~$0.0008/1K input + $0.0032/1K output
    // 1페이지당 ~$0.002, 기본 7페이지 기준 ~$0.015
    const p = pages ?? 7;
    const est = p * 0.002;
    return `~$${est.toFixed(3)}`;
  }
  if (method === "nova_hybrid") {
    // Nova Pro OCR: 1페이지 ~$0.0025
    return "~$0.003";
  }
  return "$0.00";
}

/* ── Component ── */

export default function PlaygroundPage() {
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);
  const [filename, setFilename] = React.useState<string>("");
  const [result, setResult] = React.useState<ParseResult | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [tab, setTab] = React.useState<"markdown" | "raw">("markdown");

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
    setResult(null);
    setBusy(true);

    const form = new FormData();
    form.append("file", f);

    fetch("/api/ralph/parse", { method: "POST", body: form })
      .then((r) => r.json())
      .then((data: ParseResult) => setResult(data))
      .catch((e: Error) => setResult({ ok: false, error: e.message }))
      .finally(() => setBusy(false));
  }, []);

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

  const markdownContent = React.useMemo(
    () => (result ? buildMarkdown(result) : ""),
    [result],
  );

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
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-[#E5E8EB] bg-white">
          {previewUrl ? (
            <>
              {/* 파일명만 — iframe이 자체 PDF 컨트롤을 갖고 있으므로 별도 컨트롤 없음 */}
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
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
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
            {(["markdown", "raw"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`border-b-2 px-3 py-3 text-sm font-medium transition-colors ${
                  tab === t
                    ? "border-[#191F28] text-[#191F28]"
                    : "border-transparent text-[#8B95A1] hover:text-[#191F28]"
                }`}
              >
                {t === "markdown" ? "Markdown Viewer" : "Raw Conversion Result"}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="min-h-0 flex-1 overflow-auto p-6">
            {busy ? (
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

          {/* Footer — 기술 메타데이터 + 비용 (작게) */}
          {result?.ok && (
            <div className="flex items-center justify-between border-t border-[#E5E8EB] px-4 py-2">
              <span className="text-xs text-[#B0B8C1]">
                {result.pages}p
                {result.detection_method && result.detection_method !== "none" && ` · ${result.detection_method}`}
                {result.confidence !== undefined && result.confidence > 0 && ` · 신뢰도 ${(result.confidence * 100).toFixed(0)}%`}
              </span>
              <span className="text-xs text-[#B0B8C1]">
                {formatCost(result.method, result.pages)}
              </span>
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
