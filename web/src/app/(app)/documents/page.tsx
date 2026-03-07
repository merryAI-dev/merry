"use client";

import * as React from "react";
import { CheckCircle2, Download, FileText, Loader2, UploadCloud, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { apiFetch } from "@/lib/apiClient";

/* ── Types ── */

type SupportedType = { value: string; label: string };

type ClassifiedFile = {
  fileId: string;
  filename: string;
  detectedType: string | null;
  confidence: number;
  selectedType: string; // user-confirmed
};

type JobStatus = "queued" | "running" | "succeeded" | "failed";
type JobArtifact = {
  artifactId: string;
  label: string;
  contentType: string;
  s3Bucket: string;
  s3Key: string;
  sizeBytes?: number;
};
type ResultSummary = {
  file_id: string;
  filename: string;
  doc_type: string;
  success: boolean;
  confidence: number;
  method: string;
};
type JobRecord = {
  jobId: string;
  status: JobStatus;
  title: string;
  createdAt: string;
  error?: string;
  artifacts?: JobArtifact[];
  metrics?: { results_summary?: ResultSummary[]; success_count?: number; failed_count?: number; total?: number };
};

type Stage = "upload" | "mapping" | "processing" | "results";

/* ── Helpers ── */


const DOC_TYPE_LABELS: Record<string, string> = {
  business_reg: "사업자등록증",
  financial_stmt: "재무제표",
  shareholder: "주주명부",
  investment_review: "투자검토자료",
  employee_list: "임직원명부",
  certificate: "인증서",
  startup_cert: "창업기업확인서",
  articles: "정관",
};

/* ── Component ── */

export default function DocumentsPage() {
  const [stage, setStage] = React.useState<Stage>("upload");
  const [files, setFiles] = React.useState<File[]>([]);
  const [classifiedFiles, setClassifiedFiles] = React.useState<ClassifiedFile[]>([]);
  const [supportedTypes, setSupportedTypes] = React.useState<SupportedType[]>([]);
  const [jobId, setJobId] = React.useState<string>("");
  const [job, setJob] = React.useState<JobRecord | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  /* ── Stage 1: Upload ── */

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files ?? []).filter((f) => f.name.endsWith(".pdf"));
    if (selected.length === 0) return;
    setFiles((prev) => [...prev, ...selected].slice(0, 20));
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files).filter((f) => f.name.endsWith(".pdf"));
    if (dropped.length === 0) return;
    setFiles((prev) => [...prev, ...dropped].slice(0, 20));
  }

  function removeFile(idx: number) {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  async function uploadAndClassify() {
    if (files.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      // Upload all files
      const fileIds: string[] = [];
      for (const f of files) {
        const presign = await apiFetch<{
          file: { fileId: string };
          upload: { url: string; headers: Record<string, string> };
        }>("/api/uploads/presign", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            filename: f.name,
            contentType: f.type || "application/pdf",
            sizeBytes: f.size,
          }),
        });

        const putRes = await fetch(presign.upload.url, {
          method: "PUT",
          headers: presign.upload.headers,
          body: f,
        });
        if (!putRes.ok) throw new Error("UPLOAD_FAILED");

        await apiFetch("/api/uploads/complete", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ fileId: presign.file.fileId }),
        });
        fileIds.push(presign.file.fileId);
      }

      // Classify
      const classifyRes = await apiFetch<{
        files: { fileId: string; filename: string; detectedType: string | null; confidence: number }[];
        supportedTypes: SupportedType[];
      }>("/api/ralph/classify", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ fileIds }),
      });

      setSupportedTypes(classifyRes.supportedTypes);
      setClassifiedFiles(
        classifyRes.files.map((f) => ({
          ...f,
          selectedType: f.detectedType ?? "",
        })),
      );
      setStage("mapping");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "FAILED";
      if (msg === "UPLOAD_FAILED") setError("S3 업로드 실패 — CORS/권한을 확인하세요.");
      else setError("업로드 또는 분류에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  /* ── Stage 2: HITL Mapping ── */

  function updateType(idx: number, type: string) {
    setClassifiedFiles((prev) => prev.map((f, i) => (i === idx ? { ...f, selectedType: type } : f)));
  }

  const mappedCount = classifiedFiles.filter((f) => f.selectedType).length;

  async function startExtraction() {
    const mapped = classifiedFiles.filter((f) => f.selectedType);
    if (mapped.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const typeMap: Record<string, string> = {};
      for (const f of mapped) {
        typeMap[f.fileId] = f.selectedType;
      }

      const res = await apiFetch<{ jobId: string }>("/api/jobs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          jobType: "document_extraction",
          fileIds: mapped.map((f) => f.fileId),
          params: { typeMap },
        }),
      });

      setJobId(res.jobId);
      setStage("processing");
    } catch {
      setError("잡 생성에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  /* ── Stage 3: Processing (polling) ── */

  const pollJob = React.useCallback(async () => {
    if (!jobId) return;
    try {
      const res = await apiFetch<{ jobs: JobRecord[] }>("/api/jobs");
      const found = (res.jobs || []).find((j: JobRecord) => j.jobId === jobId);
      if (found) {
        setJob(found);
        if (found.status === "succeeded" || found.status === "failed") {
          setStage("results");
        }
      }
    } catch {
      // silent
    }
  }, [jobId]);

  React.useEffect(() => {
    if (stage !== "processing") return;
    pollJob();
    const t = setInterval(pollJob, 5000);
    return () => clearInterval(t);
  }, [stage, pollJob]);

  /* ── Stage 4: Results ── */

  async function downloadArtifact(artifact: JobArtifact) {
    try {
      const res = await apiFetch<{ url: string }>(`/api/jobs/${jobId}/artifact?artifactId=${artifact.artifactId}`);
      window.open(res.url, "_blank", "noopener,noreferrer");
    } catch {
      setError("다운로드 URL 발급 실패");
    }
  }

  function reset() {
    setStage("upload");
    setFiles([]);
    setClassifiedFiles([]);
    setJobId("");
    setJob(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  /* ── Render ── */

  const stageLabels: Record<Stage, string> = {
    upload: "1. 업로드",
    mapping: "2. 문서 타입 확인",
    processing: "3. 추출 중",
    results: "4. 결과",
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="text-sm font-medium text-[#8B95A1]">RALPH Document Extraction</div>
        <h1 className="mt-1 font-black tracking-tight text-2xl text-[#191F28]">문서 일괄 추출</h1>
        <p className="mt-2 text-sm text-[#8B95A1]">
          PDF 문서를 업로드하면 자동 분류 후 구조화 데이터를 추출합니다. 문서 타입을 확인/수정한 뒤 실행하세요.
        </p>
      </div>

      {/* Stage Indicator */}
      <div className="flex items-center gap-2">
        {(["upload", "mapping", "processing", "results"] as Stage[]).map((s, i) => (
          <React.Fragment key={s}>
            {i > 0 && <div className="h-px w-6 bg-[#E5E8EB]" />}
            <Badge tone={stage === s ? "accent" : "neutral"}>{stageLabels[s]}</Badge>
          </React.Fragment>
        ))}
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
      )}

      {/* Stage 1: Upload */}
      {stage === "upload" && (
        <Card variant="strong" className="p-6">
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className="flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-[#E5E8EB] bg-white px-6 py-12 transition-colors hover:border-[color:var(--accent)]"
          >
            <UploadCloud className="h-10 w-10 text-[#8B95A1]" />
            <div className="text-sm text-[#8B95A1]">PDF 파일을 여기에 드래그하거나 클릭하세요 (최대 20개)</div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              multiple
              className="hidden"
              onChange={handleFileSelect}
            />
            <Button variant="secondary" onClick={() => fileInputRef.current?.click()}>
              파일 선택
            </Button>
          </div>

          {files.length > 0 && (
            <div className="mt-4 space-y-2">
              <div className="text-sm font-medium text-[#191F28]">{files.length}개 파일 선택됨</div>
              {files.map((f, i) => (
                <div
                  key={`${f.name}-${i}`}
                  className="flex items-center justify-between rounded-xl border border-[#E5E8EB] bg-white px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-[#8B95A1]" />
                    <span className="text-sm text-[#191F28]">{f.name}</span>
                    <span className="text-xs text-[#8B95A1]">({(f.size / 1024).toFixed(0)} KB)</span>
                  </div>
                  <button onClick={() => removeFile(i)} className="text-xs text-rose-500 hover:text-rose-700">
                    삭제
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="mt-5 flex justify-end">
            <Button variant="primary" onClick={uploadAndClassify} disabled={busy || files.length === 0}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
              업로드 & 분류
            </Button>
          </div>
        </Card>
      )}

      {/* Stage 2: HITL Mapping */}
      {stage === "mapping" && (
        <Card variant="strong" className="p-6">
          <div className="mb-4">
            <div className="text-sm font-semibold text-[#191F28]">문서 타입 확인</div>
            <div className="mt-1 text-sm text-[#8B95A1]">
              파일명에서 자동 감지된 타입을 확인하고, 필요 시 드롭다운으로 변경하세요.
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#E5E8EB] text-left text-xs font-medium text-[#8B95A1]">
                  <th className="px-3 py-2">파일명</th>
                  <th className="px-3 py-2">자동 감지</th>
                  <th className="px-3 py-2">문서 타입</th>
                </tr>
              </thead>
              <tbody>
                {classifiedFiles.map((f, idx) => (
                  <tr key={f.fileId} className="border-b border-[#E5E8EB]">
                    <td className="px-3 py-2 text-[#191F28]">{f.filename}</td>
                    <td className="px-3 py-2">
                      {f.detectedType ? (
                        <Badge tone="success">{DOC_TYPE_LABELS[f.detectedType] ?? f.detectedType}</Badge>
                      ) : (
                        <Badge tone="warn">미감지</Badge>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <select
                        className="h-9 rounded-lg border border-[#E5E8EB] bg-white px-2 text-sm text-[#191F28] outline-none focus:border-[color:var(--accent)]"
                        value={f.selectedType}
                        onChange={(e) => updateType(idx, e.target.value)}
                      >
                        <option value="">-- 선택 --</option>
                        {supportedTypes.map((t) => (
                          <option key={t.value} value={t.value}>
                            {t.label}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-5 flex items-center justify-between gap-3">
            <div className="text-sm text-[#8B95A1]">
              {mappedCount}/{classifiedFiles.length}개 매핑됨
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={reset}>
                처음으로
              </Button>
              <Button variant="primary" onClick={startExtraction} disabled={busy || mappedCount === 0}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                추출 실행 ({mappedCount}건)
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Stage 3: Processing */}
      {stage === "processing" && (
        <Card variant="strong" className="p-6">
          <div className="flex items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-[color:var(--accent)]" />
            <div>
              <div className="text-sm font-semibold text-[#191F28]">추출 진행 중...</div>
              <div className="mt-1 text-sm text-[#8B95A1]">
                잡 ID: <span className="font-mono">{jobId}</span> — 5초마다 상태를 확인합니다.
              </div>
            </div>
          </div>
          {job && (
            <div className="mt-4">
              <Badge tone={job.status === "running" ? "accent" : "neutral"}>{job.status}</Badge>
            </div>
          )}
        </Card>
      )}

      {/* Stage 4: Results */}
      {stage === "results" && job && (
        <div className="space-y-4">
          <Card variant="strong" className="p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-[#191F28]">추출 완료</div>
                <div className="mt-1 text-sm text-[#8B95A1]">
                  잡 ID: <span className="font-mono">{jobId}</span>
                </div>
              </div>
              <Badge tone={job.status === "succeeded" ? "success" : "danger"}>
                {job.status === "succeeded" ? "성공" : "실패"}
              </Badge>
            </div>

            {job.error && (
              <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {job.error}
              </div>
            )}

            {/* Summary */}
            {job.metrics && (
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-[#E5E8EB] bg-white px-4 py-3">
                  <div className="text-xs font-medium text-[#8B95A1]">전체</div>
                  <div className="mt-1 text-lg font-bold text-[#191F28]">{job.metrics.total ?? 0}건</div>
                </div>
                <div className="rounded-xl border border-[#E5E8EB] bg-white px-4 py-3">
                  <div className="text-xs font-medium text-[#8B95A1]">성공</div>
                  <div className="mt-1 text-lg font-bold text-emerald-600">
                    {job.metrics.success_count ?? 0}건
                  </div>
                </div>
                <div className="rounded-xl border border-[#E5E8EB] bg-white px-4 py-3">
                  <div className="text-xs font-medium text-[#8B95A1]">실패</div>
                  <div className="mt-1 text-lg font-bold text-rose-600">{job.metrics.failed_count ?? 0}건</div>
                </div>
              </div>
            )}

            {/* Per-file results */}
            {job.metrics?.results_summary && (
              <div className="mt-4 space-y-2">
                <div className="text-xs font-medium text-[#8B95A1]">문서별 결과</div>
                {job.metrics.results_summary.map((r) => (
                  <div
                    key={r.file_id}
                    className="flex items-center justify-between gap-2 rounded-xl border border-[#E5E8EB] bg-white px-3 py-2"
                  >
                    <div className="flex items-center gap-2">
                      {r.success ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                      ) : (
                        <XCircle className="h-4 w-4 text-rose-500" />
                      )}
                      <span className="text-sm text-[#191F28]">{r.filename}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge tone="neutral">{DOC_TYPE_LABELS[r.doc_type] ?? r.doc_type}</Badge>
                      <span className="text-xs text-[#8B95A1]">
                        {r.method === "rule" ? "규칙" : r.method === "vlm" ? "VLM" : "실패"}
                      </span>
                      <span className="font-mono text-xs text-[#8B95A1]">
                        {(r.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Artifacts */}
          <Card variant="strong" className="p-6">
            <div className="text-sm font-semibold text-[#191F28]">다운로드</div>
            <div className="mt-3 space-y-2">
              {(job.artifacts ?? []).length === 0 ? (
                <div className="text-sm text-[#8B95A1]">아티팩트가 없습니다.</div>
              ) : (
                (job.artifacts ?? []).map((a) => (
                  <div
                    key={a.artifactId}
                    className="flex items-center justify-between gap-2 rounded-xl border border-[#E5E8EB] bg-white px-3 py-2"
                  >
                    <div>
                      <div className="text-sm font-medium text-[#191F28]">{a.label}</div>
                      <div className="mt-0.5 font-mono text-xs text-[#8B95A1]">{a.contentType}</div>
                    </div>
                    <Button variant="secondary" onClick={() => downloadArtifact(a)}>
                      <Download className="h-4 w-4" />
                      다운로드
                    </Button>
                  </div>
                ))
              )}
            </div>
          </Card>

          <div className="flex justify-end">
            <Button variant="primary" onClick={reset}>
              새로운 추출
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
