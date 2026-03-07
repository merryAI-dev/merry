"use client";

import Link from "next/link";
import * as React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Download, FileSpreadsheet, Play, RefreshCw, UploadCloud } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { apiFetch } from "@/lib/apiClient";

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
  type: string;
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
};

type ExitAssumptions = {
  company_name?: string;
  target_year?: number;
  investment_year?: number;
  holding_period_years?: number;
  investment_amount?: number;
  shares?: number;
  total_shares?: number;
  net_income?: number;
  per_multiples?: number[];
};

type ExitScenario = {
  per: number;
  irr?: number;
  multiple?: number;
};


function fmtCompact(n?: number) {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("ko-KR", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

function fmtIrr(n?: number) {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return `${n.toFixed(1)}%`;
}

function fmtMultiple(n?: number) {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return `${n.toFixed(2)}x`;
}

function statusBadge(status: JobStatus) {
  if (status === "succeeded") return <Badge tone="success">완료</Badge>;
  if (status === "failed") return <Badge tone="danger">실패</Badge>;
  if (status === "running") return <Badge tone="accent">진행 중</Badge>;
  return <Badge tone="neutral">대기</Badge>;
}

function irrTone(irr?: number): "success" | "warn" | "danger" | "neutral" {
  if (typeof irr !== "number" || !Number.isFinite(irr)) return "neutral";
  if (irr >= 30) return "success";
  if (irr >= 15) return "warn";
  return "danger";
}

function irrColor(irr?: number): string {
  const tone = irrTone(irr);
  if (tone === "success") return "rgba(16,185,129,0.85)";
  if (tone === "warn") return "rgba(245,158,11,0.85)";
  if (tone === "danger") return "rgba(244,63,94,0.85)";
  return "rgba(100,116,139,0.5)";
}

function parseExit(job: JobRecord | null): { assumptions: ExitAssumptions; scenarios: ExitScenario[] } | null {
  if (!job?.metrics || typeof job.metrics !== "object") return null;
  const metrics = job.metrics as Record<string, unknown>;
  const assumptions = (metrics["assumptions"] && typeof metrics["assumptions"] === "object"
    ? (metrics["assumptions"] as Record<string, unknown>)
    : {}) as Record<string, unknown>;
  const projection = Array.isArray(metrics["projection_summary"]) ? (metrics["projection_summary"] as unknown[]) : [];

  const scenarios: ExitScenario[] = projection
    .map((row) => (row && typeof row === "object" ? (row as Record<string, unknown>) : {}))
    .map((row) => {
      const per = typeof row["PER"] === "number" ? row["PER"] : Number(row["PER"]);
      const irr = typeof row["IRR"] === "number" ? row["IRR"] : Number(row["IRR"]);
      const multiple = typeof row["Multiple"] === "number" ? row["Multiple"] : Number(row["Multiple"]);
      return {
        per: Number.isFinite(per) ? per : 0,
        irr: Number.isFinite(irr) ? irr : undefined,
        multiple: Number.isFinite(multiple) ? multiple : undefined,
      };
    })
    .filter((s) => Number.isFinite(s.per) && s.per > 0)
    .sort((a, b) => a.per - b.per);

  const outAssumptions: ExitAssumptions = {
    company_name: typeof assumptions["company_name"] === "string" ? assumptions["company_name"] : undefined,
    target_year: typeof assumptions["target_year"] === "number" ? assumptions["target_year"] : undefined,
    investment_year: typeof assumptions["investment_year"] === "number" ? assumptions["investment_year"] : undefined,
    holding_period_years: typeof assumptions["holding_period_years"] === "number" ? assumptions["holding_period_years"] : undefined,
    investment_amount: typeof assumptions["investment_amount"] === "number" ? assumptions["investment_amount"] : undefined,
    shares: typeof assumptions["shares"] === "number" ? assumptions["shares"] : undefined,
    total_shares: typeof assumptions["total_shares"] === "number" ? assumptions["total_shares"] : undefined,
    net_income: typeof assumptions["net_income"] === "number" ? assumptions["net_income"] : undefined,
    per_multiples: Array.isArray(assumptions["per_multiples"])
      ? (assumptions["per_multiples"] as unknown[])
          .map((n) => (typeof n === "number" ? n : Number(n)))
          .filter((n) => Number.isFinite(n) && n > 0)
      : undefined,
  };

  return { assumptions: outAssumptions, scenarios };
}

function normalizePerList(raw: string): number[] {
  const vals = raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => Number(s))
    .filter((n) => Number.isFinite(n) && n > 0)
    .slice(0, 12);
  if (vals.length) return Array.from(new Set(vals)).sort((a, b) => a - b);
  return [10, 20, 30];
}

function ExitTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload?: ExitScenario }> }) {
  if (!active || !payload?.length) return null;
  const p = payload[0]?.payload as ExitScenario | undefined;
  if (!p) return null;
  return (
    <div className="rounded-2xl border border-[#E5E8EB] bg-white px-3 py-2 shadow-sm">
      <div className="text-xs font-medium text-[#8B95A1]">PER {p.per}</div>
      <div className="mt-1 flex items-center justify-between gap-6 text-xs">
        <span className="text-[#8B95A1]">IRR</span>
        <span className="font-mono text-[#191F28]">{fmtIrr(p.irr)}</span>
      </div>
      <div className="mt-1 flex items-center justify-between gap-6 text-xs">
        <span className="text-[#8B95A1]">Multiple</span>
        <span className="font-mono text-[#191F28]">{fmtMultiple(p.multiple)}</span>
      </div>
    </div>
  );
}

const EMPTY_SCENARIOS: ExitScenario[] = [];

export default function ExitProjectionPage() {
  const [jobs, setJobs] = React.useState<JobRecord[]>([]);
  const [activeJobId, setActiveJobId] = React.useState<string>("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [file, setFile] = React.useState<File | null>(null);
  const fileRef = React.useRef<HTMLInputElement | null>(null);

  const [targetYear, setTargetYear] = React.useState("2030");
  const [perRaw, setPerRaw] = React.useState("10,20,30");

  const activeJob = jobs.find((j) => j.jobId === activeJobId) ?? null;
  const parsed = parseExit(activeJob);
  const scenarios = parsed?.scenarios ?? EMPTY_SCENARIOS;
  const assumptions = parsed?.assumptions ?? {};

  const loadJobs = React.useCallback(async () => {
    setError(null);
    try {
      const res = await apiFetch<{ jobs: JobRecord[] }>("/api/jobs");
      const list = (res.jobs || []).filter((j) => j.type === "exit_projection");
      setJobs(list);
      if (!activeJobId && list[0]?.jobId) setActiveJobId(list[0].jobId);
    } catch {
      setError("잡 목록을 불러오지 못했습니다. AWS 환경변수를 확인하세요.");
    }
  }, [activeJobId]);

  React.useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  React.useEffect(() => {
    const inflight = jobs.some((j) => j.status === "queued" || j.status === "running");
    if (!inflight) return;
    const t = setInterval(() => loadJobs(), 5000);
    return () => clearInterval(t);
  }, [jobs, loadJobs]);

  const best = React.useMemo(() => {
    const rows = scenarios.filter((s) => typeof s.irr === "number" && Number.isFinite(s.irr)) as Array<ExitScenario & { irr: number }>;
    if (!rows.length) return null;
    rows.sort((a, b) => b.irr - a.irr);
    return rows[0];
  }, [scenarios]);

  async function run() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const presign = await apiFetch<{
        ok: true;
        file: { fileId: string; contentType: string };
        upload: { url: string; headers: Record<string, string> };
      }>("/api/uploads/presign", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          filename: file.name,
          contentType: file.type || "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          sizeBytes: file.size,
        }),
      });

      const putRes = await fetch(presign.upload.url, { method: "PUT", headers: presign.upload.headers, body: file });
      if (!putRes.ok) throw new Error("UPLOAD_FAILED");

      await apiFetch("/api/uploads/complete", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ fileId: presign.file.fileId }),
      });

      const year = Number(targetYear);
      const perMultiples = normalizePerList(perRaw);
      const started = await apiFetch<{ ok: true; jobId: string }>("/api/jobs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          jobType: "exit_projection",
          fileIds: [presign.file.fileId],
          params: {
            targetYear: Number.isFinite(year) ? year : 2030,
            perMultiples,
          },
        }),
      });

      await loadJobs();
      setActiveJobId(started.jobId);
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
    } catch (e) {
      const msg = e instanceof Error ? e.message : "FAILED";
      if (msg === "UPLOAD_FAILED") setError("업로드에 실패했습니다. S3 CORS/권한을 확인하세요.");
      else setError("업로드/잡 생성에 실패했습니다. AWS 설정을 확인하세요.");
    } finally {
      setBusy(false);
    }
  }

  async function downloadXlsx(job: JobRecord) {
    const artifact = (job.artifacts || []).find((a) => a.artifactId === "exit_projection_xlsx");
    if (!artifact) {
      setError("다운로드 가능한 결과 파일을 찾지 못했습니다.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch<{ ok: true; url: string }>(`/api/jobs/${job.jobId}/artifact?artifactId=${artifact.artifactId}`);
      window.open(res.url, "_blank", "noopener,noreferrer");
    } catch {
      setError("다운로드 URL 발급에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  const perMultiples = normalizePerList(perRaw);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-[#8B95A1]">Exit Projection</div>
          <h1 className="mt-1 font-black tracking-tight text-2xl text-[#191F28]">
            Exit 프로젝션
          </h1>
          <div className="mt-2 text-sm text-[#8B95A1]">
            엑셀을 업로드하면 S3로 직접 전송되고, 계산은 워커 잡으로 처리됩니다. 원본 파일은 처리 후 삭제됩니다.
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={loadJobs} disabled={busy}>
            <RefreshCw className="h-4 w-4" />
            새로고침
          </Button>
          <Link href="/analysis" className="text-sm text-[#8B95A1] hover:text-[#191F28]">
            (고급) 전체 잡 러너 →
          </Link>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-5">
        <Card variant="strong" className="relative overflow-hidden rounded-3xl p-5 lg:col-span-3">
          <div className="absolute -right-20 -top-20 h-52 w-52 rounded-full bg-[color:color-mix(in_oklab,var(--accent-cyan),white_72%)] blur-2xl opacity-50" />
          <div className="absolute -left-24 -bottom-24 h-56 w-56 rounded-full bg-[color:color-mix(in_oklab,var(--accent-purple),white_78%)] blur-2xl opacity-40" />

          <div className="relative flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-[#191F28]">새 프로젝션 만들기</div>
              <div className="mt-1 text-xs text-[#8B95A1]">
                PER 시나리오별 IRR을 색상으로 표시합니다. (녹색 &gt; 30%, 노랑 15-30%, 빨강 &lt; 15%)
              </div>
            </div>
            <Badge tone="accent">Secure</Badge>
          </div>

          <div className="relative mt-4 grid gap-3 md:grid-cols-2">
            <div className="rounded-3xl border border-dashed border-[#E5E8EB] bg-white p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-[#191F28]">
                <UploadCloud className="h-4 w-4 text-[#3182F6]" />
                엑셀 업로드
              </div>
              <div className="mt-2 text-xs text-[#8B95A1]">`.xlsx`, `.xls`</div>
              <div className="mt-3">
                <input
                  ref={fileRef}
                  type="file"
                  accept=".xlsx,.xls"
                  className="block w-full text-sm text-[#8B95A1] file:mr-3 file:rounded-xl file:border-0 file:bg-black/[0.06] file:px-3 file:py-2 file:text-sm file:font-medium file:text-[#191F28] hover:file:bg-black/[0.08]"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
              {file ? (
                <div className="mt-3 rounded-2xl border border-[#E5E8EB] bg-white px-3 py-2 text-xs text-[#8B95A1]">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate">{file.name}</span>
                    <span className="font-mono">{fmtCompact(file.size)}B</span>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="rounded-3xl border border-[#E5E8EB] bg-white p-4">
              <div className="grid gap-3">
                <div>
                  <div className="text-xs font-medium text-[#8B95A1]">목표 연도</div>
                  <Input
                    value={targetYear}
                    onChange={(e) => setTargetYear(e.target.value)}
                    inputMode="numeric"
                    placeholder="2030"
                    className="mt-1"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-xs font-medium text-[#8B95A1]">PER 배수</div>
                    <div className="text-[11px] text-[#8B95A1]">{perMultiples.length}개</div>
                  </div>
                  <Input
                    value={perRaw}
                    onChange={(e) => setPerRaw(e.target.value)}
                    placeholder="10,20,30"
                    className="mt-1"
                  />
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {[8, 10, 12, 15, 20, 25, 30].map((p) => {
                      const active = perMultiples.includes(p);
                      return (
                        <button
                          key={p}
                          type="button"
                          className={cn(
                            "rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
                            active
                              ? "bg-[color:color-mix(in_oklab,var(--accent-cyan),white_86%)] text-[#191F28]"
                              : "bg-black/[0.05] text-[#8B95A1] hover:bg-black/[0.08]",
                          )}
                          onClick={() => {
                            const set = new Set(perMultiples);
                            if (set.has(p)) set.delete(p);
                            else set.add(p);
                            const next = Array.from(set).sort((a, b) => a - b);
                            setPerRaw(next.join(","));
                          }}
                        >
                          {p}x
                        </button>
                      );
                    })}
                  </div>
                </div>

                <Button className="mt-1 w-full" onClick={run} disabled={busy || !file}>
                  {busy ? <span className="inline-flex items-center gap-2"><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/50 border-t-white" />처리중</span> : (
                    <>
                      <Play className="h-4 w-4" />
                      생성
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </Card>

        <Card variant="strong" className="rounded-3xl p-5 lg:col-span-2">
          <div className="flex items-end justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-[#191F28]">최근 실행</div>
              <div className="mt-1 text-xs text-[#8B95A1]">{jobs.length}개</div>
            </div>
            <Badge tone="neutral">Exit</Badge>
          </div>

          <div className="mt-4 space-y-2">
            {jobs.length ? (
              jobs.slice(0, 8).map((j) => (
                <button
                  key={j.jobId}
                  type="button"
                  className={cn(
                    "w-full rounded-2xl border px-3 py-2 text-left transition-colors",
                    j.jobId === activeJobId
                      ? "border-[color:var(--accent-cyan)]/40 bg-[color:color-mix(in_oklab,var(--accent-cyan),white_92%)]"
                      : "border-[#E5E8EB] bg-white hover:bg-white",
                  )}
                  onClick={() => setActiveJobId(j.jobId)}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-[#191F28]">{j.title}</div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-[#8B95A1]">
                        <span className="font-mono">{j.jobId}</span>
                        <span>·</span>
                        <span className="font-mono">{(j.createdAt || "").replace("T", " ").slice(0, 16)}</span>
                      </div>
                    </div>
                    {statusBadge(j.status)}
                  </div>
                </button>
              ))
            ) : (
              <div className="rounded-2xl border border-[#E5E8EB] bg-white px-4 py-3 text-sm text-[#8B95A1]">
                아직 실행한 기록이 없습니다.
              </div>
            )}
          </div>
        </Card>
      </div>

      <Card variant="strong" className="rounded-3xl p-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-[#191F28]">시나리오</div>
            <div className="mt-1 text-xs text-[#8B95A1]">
              {activeJob ? (
                <>
                  선택된 잡: <span className="font-mono text-[#191F28]">{activeJob.jobId}</span>{" "}
                  {activeJob.status ? <span className="ml-2">{statusBadge(activeJob.status)}</span> : null}
                </>
              ) : (
                "잡을 선택하세요."
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {activeJob?.status === "succeeded" ? (
              <Button variant="secondary" onClick={() => downloadXlsx(activeJob)} disabled={busy}>
                <Download className="h-4 w-4" />
                엑셀 다운로드
              </Button>
            ) : null}
          </div>
        </div>

        {activeJob?.status === "failed" ? (
          <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {activeJob.error || "실패"}
          </div>
        ) : null}

        {activeJob?.status === "succeeded" && scenarios.length ? (
          <>
            <div className="mt-4 grid gap-3 md:grid-cols-4">
              <div className="rounded-3xl border border-[#E5E8EB] bg-white p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-[#191F28]">
                  <FileSpreadsheet className="h-4 w-4 text-[#3182F6]" />
                  요약
                </div>
                <div className="mt-3 space-y-2 text-xs">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[#8B95A1]">회사</span>
                    <span className="max-w-[14rem] truncate font-mono text-[#191F28]">
                      {assumptions.company_name || "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[#8B95A1]">목표연도</span>
                    <span className="font-mono text-[#191F28]">{assumptions.target_year ?? "—"}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[#8B95A1]">보유기간</span>
                    <span className="font-mono text-[#191F28]">
                      {typeof assumptions.holding_period_years === "number" ? `${assumptions.holding_period_years}y` : "—"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="rounded-3xl border border-[#E5E8EB] bg-white p-4">
                <div className="text-xs font-medium text-[#8B95A1]">Investment</div>
                <div className="mt-2 font-black tracking-tight text-2xl tracking-tight text-[#191F28]">
                  {fmtCompact(assumptions.investment_amount)}
                </div>
                <div className="mt-2 text-xs text-[#8B95A1]">
                  Shares <span className="ml-2 font-mono text-[#191F28]">{fmtCompact(assumptions.shares)}</span>
                </div>
                <div className="mt-1 text-xs text-[#8B95A1]">
                  Total <span className="ml-2 font-mono text-[#191F28]">{fmtCompact(assumptions.total_shares)}</span>
                </div>
              </div>

              <div className="rounded-3xl border border-[#E5E8EB] bg-white p-4">
                <div className="text-xs font-medium text-[#8B95A1]">Net Income (Target Year)</div>
                <div className="mt-2 font-black tracking-tight text-2xl tracking-tight text-[#191F28]">
                  {fmtCompact(assumptions.net_income)}
                </div>
                <div className="mt-3 text-xs text-[#8B95A1]">
                  PER 목록 <span className="ml-2 font-mono text-[#191F28]">{(assumptions.per_multiples || []).join(", ") || "—"}</span>
                </div>
              </div>

              <div className="rounded-3xl border border-[#E5E8EB] bg-white p-4">
                <div className="text-xs font-medium text-[#8B95A1]">Best IRR</div>
                <div className="mt-2 flex items-baseline justify-between gap-2">
                  <div className="font-black tracking-tight text-2xl tracking-tight text-[#191F28]">
                    {fmtIrr(best?.irr)}
                  </div>
                  <Badge tone={irrTone(best?.irr)}>{best ? `${best.per}x` : "—"}</Badge>
                </div>
                <div className="mt-3 text-xs text-[#8B95A1]">
                  Multiple <span className="ml-2 font-mono text-[#191F28]">{fmtMultiple(best?.multiple)}</span>
                </div>
              </div>
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <div className="rounded-3xl border border-[#E5E8EB] bg-white p-4">
                <div className="flex items-end justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-[#191F28]">IRR 분포</div>
                    <div className="mt-1 text-xs text-[#8B95A1]">PER에 따른 IRR 변화</div>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <Badge tone="success">30%+</Badge>
                    <Badge tone="warn">15-30%</Badge>
                    <Badge tone="danger">&lt;15%</Badge>
                  </div>
                </div>
                <div className="mt-4 h-[240px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={scenarios} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
                      <CartesianGrid stroke="rgba(0,0,0,0.06)" vertical={false} />
                      <XAxis dataKey="per" tickLine={false} axisLine={false} fontSize={12} />
                      <YAxis
                        tickLine={false}
                        axisLine={false}
                        fontSize={12}
                        tickFormatter={(v) => `${v}%`}
                        domain={[0, "auto"]}
                      />
                      <Tooltip content={<ExitTooltip />} />
                      <Bar dataKey="irr" radius={[10, 10, 2, 2]}>
                        {scenarios.map((s) => (
                          <Cell key={String(s.per)} fill={irrColor(s.irr)} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="rounded-3xl border border-[#E5E8EB] bg-white p-4">
                <div className="text-sm font-semibold text-[#191F28]">시나리오 테이블</div>
                <div className="mt-1 text-xs text-[#8B95A1]">IRR 기준으로 빠르게 비교합니다.</div>
                <div className="mt-4 overflow-hidden rounded-2xl border border-[#E5E8EB]">
                  <table className="w-full text-sm">
                    <thead className="bg-black/[0.03] text-xs text-[#8B95A1]">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium">PER</th>
                        <th className="px-3 py-2 text-left font-medium">IRR</th>
                        <th className="px-3 py-2 text-left font-medium">Multiple</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[color:var(--line)] bg-white">
                      {[...scenarios]
                        .sort((a, b) => (b.irr ?? -999) - (a.irr ?? -999))
                        .map((s) => (
                          <tr key={`row-${s.per}`} className="hover:bg-white">
                            <td className="px-3 py-2 font-mono text-[#191F28]">{s.per}x</td>
                            <td className="px-3 py-2">
                              <Badge tone={irrTone(s.irr)}>{fmtIrr(s.irr)}</Badge>
                            </td>
                            <td className="px-3 py-2 font-mono text-[#191F28]">{fmtMultiple(s.multiple)}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="mt-4 rounded-2xl border border-[#E5E8EB] bg-white px-4 py-3 text-sm text-[#8B95A1]">
            {activeJob?.status === "queued" || activeJob?.status === "running" ? "계산 중입니다. 잠시만 기다려주세요." : "결과가 아직 없습니다."}
          </div>
        )}
      </Card>
    </div>
  );
}
