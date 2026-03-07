"use client";

import * as React from "react";
import {
  CheckCircle2,
  Download,
  FileSpreadsheet,
  FileText,
  Loader2,
  UploadCloud,
  XCircle,
  Zap,
} from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { apiFetch } from "@/lib/apiClient";

/* ── Types ── */

type JobStatus = "queued" | "running" | "succeeded" | "failed";
type JobArtifact = {
  artifactId: string;
  label: string;
  contentType: string;
  s3Bucket: string;
  s3Key: string;
  sizeBytes?: number;
};
type CompanyResult = {
  company_name: string;
  file_count: number;
  has_financials: boolean;
  has_cap_table: boolean;
};
type JobRecord = {
  jobId: string;
  status: JobStatus;
  title: string;
  createdAt: string;
  error?: string;
  artifacts?: JobArtifact[];
  metrics?: {
    success_count?: number;
    failed_count?: number;
    total?: number;
    companies?: CompanyResult[];
  };
};

type Stage = "upload" | "processing" | "results";

/* ── Chunk config (flash-attention analogy: process in parallel windows) ── */
const CHUNK_SIZE = 10; // files per SQS batch window
const MAX_FILES = 200;

/* ── Component ── */

export default function ExtractPage() {
  const [stage, setStage] = React.useState<Stage>("upload");
  const [files, setFiles] = React.useState<File[]>([]);
  const [jobId, setJobId] = React.useState<string>("");
  const [job, setJob] = React.useState<JobRecord | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = React.useState(0);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  /* ── Upload ── */

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files ?? []).filter((f) =>
      f.name.toLowerCase().endsWith(".pdf"),
    );
    if (selected.length === 0) return;
    setFiles((prev) => [...prev, ...selected].slice(0, MAX_FILES));
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files).filter((f) =>
      f.name.toLowerCase().endsWith(".pdf"),
    );
    if (dropped.length === 0) return;
    setFiles((prev) => [...prev, ...dropped].slice(0, MAX_FILES));
  }

  function removeFile(idx: number) {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  async function uploadAndProcess() {
    if (files.length === 0) return;
    setBusy(true);
    setError(null);
    setUploadProgress(0);

    try {
      // Upload files in chunks of CHUNK_SIZE (parallel within each chunk)
      const fileIds: string[] = [];
      const chunks: File[][] = [];
      for (let i = 0; i < files.length; i += CHUNK_SIZE) {
        chunks.push(files.slice(i, i + CHUNK_SIZE));
      }

      for (let ci = 0; ci < chunks.length; ci++) {
        const chunk = chunks[ci];
        const chunkIds = await Promise.all(
          chunk.map(async (f) => {
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

            return presign.file.fileId;
          }),
        );
        fileIds.push(...chunkIds);
        setUploadProgress(Math.round(((ci + 1) / chunks.length) * 100));
      }

      // Create fan-out job
      const res = await apiFetch<{ jobId: string }>("/api/jobs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          jobType: "financial_extraction",
          fileIds,
          params: { consolidate: true, output_format: "xlsx" },
        }),
      });

      setJobId(res.jobId);
      setStage("processing");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "FAILED";
      if (msg === "UPLOAD_FAILED") setError("S3 upload failed — check CORS/permissions.");
      else setError("Upload or job creation failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  /* ── Polling ── */

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
    const t = setInterval(pollJob, 4000);
    return () => clearInterval(t);
  }, [stage, pollJob]);

  /* ── Download ── */

  async function downloadArtifact(artifact: JobArtifact) {
    try {
      const res = await apiFetch<{ url: string }>(
        `/api/jobs/${jobId}/artifact?artifactId=${artifact.artifactId}`,
      );
      window.open(res.url, "_blank", "noopener,noreferrer");
    } catch {
      setError("Failed to generate download URL.");
    }
  }

  function reset() {
    setStage("upload");
    setFiles([]);
    setJobId("");
    setJob(null);
    setError(null);
    setUploadProgress(0);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  /* ── Stats derived from job ── */
  const totalFiles = job?.metrics?.total ?? files.length;
  const successCount = job?.metrics?.success_count ?? 0;
  const failedCount = job?.metrics?.failed_count ?? 0;
  const companies = job?.metrics?.companies ?? [];

  /* ── Progress bar for processing ── */
  const processingPct =
    totalFiles > 0 ? Math.round(((successCount + failedCount) / totalFiles) * 100) : 0;

  /* ── Render ── */

  const stageLabels: Record<Stage, string> = {
    upload: "1. Upload",
    processing: "2. Processing",
    results: "3. Results",
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-sm font-medium text-[#8B95A1]">
          <Zap className="h-4 w-4 text-[#3182F6]" />
          Financial Data Extraction
        </div>
        <h1 className="mt-1 font-black tracking-tight text-2xl text-[#191F28]">
          Batch Extract
        </h1>
        <p className="mt-2 text-sm text-[#8B95A1]">
          Upload PDF documents from multiple companies. Files are processed in parallel chunks
          and accumulated per company into a single consolidated Excel file.
        </p>
      </div>

      {/* Stage Indicator */}
      <div className="flex items-center gap-2">
        {(["upload", "processing", "results"] as Stage[]).map((s, i) => (
          <React.Fragment key={s}>
            {i > 0 && <div className="h-px w-6 bg-[#E5E8EB]" />}
            <Badge tone={stage === s ? "accent" : "neutral"}>{stageLabels[s]}</Badge>
          </React.Fragment>
        ))}
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {/* Stage 1: Upload */}
      {stage === "upload" && (
        <Card variant="strong" className="p-6">
          {/* Drop zone */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className="flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-[#E5E8EB] bg-white px-6 py-12 transition-colors hover:border-[#3182F6]"
          >
            <UploadCloud className="h-10 w-10 text-[#8B95A1]" />
            <div className="text-center">
              <div className="text-sm font-medium text-[#4E5968]">
                Drop PDF files here or click to browse
              </div>
              <div className="mt-1 text-xs text-[#8B95A1]">
                Up to {MAX_FILES} files · Processed in parallel chunks of {CHUNK_SIZE}
              </div>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              multiple
              className="hidden"
              onChange={handleFileSelect}
            />
            <Button variant="secondary" onClick={() => fileInputRef.current?.click()}>
              Browse files
            </Button>
          </div>

          {/* File list */}
          {files.length > 0 && (
            <div className="mt-4">
              <div className="mb-2 flex items-center justify-between">
                <div className="text-sm font-medium text-[#191F28]">
                  {files.length} file{files.length > 1 ? "s" : ""} selected
                </div>
                <button
                  onClick={() => setFiles([])}
                  className="text-xs text-[#8B95A1] hover:text-rose-500"
                >
                  Clear all
                </button>
              </div>
              <div className="max-h-60 space-y-1.5 overflow-y-auto">
                {files.map((f, i) => (
                  <div
                    key={`${f.name}-${i}`}
                    className="flex items-center justify-between rounded-xl border border-[#E5E8EB] bg-white px-3 py-2"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <FileText className="h-4 w-4 shrink-0 text-[#8B95A1]" />
                      <span className="truncate text-sm text-[#191F28]">{f.name}</span>
                      <span className="shrink-0 text-xs text-[#8B95A1]">
                        ({(f.size / 1024).toFixed(0)} KB)
                      </span>
                    </div>
                    <button
                      onClick={() => removeFile(i)}
                      className="ml-2 shrink-0 text-xs text-rose-500 hover:text-rose-700"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Upload progress */}
          {busy && uploadProgress > 0 && (
            <div className="mt-4">
              <div className="mb-1 flex items-center justify-between text-xs text-[#8B95A1]">
                <span>Uploading chunks…</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#E5E8EB]">
                <div
                  className="h-full rounded-full bg-[#3182F6] transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          <div className="mt-5 flex justify-end">
            <Button
              variant="primary"
              onClick={uploadAndProcess}
              disabled={busy || files.length === 0}
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Zap className="h-4 w-4" />
              )}
              {busy ? "Uploading…" : `Start Extraction (${files.length} files)`}
            </Button>
          </div>
        </Card>
      )}

      {/* Stage 2: Processing */}
      {stage === "processing" && (
        <Card variant="strong" className="p-6 space-y-5">
          <div className="flex items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-[#3182F6]" />
            <div>
              <div className="text-sm font-semibold text-[#191F28]">Processing files…</div>
              <div className="mt-0.5 text-xs text-[#8B95A1] font-mono">{jobId}</div>
            </div>
          </div>

          {/* Progress bar */}
          <div>
            <div className="mb-1.5 flex items-center justify-between text-xs text-[#8B95A1]">
              <span>
                {successCount + failedCount} / {totalFiles} processed
              </span>
              <span>{processingPct}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-[#E5E8EB]">
              <div
                className="h-full rounded-full bg-[#3182F6] transition-all duration-500"
                style={{ width: `${processingPct}%` }}
              />
            </div>
          </div>

          {/* Live company accumulation */}
          {companies.length > 0 && (
            <div>
              <div className="mb-2 text-xs font-medium text-[#8B95A1] uppercase tracking-wide">
                Companies accumulated
              </div>
              <div className="space-y-1.5">
                {companies.map((c) => (
                  <div
                    key={c.company_name}
                    className="flex items-center justify-between rounded-xl border border-[#E5E8EB] bg-white px-3 py-2"
                  >
                    <span className="text-sm font-medium text-[#191F28]">
                      {c.company_name}
                    </span>
                    <div className="flex items-center gap-2">
                      {c.has_financials && (
                        <Badge tone="success">Financials</Badge>
                      )}
                      {c.has_cap_table && (
                        <Badge tone="accent">Cap Table</Badge>
                      )}
                      <span className="text-xs text-[#8B95A1]">
                        {c.file_count} file{c.file_count > 1 ? "s" : ""}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="text-xs text-[#8B95A1]">
            Files are processed in parallel windows of {CHUNK_SIZE} · polling every 4 s
          </div>
        </Card>
      )}

      {/* Stage 3: Results */}
      {stage === "results" && job && (
        <div className="space-y-4">
          <Card variant="strong" className="p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-[#191F28]">Extraction complete</div>
                <div className="mt-0.5 text-xs text-[#8B95A1] font-mono">{jobId}</div>
              </div>
              <Badge tone={job.status === "succeeded" ? "success" : "danger"}>
                {job.status === "succeeded" ? "Succeeded" : "Failed"}
              </Badge>
            </div>

            {job.error && (
              <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {job.error}
              </div>
            )}

            {/* Summary stats */}
            {job.metrics && (
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {[
                  { label: "Total", value: job.metrics.total ?? 0, color: "text-[#191F28]" },
                  { label: "Success", value: job.metrics.success_count ?? 0, color: "text-emerald-600" },
                  { label: "Failed", value: job.metrics.failed_count ?? 0, color: "text-rose-600" },
                ].map(({ label, value, color }) => (
                  <div
                    key={label}
                    className="rounded-xl border border-[#E5E8EB] bg-white px-4 py-3"
                  >
                    <div className="text-xs font-medium text-[#8B95A1]">{label}</div>
                    <div className={cn("mt-1 text-lg font-bold", color)}>{value}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Per-company results */}
            {companies.length > 0 && (
              <div className="mt-4">
                <div className="mb-2 text-xs font-medium text-[#8B95A1] uppercase tracking-wide">
                  {companies.length} compan{companies.length > 1 ? "ies" : "y"} extracted
                </div>
                <div className="space-y-1.5">
                  {companies.map((c) => (
                    <div
                      key={c.company_name}
                      className="flex items-center justify-between rounded-xl border border-[#E5E8EB] bg-white px-3 py-2"
                    >
                      <div className="flex items-center gap-2">
                        {c.has_financials ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                        ) : (
                          <XCircle className="h-4 w-4 text-[#D1D6DC]" />
                        )}
                        <span className="text-sm text-[#191F28]">{c.company_name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {c.has_financials && <Badge tone="success">IS/BS</Badge>}
                        {c.has_cap_table && <Badge tone="accent">Cap Table</Badge>}
                        <span className="text-xs text-[#8B95A1]">
                          {c.file_count} file{c.file_count > 1 ? "s" : ""}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>

          {/* Artifacts — consolidated Excel download */}
          <Card variant="strong" className="p-6">
            <div className="flex items-center gap-2 text-sm font-semibold text-[#191F28]">
              <FileSpreadsheet className="h-4 w-4 text-emerald-600" />
              Download
            </div>
            <div className="mt-3 space-y-2">
              {(job.artifacts ?? []).length === 0 ? (
                <div className="text-sm text-[#8B95A1]">No artifacts available.</div>
              ) : (
                (job.artifacts ?? []).map((a) => (
                  <div
                    key={a.artifactId}
                    className="flex items-center justify-between gap-2 rounded-xl border border-[#E5E8EB] bg-white px-4 py-3"
                  >
                    <div>
                      <div className="text-sm font-medium text-[#191F28]">{a.label}</div>
                      <div className="mt-0.5 font-mono text-xs text-[#8B95A1]">
                        {a.contentType}
                        {a.sizeBytes != null && (
                          <span className="ml-2">
                            {(a.sizeBytes / 1024).toFixed(0)} KB
                          </span>
                        )}
                      </div>
                    </div>
                    <Button variant="primary" size="sm" onClick={() => downloadArtifact(a)}>
                      <Download className="h-4 w-4" />
                      Download
                    </Button>
                  </div>
                ))
              )}
            </div>
          </Card>

          <div className="flex justify-end">
            <Button variant="secondary" onClick={reset}>
              New extraction
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
