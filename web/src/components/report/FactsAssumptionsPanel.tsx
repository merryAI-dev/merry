"use client";

import * as React from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { AssumptionPack, ComputeSnapshot, FactPack } from "@/lib/reportPacks";

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
  status: JobStatus;
  title: string;
  createdAt: string;
  artifacts?: JobArtifact[];
  metrics?: Record<string, unknown>;
};

type ValidationStatus = "pass" | "warn" | "fail";

type CheckResult = {
  check: string;
  status: ValidationStatus;
  message: string;
};

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.error || "FAILED");
  return json as T;
}

function toNumberInput(raw: string): number | undefined {
  const s = (raw ?? "").trim().replaceAll(",", "");
  if (!s) return undefined;
  const n = Number(s);
  return Number.isFinite(n) ? n : undefined;
}

function toPerArray(raw: string): number[] {
  const parts = (raw ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => Number(s))
    .filter((n) => Number.isFinite(n) && n > 0)
    .map((n) => Math.round(n * 1000) / 1000);

  const dedup: number[] = [];
  const seen = new Set<number>();
  for (const n of parts) {
    if (seen.has(n)) continue;
    seen.add(n);
    dedup.push(n);
  }
  return dedup.slice(0, 12);
}

function badgeForStatus(status?: JobStatus) {
  if (status === "succeeded") return <Badge tone="success">완료</Badge>;
  if (status === "failed") return <Badge tone="danger">실패</Badge>;
  if (status === "running") return <Badge tone="accent">진행 중</Badge>;
  if (status === "queued") return <Badge tone="neutral">대기</Badge>;
  return <Badge tone="neutral">—</Badge>;
}

function packBadge(status?: AssumptionPack["status"]) {
  if (status === "locked") return <Badge tone="success">locked</Badge>;
  if (status === "validated") return <Badge tone="accent">validated</Badge>;
  if (status === "draft") return <Badge tone="neutral">draft</Badge>;
  return <Badge tone="neutral">—</Badge>;
}

function upsertAssumptionNumber(pack: AssumptionPack, key: string, value: number | undefined) {
  const next = { ...pack };
  const assumptions = [...(next.assumptions || [])];
  const idx = assumptions.findIndex((a) => a.key === key);
  const cur = idx >= 0 ? assumptions[idx] : null;
  const evidence = cur?.evidence?.length ? cur.evidence : [{ note: "확인 필요" }];
  const unit = cur?.unit;
  const required = Boolean(cur?.required);
  const val = typeof value === "number" && Number.isFinite(value) ? value : undefined;
  const updated = {
    key,
    valueType: "number" as const,
    numberValue: val,
    unit,
    required,
    evidence,
  };
  if (idx >= 0) assumptions[idx] = { ...cur, ...updated };
  else assumptions.push(updated as any);
  next.assumptions = assumptions;
  return next;
}

function upsertAssumptionNumberArray(pack: AssumptionPack, key: string, value: number[]) {
  const next = { ...pack };
  const assumptions = [...(next.assumptions || [])];
  const idx = assumptions.findIndex((a) => a.key === key);
  const cur = idx >= 0 ? assumptions[idx] : null;
  const evidence = cur?.evidence?.length ? cur.evidence : [{ note: "확인 필요" }];
  const unit = cur?.unit;
  const required = Boolean(cur?.required);
  const updated = {
    key,
    valueType: "number_array" as const,
    numberArrayValue: value,
    unit,
    required,
    evidence,
  };
  if (idx >= 0) assumptions[idx] = { ...cur, ...updated };
  else assumptions.push(updated as any);
  next.assumptions = assumptions;
  return next;
}

export function FactsAssumptionsPanel(props: {
  sessionId: string;
  companyName?: string;
  evidenceJobs: JobRecord[];
}) {
  const { sessionId, companyName, evidenceJobs } = props;

  const [msg, setMsg] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const [selectedEvidenceJobId, setSelectedEvidenceJobId] = React.useState("");

  const [factPack, setFactPack] = React.useState<FactPack | null>(null);
  const [assumptionPack, setAssumptionPack] = React.useState<AssumptionPack | null>(null);
  const [checks, setChecks] = React.useState<CheckResult[] | null>(null);

  const [computeJob, setComputeJob] = React.useState<JobRecord | null>(null);

  const [xlsxFile, setXlsxFile] = React.useState<File | null>(null);
  const fileRef = React.useRef<HTMLInputElement | null>(null);

  const [fieldTargetYear, setFieldTargetYear] = React.useState("");
  const [fieldInvestmentYear, setFieldInvestmentYear] = React.useState("");
  const [fieldInvestmentAmount, setFieldInvestmentAmount] = React.useState("");
  const [fieldShares, setFieldShares] = React.useState("");
  const [fieldTotalShares, setFieldTotalShares] = React.useState("");
  const [fieldPricePerShare, setFieldPricePerShare] = React.useState("");
  const [fieldNetIncome, setFieldNetIncome] = React.useState("");
  const [fieldPerMultiples, setFieldPerMultiples] = React.useState("10,20,30");

  const loadAll = React.useCallback(async () => {
    setMsg(null);
    try {
      const [facts, assumps, compute] = await Promise.all([
        fetchJson<{ factPack: FactPack | null }>(`/api/report/${sessionId}/facts/latest`).catch(() => ({ factPack: null })),
        fetchJson<{ pack: AssumptionPack | null }>(`/api/report/${sessionId}/assumptions/latest`).catch(() => ({ pack: null })),
        fetchJson<{ snapshot: ComputeSnapshot | null; job: JobRecord | null }>(`/api/report/${sessionId}/compute/latest`).catch(() => ({ snapshot: null, job: null })),
      ]);

      setFactPack(facts.factPack ?? null);
      setAssumptionPack(assumps.pack ?? null);
      setComputeJob(compute.job ?? null);
    } catch {
      // Non-fatal. Individual calls already guarded.
    }
  }, [sessionId]);

  React.useEffect(() => {
    loadAll();
  }, [loadAll]);

  React.useEffect(() => {
    // Auto-refresh compute while running.
    const inflight = computeJob?.status === "queued" || computeJob?.status === "running";
    if (!inflight) return;
    const t = setInterval(() => loadAll(), 5000);
    return () => clearInterval(t);
  }, [computeJob?.status, loadAll]);

  React.useEffect(() => {
    if (!assumptionPack) return;

    const byKey = new Map<string, any>();
    for (const a of assumptionPack.assumptions || []) byKey.set(a.key, a);

    const n = (k: string) => {
      const v = byKey.get(k)?.numberValue;
      return typeof v === "number" && Number.isFinite(v) ? String(v) : "";
    };
    const arr = (k: string) => {
      const v = byKey.get(k)?.numberArrayValue;
      return Array.isArray(v) ? v.join(",") : "";
    };

    setFieldTargetYear(n("target_year"));
    setFieldInvestmentYear(n("investment_year"));
    setFieldInvestmentAmount(n("investment_amount"));
    setFieldShares(n("shares"));
    setFieldTotalShares(n("total_shares"));
    setFieldPricePerShare(n("price_per_share"));
    setFieldNetIncome(n("net_income_target_year"));
    setFieldPerMultiples(arr("per_multiples") || fieldPerMultiples);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assumptionPack?.packId]);

  async function buildFactPack() {
    const jobId =
      selectedEvidenceJobId.trim() ||
      evidenceJobs.find((j) => j.status === "succeeded")?.jobId ||
      "";
    if (!jobId) {
      setMsg("먼저 PDF 근거(pdf_evidence) 잡을 실행해 주세요.");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetchJson<{ factPackId: string; warnings: string[] }>(`/api/report/${sessionId}/facts/build`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sourceJobIds: [jobId] }),
      });
      setMsg(res.warnings?.length ? `FactPack 생성됨 (경고 ${res.warnings.length}개)` : "FactPack 생성됨");
      await loadAll();
    } catch (e) {
      const m = e instanceof Error ? e.message : "FAILED";
      setMsg(`FactPack 생성 실패: ${m}`);
    } finally {
      setBusy(false);
    }
  }

  async function suggestAssumptions() {
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetchJson<{ pack: AssumptionPack }>(`/api/report/${sessionId}/assumptions/suggest`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ factPackId: factPack?.factPackId, mode: "exit_projection" }),
      });
      setAssumptionPack(res.pack);
      setChecks(null);
      setMsg("가정(AssumptionPack) 초안을 생성했습니다. 필요한 값만 채운 뒤 검증하세요.");
    } catch (e) {
      const m = e instanceof Error ? e.message : "FAILED";
      setMsg(`가정 제안 실패: ${m}`);
    } finally {
      setBusy(false);
    }
  }

  async function saveAssumptions() {
    if (!assumptionPack) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetchJson<{ pack: AssumptionPack }>(`/api/report/${sessionId}/assumptions/save`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ pack: assumptionPack }),
      });
      setAssumptionPack(res.pack);
      setChecks(null);
      setMsg("가정을 저장했습니다.");
    } catch (e) {
      const m = e instanceof Error ? e.message : "FAILED";
      setMsg(`가정 저장 실패: ${m}`);
    } finally {
      setBusy(false);
    }
  }

  async function validateAssumptions() {
    if (!assumptionPack) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetchJson<{ status: ValidationStatus; checks: CheckResult[]; pack?: AssumptionPack }>(
        `/api/report/${sessionId}/assumptions/validate`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ packId: assumptionPack.packId }),
        },
      );
      setChecks(res.checks || null);
      if (res.pack) setAssumptionPack(res.pack);
      setMsg(res.status === "pass" ? "검증 통과" : res.status === "warn" ? "검증 경고 있음" : "검증 실패");
    } catch (e) {
      const m = e instanceof Error ? e.message : "FAILED";
      setMsg(`검증 실패: ${m}`);
    } finally {
      setBusy(false);
    }
  }

  async function lockAssumptions() {
    if (!assumptionPack) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetchJson<{ pack: AssumptionPack }>(`/api/report/${sessionId}/assumptions/lock`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ packId: assumptionPack.packId }),
      });
      setAssumptionPack(res.pack);
      setMsg("잠금(locked) 완료. 이제 섹션 생성은 이 가정 스냅샷을 기준으로 합니다.");
    } catch (e) {
      const m = e instanceof Error ? e.message : "FAILED";
      setMsg(`잠금 실패: ${m}`);
    } finally {
      setBusy(false);
    }
  }

  function syncPackFromFields(p: AssumptionPack): AssumptionPack {
    let next = { ...p };
    next = upsertAssumptionNumber(next, "target_year", toNumberInput(fieldTargetYear));
    next = upsertAssumptionNumber(next, "investment_year", toNumberInput(fieldInvestmentYear));
    next = upsertAssumptionNumber(next, "investment_amount", toNumberInput(fieldInvestmentAmount));
    next = upsertAssumptionNumber(next, "shares", toNumberInput(fieldShares));
    next = upsertAssumptionNumber(next, "total_shares", toNumberInput(fieldTotalShares));
    next = upsertAssumptionNumber(next, "price_per_share", toNumberInput(fieldPricePerShare));
    next = upsertAssumptionNumber(next, "net_income_target_year", toNumberInput(fieldNetIncome));
    next = upsertAssumptionNumberArray(next, "per_multiples", toPerArray(fieldPerMultiples));
    if (companyName && !next.companyName) next = { ...next, companyName };
    return next;
  }

  async function uploadAndComputeExitProjection() {
    if (!assumptionPack) {
      setMsg("먼저 AssumptionPack을 생성하세요.");
      return;
    }
    if (assumptionPack.status !== "locked") {
      setMsg("먼저 검증 후 잠금(locked)하세요.");
      return;
    }
    if (!xlsxFile) {
      setMsg("엑셀(.xlsx) 파일을 선택하세요.");
      return;
    }

    setBusy(true);
    setMsg(null);
    try {
      const presign = await fetchJson<{
        file: { fileId: string; contentType: string };
        upload: { url: string; headers: Record<string, string> };
      }>("/api/uploads/presign", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          filename: xlsxFile.name,
          contentType: xlsxFile.type || "application/octet-stream",
          sizeBytes: xlsxFile.size,
        }),
      });

      const putRes = await fetch(presign.upload.url, {
        method: "PUT",
        headers: presign.upload.headers,
        body: xlsxFile,
      });
      if (!putRes.ok) throw new Error("UPLOAD_FAILED");

      await fetchJson("/api/uploads/complete", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ fileId: presign.file.fileId }),
      });

      const started = await fetchJson<{ jobId: string }>(`/api/report/${sessionId}/compute/exit-projection`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ packId: assumptionPack.packId, fileId: presign.file.fileId }),
      });

      setMsg(`Exit 프로젝션 잡 생성: ${started.jobId}`);
      setXlsxFile(null);
      if (fileRef.current) fileRef.current.value = "";
      await loadAll();
    } catch (e) {
      const m = e instanceof Error ? e.message : "FAILED";
      if (m === "UPLOAD_FAILED") setMsg("업로드에 실패했습니다. S3 CORS/권한을 확인하세요.");
      else setMsg(`Exit 프로젝션 실행 실패: ${m}`);
    } finally {
      setBusy(false);
    }
  }

  async function downloadExitXlsx() {
    const jobId = computeJob?.jobId;
    if (!jobId) return;
    const artifactId = "exit_projection_xlsx";
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetchJson<{ url: string }>(`/api/jobs/${jobId}/artifact?artifactId=${artifactId}`);
      window.open(res.url, "_blank", "noopener,noreferrer");
    } catch {
      setMsg("다운로드 URL 발급에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  const locked = assumptionPack?.status === "locked";
  const editable = !locked;

  return (
    <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-4" id="step-evidence">
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs font-semibold text-[color:var(--ink)]">2. 근거(Facts) / 가정(Assumptions)</div>
        <Button variant="ghost" size="sm" onClick={loadAll} disabled={busy}>
          새로고침
        </Button>
      </div>

      {msg ? (
        <div className="mt-3 rounded-xl border border-[color:var(--line)] bg-white/80 px-3 py-2 text-xs text-[color:var(--muted)]">
          {msg}
        </div>
      ) : null}

      <div className="mt-3 space-y-3">
        <div className="rounded-xl border border-[color:var(--line)] bg-white/80 p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs font-semibold text-[color:var(--ink)]">FactPack</div>
            {factPack ? <Badge tone="accent">latest</Badge> : <Badge tone="neutral">none</Badge>}
          </div>
          <div className="mt-2 text-xs text-[color:var(--muted)]">
            {factPack ? (
              <>
                id: <span className="font-mono text-[color:var(--ink)]">{factPack.factPackId}</span> · facts{" "}
                {(factPack.facts || []).length} · warnings {(factPack.warnings || []).length}
              </>
            ) : (
              "아직 FactPack이 없습니다. PDF 근거 잡 결과에서 생성하세요."
            )}
          </div>

          <div className="mt-3 grid gap-2">
            <select
              className="h-11 w-full rounded-xl border border-[color:var(--line)] bg-white/80 px-3 text-sm text-[color:var(--ink)] outline-none focus:border-[color:var(--accent)]"
              value={selectedEvidenceJobId}
              onChange={(e) => setSelectedEvidenceJobId(e.target.value)}
              disabled={busy}
            >
              <option value="">근거 잡 선택(기본: 최신 성공)</option>
              {evidenceJobs.map((j) => (
                <option key={j.jobId} value={j.jobId}>
                  {j.title} · {j.jobId.slice(0, 8)} · {j.status}
                </option>
              ))}
            </select>
            <Button variant="secondary" onClick={buildFactPack} disabled={busy}>
              근거(Fact) 생성
            </Button>
          </div>
        </div>

        <div className="rounded-xl border border-[color:var(--line)] bg-white/80 p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs font-semibold text-[color:var(--ink)]">AssumptionPack</div>
            {packBadge(assumptionPack?.status)}
          </div>
          <div className="mt-2 text-xs text-[color:var(--muted)]">
            {assumptionPack ? (
              <>
                id: <span className="font-mono text-[color:var(--ink)]">{assumptionPack.packId}</span> ·{" "}
                {assumptionPack.status}
              </>
            ) : (
              "아직 AssumptionPack이 없습니다."
            )}
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={suggestAssumptions} disabled={busy}>
              가정 제안(LLM)
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => (assumptionPack ? setAssumptionPack(syncPackFromFields(assumptionPack)) : null)}
              disabled={busy || !assumptionPack || !editable}
            >
              입력값 반영
            </Button>
            <Button variant="secondary" size="sm" onClick={saveAssumptions} disabled={busy || !assumptionPack || !editable}>
              저장
            </Button>
            <Button variant="secondary" size="sm" onClick={validateAssumptions} disabled={busy || !assumptionPack || !editable}>
              검증
            </Button>
            <Button variant="primary" size="sm" onClick={lockAssumptions} disabled={busy || !assumptionPack || assumptionPack.status !== "validated"}>
              잠금
            </Button>
          </div>

          {assumptionPack ? (
            <div className="mt-3 grid gap-2">
              <div className="grid grid-cols-2 gap-2">
                <Input
                  placeholder="target_year"
                  value={fieldTargetYear}
                  onChange={(e) => setFieldTargetYear(e.target.value)}
                  disabled={!editable || busy}
                />
                <Input
                  placeholder="investment_year"
                  value={fieldInvestmentYear}
                  onChange={(e) => setFieldInvestmentYear(e.target.value)}
                  disabled={!editable || busy}
                />
              </div>
              <Input
                placeholder="investment_amount (KRW)"
                value={fieldInvestmentAmount}
                onChange={(e) => setFieldInvestmentAmount(e.target.value)}
                disabled={!editable || busy}
              />
              <div className="grid grid-cols-2 gap-2">
                <Input placeholder="shares" value={fieldShares} onChange={(e) => setFieldShares(e.target.value)} disabled={!editable || busy} />
                <Input placeholder="total_shares" value={fieldTotalShares} onChange={(e) => setFieldTotalShares(e.target.value)} disabled={!editable || busy} />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Input
                  placeholder="price_per_share (KRW)"
                  value={fieldPricePerShare}
                  onChange={(e) => setFieldPricePerShare(e.target.value)}
                  disabled={!editable || busy}
                />
                <Input
                  placeholder="net_income_target_year (KRW)"
                  value={fieldNetIncome}
                  onChange={(e) => setFieldNetIncome(e.target.value)}
                  disabled={!editable || busy}
                />
              </div>
              <Input
                placeholder="per_multiples (ex: 10,20,30)"
                value={fieldPerMultiples}
                onChange={(e) => setFieldPerMultiples(e.target.value)}
                disabled={!editable || busy}
              />
            </div>
          ) : null}

          {checks?.length ? (
            <div className="mt-3 space-y-1 text-xs">
              {checks.slice(0, 10).map((c, idx) => (
                <div key={idx} className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[10px] text-[color:var(--muted)]">{c.check}</span>
                  <span className="flex-1 truncate text-[color:var(--muted)]">{c.message}</span>
                  <Badge tone={c.status === "pass" ? "success" : c.status === "warn" ? "accent" : "danger"}>{c.status}</Badge>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <div className="rounded-xl border border-[color:var(--line)] bg-white/80 p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs font-semibold text-[color:var(--ink)]">Compute (Exit Projection)</div>
            {badgeForStatus(computeJob?.status)}
          </div>

          <div className="mt-2 text-xs text-[color:var(--muted)]">
            {computeJob?.jobId ? (
              <>
                job: <span className="font-mono text-[color:var(--ink)]">{computeJob.jobId}</span>
              </>
            ) : (
              "아직 실행된 Exit 프로젝션 잡이 없습니다."
            )}
          </div>

          <div className="mt-3 grid gap-2">
            <input
              ref={fileRef}
              type="file"
              accept=".xlsx,.xls"
              className="block w-full text-xs text-[color:var(--muted)]"
              onChange={(e) => setXlsxFile(e.target.files?.[0] ?? null)}
              disabled={busy}
            />
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" onClick={uploadAndComputeExitProjection} disabled={busy || !xlsxFile || !locked}>
                업로드 & 실행
              </Button>
              <Button variant="secondary" onClick={downloadExitXlsx} disabled={busy || computeJob?.status !== "succeeded"}>
                XLSX 다운로드
              </Button>
            </div>
          </div>

          {computeJob?.metrics?.projection_summary ? (
            <div className="mt-3 text-xs text-[color:var(--muted)]">
              projection_summary:{" "}
              <span className="font-mono text-[color:var(--ink)]">
                {Array.isArray(computeJob.metrics.projection_summary) ? `${computeJob.metrics.projection_summary.length} rows` : "ok"}
              </span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
