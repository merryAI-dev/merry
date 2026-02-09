"use client";

import * as React from "react";
import { Download, Loader2, Play, RefreshCw, UploadCloud } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";

type JobType = "exit_projection" | "diagnosis_analysis" | "pdf_evidence" | "pdf_parse" | "contract_review";
type JobStatus = "queued" | "running" | "succeeded" | "failed";

type JobArtifact = {
  artifactId: string;
  label: string;
  contentType: string;
  s3Bucket: string;
  s3Key: string;
  sizeBytes?: number;
};

type JobRecord = {
  jobId: string;
  type: JobType;
  status: JobStatus;
  title: string;
  createdBy: string;
  createdAt: string;
  updatedAt?: string;
  inputFileIds: string[];
  params?: Record<string, unknown>;
  error?: string;
  artifacts?: JobArtifact[];
  metrics?: Record<string, unknown>;
  usage?: Record<string, unknown>;
};

type CostEstimate =
  | { ok: true; samples: number; avgUsd?: number; estimateUsd?: number; note?: string }
  | { ok: false; error: string };

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.error || "FAILED");
  return json as T;
}

function badgeForStatus(status: JobStatus) {
  if (status === "succeeded") return <Badge tone="success">완료</Badge>;
  if (status === "failed") return <Badge tone="danger">실패</Badge>;
  if (status === "running") return <Badge tone="accent">진행 중</Badge>;
  return <Badge tone="neutral">대기</Badge>;
}

function labelForType(type: JobType) {
  if (type === "exit_projection") return "Exit 프로젝션";
  if (type === "diagnosis_analysis") return "기업진단";
  if (type === "pdf_parse") return "PDF 파싱";
  if (type === "pdf_evidence") return "PDF 근거";
  return "계약서";
}

export default function AnalysisPage() {
  const [jobs, setJobs] = React.useState<JobRecord[]>([]);
  const [activeJobId, setActiveJobId] = React.useState<string>("");

  const [jobType, setJobType] = React.useState<JobType>("pdf_evidence");
  const [file1, setFile1] = React.useState<File | null>(null);
  const [file2, setFile2] = React.useState<File | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const file1Ref = React.useRef<HTMLInputElement | null>(null);
  const file2Ref = React.useRef<HTMLInputElement | null>(null);

  const [exitTargetYear, setExitTargetYear] = React.useState("2030");
  const [exitPer, setExitPer] = React.useState("10,20,30");
  const [parseMaxPages, setParseMaxPages] = React.useState("30");
  const [parseOutputMode, setParseOutputMode] = React.useState("structured");
  const [evidenceMaxPages, setEvidenceMaxPages] = React.useState("30");
  const [evidenceMaxResults, setEvidenceMaxResults] = React.useState("20");
  const [cost, setCost] = React.useState<CostEstimate | null>(null);

  const activeJob = jobs.find((j) => j.jobId === activeJobId) ?? null;

  const loadJobs = React.useCallback(async () => {
    setError(null);
    try {
      const res = await fetchJson<{ jobs: JobRecord[] }>("/api/jobs");
      setJobs(res.jobs || []);
      if (!activeJobId && (res.jobs?.[0]?.jobId ?? "")) setActiveJobId(res.jobs[0].jobId);
    } catch {
      setError("잡 목록을 불러오지 못했습니다. AWS 환경변수를 확인하세요.");
    }
  }, [activeJobId]);

  React.useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  const loadCost = React.useCallback(async () => {
    try {
      const res = await fetchJson<CostEstimate>(`/api/cost/estimate?n=200&type=${jobType}`);
      setCost(res);
    } catch {
      // Non-fatal.
      setCost(null);
    }
  }, [jobType]);

  React.useEffect(() => {
    loadCost();
  }, [loadCost]);

  React.useEffect(() => {
    // Keep state sane when switching job types.
    setError(null);
    setFile1(null);
    if (file1Ref.current) file1Ref.current.value = "";
    if (jobType !== "contract_review") {
      setFile2(null);
      if (file2Ref.current) file2Ref.current.value = "";
    }
  }, [jobType]);

  // Auto-refresh while any job is in-flight.
  React.useEffect(() => {
    const inflight = jobs.some((j) => j.status === "queued" || j.status === "running");
    if (!inflight) return;
    const t = setInterval(() => loadJobs(), 5000);
    return () => clearInterval(t);
  }, [jobs, loadJobs]);

  function buildParams(): Record<string, unknown> {
    if (jobType === "exit_projection") {
      const year = Number(exitTargetYear);
      const per = exitPer
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map((s) => Number(s))
        .filter((n) => Number.isFinite(n) && n > 0);
      return { targetYear: Number.isFinite(year) ? year : 2030, perMultiples: per.length ? per : [10, 20, 30] };
    }
    if (jobType === "pdf_evidence") {
      const maxPages = Number(evidenceMaxPages);
      const maxResults = Number(evidenceMaxResults);
      return {
        maxPages: Number.isFinite(maxPages) ? maxPages : 30,
        maxResults: Number.isFinite(maxResults) ? maxResults : 20,
      };
    }
    if (jobType === "pdf_parse") {
      const maxPages = Number(parseMaxPages);
      const mode = (parseOutputMode || "structured").trim();
      const outputMode = mode === "text_only" || mode === "tables_only" ? mode : "structured";
      return {
        maxPages: Number.isFinite(maxPages) ? maxPages : 30,
        outputMode,
      };
    }
    return {};
  }

  function acceptForJob(type: JobType): string {
    if (type === "exit_projection" || type === "diagnosis_analysis") return ".xlsx,.xls";
    if (type === "pdf_evidence" || type === "pdf_parse") return ".pdf";
    return ".pdf,.docx";
  }

  async function uploadAndRun() {
    if (!file1) return;
    setBusy(true);
    setError(null);
    try {
      const files: File[] = [];
      files.push(file1);
      if (jobType === "contract_review" && file2) files.push(file2);

      async function uploadOne(f: File): Promise<string> {
        const presign = await fetchJson<{
          file: { fileId: string; contentType: string };
          upload: { url: string; headers: Record<string, string> };
        }>("/api/uploads/presign", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            filename: f.name,
            contentType: f.type || "application/octet-stream",
            sizeBytes: f.size,
          }),
        });

        const putRes = await fetch(presign.upload.url, {
          method: "PUT",
          headers: presign.upload.headers,
          body: f,
        });
        if (!putRes.ok) throw new Error("UPLOAD_FAILED");

        await fetchJson("/api/uploads/complete", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ fileId: presign.file.fileId }),
        });
        return presign.file.fileId;
      }

      const fileIds: string[] = [];
      for (const f of files) fileIds.push(await uploadOne(f));

      const started = await fetchJson<{ jobId: string }>("/api/jobs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          jobType,
          fileIds,
          params: buildParams(),
        }),
      });

      await loadJobs();
      setActiveJobId(started.jobId);
      setFile1(null);
      setFile2(null);
      if (file1Ref.current) file1Ref.current.value = "";
      if (file2Ref.current) file2Ref.current.value = "";
    } catch (e) {
      const msg = e instanceof Error ? e.message : "FAILED";
      if (msg === "UPLOAD_FAILED") setError("업로드에 실패했습니다. S3 CORS/권한을 확인하세요.");
      else setError("업로드/잡 생성에 실패했습니다. AWS 설정을 확인하세요.");
    } finally {
      setBusy(false);
    }
  }

  async function downloadArtifact(job: JobRecord, artifact: JobArtifact) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetchJson<{ url: string }>(`/api/jobs/${job.jobId}/artifact?artifactId=${artifact.artifactId}`);
      window.open(res.url, "_blank", "noopener,noreferrer");
    } catch {
      setError("다운로드 URL 발급에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-[color:var(--muted)]">Secure Analysis</div>
          <h1 className="mt-1 font-[family-name:var(--font-display)] text-3xl tracking-tight text-[color:var(--ink)]">
            문서 업로드 & 분석 잡
          </h1>
          <div className="mt-2 text-sm text-[color:var(--muted)]">
            업로드는 S3 프리사인 URL로 브라우저에서 직접 전송되고, 분석은 Python 워커 잡으로 처리됩니다.
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={loadJobs} disabled={busy}>
            <RefreshCw className="h-4 w-4" />
            새로고침
          </Button>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-900">
          {error}
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <Card variant="strong" className="p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-[color:var(--ink)]">새 분석</div>
              <div className="mt-1 text-sm text-[color:var(--muted)]">
                파일 1개 업로드 후, 잡을 생성합니다. (원본 삭제/아티팩트 보관 정책은 워커에서 관리)
              </div>
            </div>
            <Badge tone="neutral">Vercel-safe</Badge>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1">
              <span className="text-xs font-medium text-[color:var(--muted)]">잡 타입</span>
              <select
                className="h-11 rounded-xl border border-[color:var(--line)] bg-white/80 px-3 text-sm text-[color:var(--ink)] outline-none focus:border-[color:var(--accent)]"
                value={jobType}
                onChange={(e) => setJobType(e.target.value as JobType)}
                disabled={busy}
              >
                <option value="pdf_parse">PDF 파싱(구조화)</option>
                <option value="pdf_evidence">PDF 근거 추출</option>
                <option value="exit_projection">Exit 프로젝션(엑셀)</option>
                <option value="diagnosis_analysis">기업진단 분석(엑셀)</option>
                <option value="contract_review">계약서 검토(PDF/DOCX)</option>
              </select>
            </label>

            {jobType === "contract_review" ? (
              <>
                <label className="grid gap-1">
                  <span className="text-xs font-medium text-[color:var(--muted)]">텀싯 (필수)</span>
                  <input
                    ref={file1Ref}
                    id="analysis-file-1"
                    type="file"
                    accept={acceptForJob(jobType)}
                    className="h-11 rounded-xl border border-[color:var(--line)] bg-white/80 px-3 text-sm"
                    onChange={(e) => setFile1(e.target.files?.[0] ?? null)}
                    disabled={busy}
                  />
                </label>
                <label className="grid gap-1">
                  <span className="text-xs font-medium text-[color:var(--muted)]">투자계약서 (선택)</span>
                  <input
                    ref={file2Ref}
                    id="analysis-file-2"
                    type="file"
                    accept={acceptForJob(jobType)}
                    className="h-11 rounded-xl border border-[color:var(--line)] bg-white/80 px-3 text-sm"
                    onChange={(e) => setFile2(e.target.files?.[0] ?? null)}
                    disabled={busy}
                  />
                </label>
              </>
            ) : (
              <label className="grid gap-1">
                <span className="text-xs font-medium text-[color:var(--muted)]">파일</span>
                <input
                  ref={file1Ref}
                  id="analysis-file-1"
                  type="file"
                  accept={acceptForJob(jobType)}
                  className="h-11 rounded-xl border border-[color:var(--line)] bg-white/80 px-3 text-sm"
                  onChange={(e) => setFile1(e.target.files?.[0] ?? null)}
                  disabled={busy}
                />
              </label>
            )}
          </div>

          {jobType === "exit_projection" ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1">
                <span className="text-xs font-medium text-[color:var(--muted)]">Target year</span>
                <Input
                  value={exitTargetYear}
                  onChange={(e) => setExitTargetYear(e.target.value)}
                  disabled={busy}
                />
              </label>
              <label className="grid gap-1">
                <span className="text-xs font-medium text-[color:var(--muted)]">PER multiples</span>
                <Input
                  value={exitPer}
                  onChange={(e) => setExitPer(e.target.value)}
                  disabled={busy}
                />
              </label>
            </div>
          ) : null}

          {jobType === "pdf_evidence" ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1">
                <span className="text-xs font-medium text-[color:var(--muted)]">Max pages</span>
                <Input
                  value={evidenceMaxPages}
                  onChange={(e) => setEvidenceMaxPages(e.target.value)}
                  disabled={busy}
                />
              </label>
              <label className="grid gap-1">
                <span className="text-xs font-medium text-[color:var(--muted)]">Max results</span>
                <Input
                  value={evidenceMaxResults}
                  onChange={(e) => setEvidenceMaxResults(e.target.value)}
                  disabled={busy}
                />
              </label>
            </div>
          ) : null}

          {jobType === "pdf_parse" ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1">
                <span className="text-xs font-medium text-[color:var(--muted)]">Max pages</span>
                <Input
                  value={parseMaxPages}
                  onChange={(e) => setParseMaxPages(e.target.value)}
                  disabled={busy}
                />
              </label>
              <label className="grid gap-1">
                <span className="text-xs font-medium text-[color:var(--muted)]">Output mode</span>
                <select
                  className="h-11 rounded-xl border border-[color:var(--line)] bg-white/80 px-3 text-sm text-[color:var(--ink)] outline-none focus:border-[color:var(--accent)]"
                  value={parseOutputMode}
                  onChange={(e) => setParseOutputMode(e.target.value)}
                  disabled={busy}
                >
                  <option value="structured">structured</option>
                  <option value="text_only">text_only</option>
                  <option value="tables_only">tables_only</option>
                </select>
              </label>
            </div>
          ) : null}

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs text-[color:var(--muted)]">
              S3 버킷: <span className="font-mono">MERRY_S3_BUCKET</span> · DDB: <span className="font-mono">MERRY_DDB_TABLE</span>
            </div>
            <Button variant="primary" onClick={uploadAndRun} disabled={busy || !file1}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
              업로드 & 실행
            </Button>
          </div>
        </Card>

        <Card variant="strong" className="p-5">
          <div className="text-sm font-semibold text-[color:var(--ink)]">최근 잡</div>
          <div className="mt-3 space-y-2">
            {jobs.length === 0 ? (
              <div className="text-sm text-[color:var(--muted)]">아직 생성된 잡이 없습니다.</div>
            ) : (
              jobs.map((job) => {
                const active = job.jobId === activeJobId;
                return (
                  <button
                    key={job.jobId}
                    onClick={() => setActiveJobId(job.jobId)}
                    className={cn(
                      "w-full rounded-2xl border px-3 py-2 text-left transition-colors",
                      active
                        ? "border-[color:var(--accent)] bg-[color:color-mix(in_oklab,var(--accent),white_92%)]"
                        : "border-[color:var(--line)] bg-white/70 hover:bg-white",
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-medium text-[color:var(--ink)]">{job.title}</div>
                      {badgeForStatus(job.status)}
                    </div>
                    <div className="mt-1 flex items-center justify-between gap-2 text-xs text-[color:var(--muted)]">
                      <div>{labelForType(job.type)}</div>
                      <div className="font-mono">{job.jobId}</div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </Card>
      </div>

      <Card variant="strong" className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-[color:var(--ink)]">비용 외삽 (200건)</div>
            <div className="mt-1 text-sm text-[color:var(--muted)]">
              최근 성공 잡의 토큰 사용량(usage)을 기반으로 평균 비용을 계산합니다. 단가는 환경변수로 오버라이드 가능합니다.
            </div>
          </div>
          <Badge tone="neutral">MVP</Badge>
        </div>

        <div className="mt-4 rounded-2xl border border-[color:var(--line)] bg-white/70 p-4 text-sm">
          {!cost ? (
            <div className="text-[color:var(--muted)]">계산 정보를 불러오지 못했습니다.</div>
          ) : cost.ok && cost.samples === 0 ? (
            <div className="text-[color:var(--muted)]">{cost.note ?? "아직 샘플이 없습니다."}</div>
          ) : cost.ok ? (
            <div className="grid gap-2 sm:grid-cols-3">
              <div>
                <div className="text-xs font-medium text-[color:var(--muted)]">샘플 수</div>
                <div className="mt-1 font-mono text-[color:var(--ink)]">{cost.samples}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-[color:var(--muted)]">평균 비용(USD)</div>
                <div className="mt-1 font-mono text-[color:var(--ink)]">{(cost.avgUsd ?? 0).toFixed(4)}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-[color:var(--muted)]">200건 추정(USD)</div>
                <div className="mt-1 font-mono text-[color:var(--ink)]">{(cost.estimateUsd ?? 0).toFixed(2)}</div>
              </div>
            </div>
          ) : (
            <div className="text-rose-900">실패: {cost.error}</div>
          )}
        </div>
      </Card>

      <Card variant="strong" className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-[color:var(--ink)]">잡 상세</div>
            <div className="mt-1 text-sm text-[color:var(--muted)]">
              결과 파일은 S3 아티팩트로 저장되고, 다운로드는 프리사인 URL로 제공됩니다.
            </div>
          </div>
          {activeJob ? badgeForStatus(activeJob.status) : <Badge tone="neutral">선택 없음</Badge>}
        </div>

        {!activeJob ? (
          <div className="mt-4 text-sm text-[color:var(--muted)]">오른쪽에서 잡을 선택하세요.</div>
        ) : (
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-4">
              <div className="text-xs font-medium text-[color:var(--muted)]">메타</div>
              <div className="mt-2 grid gap-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[color:var(--muted)]">Type</span>
                  <span className="font-medium text-[color:var(--ink)]">{labelForType(activeJob.type)}</span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[color:var(--muted)]">Created</span>
                  <span className="font-mono text-xs text-[color:var(--ink)]">{activeJob.createdAt}</span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[color:var(--muted)]">Inputs</span>
                  <span className="font-mono text-xs text-[color:var(--ink)]">{activeJob.inputFileIds.join(", ")}</span>
                </div>
              </div>
              {activeJob.error ? (
                <div className="mt-3 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-900">
                  {activeJob.error}
                </div>
              ) : null}
            </div>

            <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-4">
              <div className="text-xs font-medium text-[color:var(--muted)]">아티팩트</div>
              <div className="mt-3 space-y-2">
                {(activeJob.artifacts ?? []).length === 0 ? (
                  <div className="text-sm text-[color:var(--muted)]">아직 결과가 없습니다.</div>
                ) : (
                  (activeJob.artifacts ?? []).map((a) => (
                    <div key={a.artifactId} className="flex items-center justify-between gap-2 rounded-xl border border-[color:var(--line)] bg-white/80 px-3 py-2">
                      <div>
                        <div className="text-sm font-medium text-[color:var(--ink)]">{a.label}</div>
                        <div className="mt-0.5 font-mono text-xs text-[color:var(--muted)]">{a.artifactId}</div>
                      </div>
                      <Button variant="secondary" onClick={() => downloadArtifact(activeJob, a)} disabled={busy}>
                        <Download className="h-4 w-4" />
                        다운로드
                      </Button>
                    </div>
                  ))
                )}
              </div>

              {activeJob.status === "queued" ? (
                <div className="mt-3 flex items-center gap-2 text-xs text-[color:var(--muted)]">
                  <Play className="h-4 w-4" />
                  워커가 SQS에서 잡을 가져가면 진행으로 바뀝니다.
                </div>
              ) : null}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
