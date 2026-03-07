"use client";

import * as React from "react";
import {
  CheckSquare,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  Download,
  FileText,
  Loader2,
  OctagonX,
  RefreshCw,
  RotateCcw,
  Search,
  Square,
  X,
} from "lucide-react";
import { apiFetch } from "@/lib/apiClient";

import { Badge, type BadgeProps } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { useToast } from "@/components/ui/Toast";
import { cn } from "@/lib/cn";

/* ── Types (mirror server types) ── */

type JobStatus = "queued" | "running" | "succeeded" | "failed";
type FanoutStatus = "splitting" | "running" | "assembling" | "succeeded" | "failed";

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
  error?: string;
  artifacts?: JobArtifact[];
  metrics?: Record<string, unknown>;
  fanout?: boolean;
  totalTasks?: number;
  processedCount?: number;
  failedCount?: number;
  fanoutStatus?: FanoutStatus;
};

type ConditionResult = {
  condition?: string;
  result?: boolean;
  evidence?: string;
};

type TaskResult = {
  filename?: string;
  company_name?: string;
  company_group_name?: string;
  company_group_key?: string;
  method?: string;
  pages?: number;
  elapsed_s?: number;
  text_chars?: number;
  conditions?: ConditionResult[];
  condition_summary?: Record<string, unknown>;
  detected_facts?: Record<string, unknown>;
  cache?: Record<string, unknown>;
  parse_warning?: string;
  raw_response?: string;
  error?: string;
  [key: string]: unknown;
};

type TaskRecord = {
  taskId: string;
  jobId: string;
  taskIndex: number;
  status: string;
  fileId: string;
  createdAt: string;
  updatedAt?: string;
  startedAt?: string;
  endedAt?: string;
  error?: string;
  result?: TaskResult;
};

/* ── Helpers ── */

const JOB_TYPE_LABELS: Record<string, string> = {
  exit_projection: "Exit 프로젝션",
  diagnosis_analysis: "기업진단 분석",
  pdf_evidence: "PDF 근거 추출",
  pdf_parse: "PDF 파싱",
  contract_review: "계약서 검토",
  document_extraction: "문서 일괄 추출",
  condition_check: "조건 검사",
  financial_extraction: "재무 데이터 추출",
};

function statusTone(s: JobStatus): BadgeProps["tone"] {
  switch (s) {
    case "succeeded": return "success";
    case "failed": return "danger";
    case "running": return "accent";
    default: return "neutral";
  }
}

function statusLabel(s: JobStatus): string {
  switch (s) {
    case "queued": return "대기";
    case "running": return "진행 중";
    case "succeeded": return "완료";
    case "failed": return "실패";
    default: return s;
  }
}

function taskStatusTone(s: string): BadgeProps["tone"] {
  switch (s) {
    case "succeeded": return "success";
    case "failed": return "danger";
    case "processing": return "accent";
    default: return "neutral";
  }
}

function taskStatusLabel(s: string): string {
  switch (s) {
    case "pending": return "대기";
    case "processing": return "처리 중";
    case "succeeded": return "성공";
    case "failed": return "실패";
    default: return s;
  }
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "방금 전";
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  return `${days}일 전`;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function readMetricNumber(metrics: Record<string, unknown> | undefined, key: string): number {
  if (!metrics) return 0;
  const value = metrics[key];
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
}

function formatMetricValue(key: string, value: unknown): string {
  if (key === "artifacts_bytes" && typeof value === "number") {
    return formatBytes(value);
  }
  if (key === "ended_at" && typeof value === "string") {
    return new Date(value).toLocaleString("ko-KR");
  }
  if (typeof value === "number") {
    return value.toLocaleString();
  }
  return String(value ?? "-");
}

type CompanyGroupSummary = {
  key: string;
  name: string;
  fileCount: number;
  successCount: number;
  failedCount: number;
  warningCount: number;
  resultCacheHits: number;
  parseCacheHits: number;
  ruleConditionCount: number;
  llmConditionCount: number;
  variants: string[];
};

function buildConditionCompanyGroups(tasks: TaskRecord[] | undefined): CompanyGroupSummary[] {
  if (!tasks?.length) return [];

  const groups = new Map<string, CompanyGroupSummary>();
  for (const task of tasks) {
    const result = task.result;
    if (!result || typeof result !== "object") continue;

    const detectedFacts = result.detected_facts && typeof result.detected_facts === "object"
      ? result.detected_facts as Record<string, unknown>
      : undefined;
    const companyName = typeof result.company_name === "string" ? result.company_name.trim() : "";
    const companyGroupName = typeof result.company_group_name === "string"
      ? result.company_group_name.trim()
      : typeof detectedFacts?.company_group_name === "string"
        ? String(detectedFacts.company_group_name).trim()
        : "";
    const companyGroupKey = typeof result.company_group_key === "string"
      ? result.company_group_key.trim().toLowerCase()
      : typeof detectedFacts?.company_group_key === "string"
        ? String(detectedFacts.company_group_key).trim().toLowerCase()
        : "";
    if (!companyGroupKey || !companyGroupName) continue;

    const cacheInfo = result.cache && typeof result.cache === "object"
      ? result.cache as Record<string, unknown>
      : undefined;
    const summary = result.condition_summary && typeof result.condition_summary === "object"
      ? result.condition_summary as Record<string, unknown>
      : undefined;
    const existing = groups.get(companyGroupKey) ?? {
      key: companyGroupKey,
      name: companyGroupName,
      fileCount: 0,
      successCount: 0,
      failedCount: 0,
      warningCount: 0,
      resultCacheHits: 0,
      parseCacheHits: 0,
      ruleConditionCount: 0,
      llmConditionCount: 0,
      variants: [],
    };

    existing.fileCount += 1;
    existing.successCount += task.status === "succeeded" ? 1 : 0;
    existing.failedCount += task.status === "failed" ? 1 : 0;
    existing.warningCount += typeof result.parse_warning === "string" && result.parse_warning ? 1 : 0;
    existing.resultCacheHits += cacheInfo?.result_hit === true ? 1 : 0;
    existing.parseCacheHits += cacheInfo?.parse_hit === true ? 1 : 0;
    existing.ruleConditionCount += readMetricNumber(summary, "rule_count");
    existing.llmConditionCount += readMetricNumber(summary, "llm_count");
    if (companyName && !existing.variants.includes(companyName)) {
      existing.variants.push(companyName);
    }
    groups.set(companyGroupKey, existing);
  }

  return Array.from(groups.values()).sort((a, b) => {
    if (b.fileCount !== a.fileCount) return b.fileCount - a.fileCount;
    return a.name.localeCompare(b.name, "ko-KR");
  });
}

const METRIC_LABELS: Record<string, string> = {
  total: "총 파일",
  success_count: "성공 파일",
  failed_count: "실패 파일",
  warning_count: "복구 경고",
  company_group_count: "기업 그룹",
  recognized_company_files: "기업명 인식 파일",
  unrecognized_company_files: "기업명 미인식 파일",
  result_cache_hits: "결과 캐시 적중",
  parse_cache_hits: "파싱 캐시 적중",
  rule_condition_count: "규칙 판정 조건",
  llm_condition_count: "LLM 판정 조건",
  rule_only_files: "규칙 전용 파일",
  text_chars: "분석 텍스트",
  saved_total_tokens: "절감 토큰",
  artifacts_bytes: "결과물 크기",
  ended_at: "종료 시각",
};

/** Estimate Bedrock Nova Pro cost from token counts. */
function estimateCost(tokenUsage: { input_tokens?: number; output_tokens?: number }): string {
  const input = tokenUsage.input_tokens ?? 0;
  const output = tokenUsage.output_tokens ?? 0;
  // Nova Pro pricing: $0.0008/1K input, $0.0032/1K output
  const cost = (input / 1000) * 0.0008 + (output / 1000) * 0.0032;
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

/* ── Filter options ── */

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "전체" },
  { value: "running", label: "진행 중" },
  { value: "succeeded", label: "완료" },
  { value: "failed", label: "실패" },
  { value: "queued", label: "대기" },
];

const TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "전체" },
  ...Object.entries(JOB_TYPE_LABELS).map(([value, label]) => ({ value, label })),
];

const PAGE_SIZE = 20;

/* ── Page ── */

export default function HistoryPage() {
  const { toast } = useToast();
  const [jobs, setJobs] = React.useState<JobRecord[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [expandedJobId, setExpandedJobId] = React.useState<string | null>(null);
  const [tasks, setTasks] = React.useState<Record<string, TaskRecord[]>>({});
  const [loadingTasks, setLoadingTasks] = React.useState<Record<string, boolean>>({});

  // Filter & pagination state.
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [typeFilter, setTypeFilter] = React.useState("all");
  const [searchQuery, setSearchQuery] = React.useState("");
  const [debouncedQuery, setDebouncedQuery] = React.useState("");
  const [offset, setOffset] = React.useState(0);
  const [total, setTotal] = React.useState(0);
  const [hasMore, setHasMore] = React.useState(false);

  // Debounce search query.
  React.useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Reset offset when filters change.
  React.useEffect(() => {
    setOffset(0);
  }, [statusFilter, typeFilter, debouncedQuery]);

  const fetchJobs = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("limit", String(PAGE_SIZE));
      params.set("offset", String(offset));
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (typeFilter !== "all") params.set("type", typeFilter);
      if (debouncedQuery) params.set("q", debouncedQuery);

      const data = await apiFetch<{ ok: boolean; jobs?: unknown[]; total?: number; hasMore?: boolean }>(`/api/jobs?${params}`);
      setJobs((data.jobs as typeof jobs) || []);
      setTotal(data.total ?? 0);
      setHasMore(data.hasMore ?? false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [offset, statusFilter, typeFilter, debouncedQuery]);

  React.useEffect(() => { fetchJobs(); }, [fetchJobs]);

  const toggleExpand = React.useCallback(async (jobId: string, fanout?: boolean) => {
    if (expandedJobId === jobId) {
      setExpandedJobId(null);
      return;
    }
    setExpandedJobId(jobId);
    if (fanout && !tasks[jobId]) {
      setLoadingTasks((p) => ({ ...p, [jobId]: true }));
      try {
        const data = await apiFetch<{ ok: boolean; tasks?: unknown[] }>(`/api/jobs/${jobId}/tasks`);
        setTasks((p) => ({ ...p, [jobId]: (data.tasks as typeof tasks[string]) || [] }));
      } catch {
        // silent
      } finally {
        setLoadingTasks((p) => ({ ...p, [jobId]: false }));
      }
    }
  }, [expandedJobId, tasks]);

  // Multi-select & bulk retry state.
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [bulkRetrying, setBulkRetrying] = React.useState(false);
  const searchRef = React.useRef<HTMLInputElement>(null);

  const toggleSelect = React.useCallback((jobId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  }, []);

  const handleBulkRetry = React.useCallback(async () => {
    if (selected.size === 0) return;
    setBulkRetrying(true);
    try {
      const data = await apiFetch<{
        ok: boolean;
        totalRetried: number;
        failedJobs: number;
        results: Array<{ jobId: string; ok: boolean; retriedCount?: number; error?: string }>;
      }>("/api/jobs/bulk-retry", {
        method: "POST",
        body: JSON.stringify({ jobIds: Array.from(selected) }),
      });

      if (data.totalRetried > 0) {
        setSelected(new Set());
        await fetchJobs();
      }

      if (data.failedJobs === 0) {
        toast(`선택한 작업 ${data.results.length}건을 재시도했습니다`, "success");
        return;
      }

      const firstError = data.results.find((result) => !result.ok)?.error;
      if (data.totalRetried > 0) {
        toast(`일부만 재시도했습니다. 실패 ${data.failedJobs}건${firstError ? ` (${firstError})` : ""}`, "info", 5000);
        return;
      }

      toast(`재시도에 실패했습니다${firstError ? `: ${firstError}` : ""}`, "error", 6000);
    } catch {
      toast("일괄 재시도 요청에 실패했습니다", "error", 6000);
    } finally {
      setBulkRetrying(false);
    }
  }, [selected, fetchJobs, toast]);

  // Keyboard shortcuts.
  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      // Cmd/Ctrl + K → focus search
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        searchRef.current?.focus();
        return;
      }
      // Escape → clear search & selection
      if (e.key === "Escape") {
        if (searchQuery) {
          setSearchQuery("");
        }
        if (selected.size > 0) {
          setSelected(new Set());
        }
        (document.activeElement as HTMLElement)?.blur?.();
        return;
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [searchQuery, selected.size]);

  // Clear selection when jobs change.
  React.useEffect(() => {
    setSelected(new Set());
  }, [jobs]);

  const [cancelling, setCancelling] = React.useState<string | null>(null);

  const handleCancel = React.useCallback(async (jobId: string) => {
    if (!confirm("이 작업을 취소하시겠습니까? 진행 중인 개별 작업은 완료 후 결과가 무시됩니다.")) return;
    setCancelling(jobId);
    try {
      const data = await apiFetch<{ ok: boolean }>(`/api/jobs/${jobId}/cancel`, { method: "POST" });
      if (data.ok) {
        await fetchJobs();
      }
    } catch {
      // silent
    } finally {
      setCancelling(null);
    }
  }, [fetchJobs]);

  const handleDownload = React.useCallback(async (jobId: string, artifactId: string) => {
    try {
      const data = await apiFetch<{ ok: boolean; url?: string }>(`/api/jobs/${jobId}/artifact?artifactId=${artifactId}`);
      if (data.ok && data.url) {
        window.open(data.url, "_blank");
      }
    } catch {
      // silent
    }
  }, []);

  const handleDownloadAll = React.useCallback(async (jobId: string) => {
    try {
      const data = await apiFetch<{ ok: boolean; url?: string }>(`/api/jobs/${jobId}/artifact/zip`);
      if (data.ok && data.url) {
        window.open(data.url, "_blank");
      }
    } catch {
      // silent
    }
  }, []);

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#191F28]">작업 이력</h1>
          <p className="mt-1 text-sm text-[#8B95A1]">
            최근 실행된 배치 작업 목록과 상세 결과를 확인합니다.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={fetchJobs}
          disabled={loading}
        >
          <RefreshCw className={cn("mr-1.5 h-4 w-4", loading && "animate-spin")} />
          새로고침
        </Button>
      </div>

      {/* Filters */}
      <Card className="flex flex-wrap items-center gap-3 p-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#B0B8C1]" />
          <Input
            ref={searchRef}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="제목, Job ID로 검색... (⌘K)"
            className="h-9 pl-9 pr-8 text-xs"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2"
            >
              <X className="h-3.5 w-3.5 text-[#B0B8C1] hover:text-[#4E5968]" />
            </button>
          )}
        </div>

        {/* Status filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-[#8B95A1] shrink-0">상태</span>
          <div className="flex rounded-lg border border-[#E5E8EB] overflow-hidden">
            {STATUS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setStatusFilter(opt.value)}
                className={cn(
                  "px-2.5 py-1.5 text-[11px] font-medium transition-colors",
                  statusFilter === opt.value
                    ? "bg-[#3182F6] text-white"
                    : "bg-white text-[#4E5968] hover:bg-[#F2F4F6]",
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Type filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-[#8B95A1] shrink-0">유형</span>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="h-8 rounded-lg border border-[#E5E8EB] bg-white px-2 text-[11px] text-[#4E5968] outline-none focus:border-[#3182F6]"
          >
            {TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {/* Bulk actions + result count */}
        <div className="flex items-center gap-2 ml-auto">
          {selected.size > 0 && (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleBulkRetry}
              disabled={bulkRetrying}
            >
              {bulkRetrying ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
              )}
              {selected.size}개 재시도
            </Button>
          )}
          <span className="text-[11px] text-[#B0B8C1] tabular-nums">
            {total}건
          </span>
        </div>
      </Card>

      {/* Error */}
      {error && (
        <Card className="border-rose-200 bg-rose-50 p-4">
          <p className="text-sm text-rose-700">{error}</p>
        </Card>
      )}

      {/* Loading */}
      {loading && jobs.length === 0 && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-[#3182F6]" />
          <span className="ml-2 text-sm text-[#8B95A1]">불러오는 중...</span>
        </div>
      )}

      {/* Empty */}
      {!loading && jobs.length === 0 && !error && (
        <Card className="flex flex-col items-center justify-center py-20">
          <Clock className="h-10 w-10 text-[#D1D6DB]" />
          <p className="mt-3 text-sm text-[#8B95A1]">
            {statusFilter !== "all" || typeFilter !== "all" || debouncedQuery
              ? "검색 결과가 없습니다."
              : "아직 실행된 작업이 없습니다."}
          </p>
        </Card>
      )}

      {/* Job list */}
      <div className="space-y-3">
        {jobs.map((job) => {
          const isExpanded = expandedJobId === job.jobId;
          const jobTasks = tasks[job.jobId];
          const isLoadingTasks = loadingTasks[job.jobId];
          const metrics = job.metrics && typeof job.metrics === "object"
            ? job.metrics as Record<string, unknown>
            : undefined;
          const warningCount = readMetricNumber(metrics, "warning_count");
          const pct = job.fanout && job.totalTasks
            ? Math.round(((job.processedCount ?? 0) / job.totalTasks) * 100)
            : null;

          return (
            <Card key={job.jobId} className="overflow-hidden">
              {/* Job Row */}
              <div className="flex items-center">
                {/* Checkbox for failed fanout jobs */}
                {job.fanout && job.status === "failed" ? (
                  <button
                    type="button"
                    className="shrink-0 pl-3 py-4 text-[#8B95A1] hover:text-[#3182F6]"
                    onClick={(e) => { e.stopPropagation(); toggleSelect(job.jobId); }}
                    aria-label={selected.has(job.jobId) ? "선택 해제" : "재시도 대상 선택"}
                  >
                    {selected.has(job.jobId)
                      ? <CheckSquare className="h-4 w-4 text-[#3182F6]" />
                      : <Square className="h-4 w-4" />}
                  </button>
                ) : (
                  <span className="w-7 shrink-0" />
                )}

              <button
                type="button"
                className="flex flex-1 items-center gap-3 px-3 py-4 text-left hover:bg-[#F9FAFB] transition-colors"
                onClick={() => toggleExpand(job.jobId, job.fanout)}
                aria-expanded={isExpanded}
              >
                {/* Expand icon */}
                {job.fanout ? (
                  isExpanded
                    ? <ChevronDown className="h-4 w-4 shrink-0 text-[#8B95A1]" />
                    : <ChevronRight className="h-4 w-4 shrink-0 text-[#8B95A1]" />
                ) : (
                  <FileText className="h-4 w-4 shrink-0 text-[#8B95A1]" />
                )}

                {/* Status */}
                <Badge tone={statusTone(job.status)}>{statusLabel(job.status)}</Badge>

                {/* Title + type */}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-[#191F28]">
                    {job.title}
                  </p>
                  <p className="text-xs text-[#8B95A1]">
                    {JOB_TYPE_LABELS[job.type] || job.type}
                    {job.fanout && job.totalTasks != null && (
                      <span className="ml-2">
                        ({job.processedCount ?? 0}/{job.totalTasks} 파일
                        {warningCount > 0 && (
                          <span className="text-amber-600"> | 경고 {warningCount}</span>
                        )}
                        {(job.failedCount ?? 0) > 0 && (
                          <span className="text-rose-500"> | 실패 {job.failedCount}</span>
                        )}
                        )
                      </span>
                    )}
                  </p>
                </div>

                {/* Progress bar (fan-out running) */}
                {job.fanout && job.status === "running" && pct !== null && (
                  <div className="hidden sm:flex items-center gap-2 w-32">
                    <div className="flex-1 h-1.5 rounded-full bg-[#E5E8EB] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[#3182F6] transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-xs text-[#8B95A1] tabular-nums">{pct}%</span>
                  </div>
                )}

                {/* Timestamp + creator */}
                <div className="hidden sm:block text-right shrink-0">
                  <p className="text-xs text-[#8B95A1]">{relativeTime(job.createdAt)}</p>
                  <p className="text-xs text-[#B0B8C1]">{job.createdBy}</p>
                </div>
              </button>
              </div>

              {/* Expanded Detail */}
              {isExpanded && (
                <div className="border-t border-[#F2F4F6] bg-[#FAFBFC] px-5 py-4 space-y-4">
                  {/* Metadata */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div>
                      <span className="text-[#8B95A1]">Job ID</span>
                      <p className="font-mono text-[#4E5968]">{job.jobId}</p>
                    </div>
                    <div>
                      <span className="text-[#8B95A1]">생성 시각</span>
                      <p className="text-[#4E5968]">{new Date(job.createdAt).toLocaleString("ko-KR")}</p>
                    </div>
                    <div>
                      <span className="text-[#8B95A1]">파일 수</span>
                      <p className="text-[#4E5968]">{job.inputFileIds?.length ?? 0}</p>
                    </div>
                    {job.error && (
                      <div className="col-span-2 sm:col-span-4">
                        <span className="text-[#8B95A1]">에러</span>
                        <p className="text-rose-600 font-mono text-xs break-all">{job.error}</p>
                      </div>
                    )}
                  </div>

                  {/* Cancel button for running fan-out jobs */}
                  {job.fanout && job.status === "running" && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleCancel(job.jobId)}
                      disabled={cancelling === job.jobId}
                      className="text-rose-600 border-rose-200 hover:bg-rose-50"
                    >
                      {cancelling === job.jobId ? (
                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <OctagonX className="mr-1.5 h-3.5 w-3.5" />
                      )}
                      작업 취소
                    </Button>
                  )}

                  {/* Token Usage / Cost */}
                  {metrics &&
                    typeof metrics.token_usage === "object" &&
                    metrics.token_usage !== null && (() => {
                    const tu = metrics.token_usage as {
                      input_tokens?: number; output_tokens?: number; total_tokens?: number;
                    };
                    return (tu.total_tokens ?? 0) > 0;
                  })() && (
                    <div>
                      <p className="text-xs font-medium text-[#8B95A1] mb-1">API 사용량</p>
                      {(() => {
                        const tu = metrics.token_usage as {
                          input_tokens?: number; output_tokens?: number; total_tokens?: number;
                        };
                        return (
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                            <div className="rounded bg-white px-2.5 py-1.5 border border-[#E5E8EB]">
                              <span className="text-[#8B95A1]">입력 토큰</span>
                              <p className="font-mono text-[#191F28]">{(tu.input_tokens ?? 0).toLocaleString()}</p>
                            </div>
                            <div className="rounded bg-white px-2.5 py-1.5 border border-[#E5E8EB]">
                              <span className="text-[#8B95A1]">출력 토큰</span>
                              <p className="font-mono text-[#191F28]">{(tu.output_tokens ?? 0).toLocaleString()}</p>
                            </div>
                            <div className="rounded bg-white px-2.5 py-1.5 border border-[#E5E8EB]">
                              <span className="text-[#8B95A1]">총 토큰</span>
                              <p className="font-mono text-[#191F28]">{(tu.total_tokens ?? 0).toLocaleString()}</p>
                            </div>
                            <div className="rounded bg-white px-2.5 py-1.5 border border-blue-200 bg-blue-50">
                              <span className="text-[#8B95A1]">예상 비용</span>
                              <p className="font-mono text-[#3182F6] font-semibold">{estimateCost(tu)}</p>
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  )}

                  {/* Metrics */}
                  {metrics && Object.keys(metrics).length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-[#8B95A1] mb-1">메트릭</p>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                        {Object.entries(metrics)
                          .filter(([k, v]) => (
                            k !== "token_usage" &&
                            k !== "deleted_inputs" &&
                            k !== "conditions" &&
                            (typeof v !== "object" || v === null)
                          ))
                          .map(([k, v]) => (
                          <div key={k} className="rounded bg-white px-2.5 py-1.5 border border-[#E5E8EB]">
                            <span className="text-[#8B95A1]">{METRIC_LABELS[k] || k}</span>
                            <p className="font-mono text-[#191F28]">
                              {formatMetricValue(k, v)}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Artifacts */}
                  {job.artifacts && job.artifacts.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-xs font-medium text-[#8B95A1]">결과 파일</p>
                        {job.artifacts.length > 1 && (
                          <Button
                            variant="secondary"
                            size="sm"
                            className="h-6 text-[10px] px-2"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDownloadAll(job.jobId);
                            }}
                          >
                            <Download className="mr-1 h-3 w-3" />
                            ZIP 전체 다운로드
                          </Button>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {job.artifacts.map((a) => (
                          <Button
                            key={a.artifactId}
                            variant="secondary"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDownload(job.jobId, a.artifactId);
                            }}
                          >
                            <Download className="mr-1.5 h-3.5 w-3.5" />
                            {a.label}
                            {a.sizeBytes != null && (
                              <span className="ml-1 text-[#8B95A1]">
                                ({formatBytes(a.sizeBytes)})
                              </span>
                            )}
                          </Button>
                        ))}
                      </div>
                    </div>
                  )}

                  {job.type === "condition_check" && (
                    <ConditionCompanyGroupPanel tasks={jobTasks} />
                  )}

                  {/* Fan-out Tasks */}
                  {job.fanout && (
                    <TaskDetailPanel
                      tasks={jobTasks}
                      loading={isLoadingTasks}
                      totalTasks={job.totalTasks ?? 0}
                    />
                  )}
                </div>
              )}
            </Card>
          );
        })}
      </div>

      {/* Pagination */}
      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-[#8B95A1] tabular-nums">
            {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} / {total}건
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              <ChevronLeft className="mr-1 h-3.5 w-3.5" />
              이전
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={!hasMore}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              다음
              <ChevronRight className="ml-1 h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}


/* ── Task Detail Panel (accordion) ── */

function ConditionCompanyGroupPanel({ tasks }: { tasks?: TaskRecord[] }) {
  const groups = React.useMemo(() => buildConditionCompanyGroups(tasks), [tasks]);
  if (groups.length === 0) return null;

  return (
    <div>
      <p className="text-xs font-medium text-[#8B95A1] mb-2">
        기업 그룹 ({groups.length}개)
      </p>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {groups.slice(0, 6).map((group) => (
          <div key={group.key} className="rounded border border-[#E5E8EB] bg-white px-3 py-2.5">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-[#191F28]">{group.name}</p>
                {group.variants.length > 1 && (
                  <p className="mt-0.5 text-[11px] text-[#8B95A1]">
                    표기 {group.variants.slice(0, 2).join(" · ")}
                    {group.variants.length > 2 && ` 외 ${group.variants.length - 2}개`}
                  </p>
                )}
              </div>
              <span className="rounded-full bg-[#F2F4F6] px-2 py-0.5 text-[11px] font-medium text-[#4E5968]">
                {group.fileCount}건
              </span>
            </div>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-[#4E5968]">
              <span>성공 {group.successCount}</span>
              {group.failedCount > 0 && <span className="text-rose-600">실패 {group.failedCount}</span>}
              {group.warningCount > 0 && <span className="text-amber-700">경고 {group.warningCount}</span>}
              {group.resultCacheHits > 0 && <span className="text-blue-700">결과 캐시 {group.resultCacheHits}</span>}
              {group.parseCacheHits > 0 && <span className="text-sky-700">파싱 캐시 {group.parseCacheHits}</span>}
            </div>
            <div className="mt-2 text-[11px] text-[#8B95A1]">
              규칙 {group.ruleConditionCount} · LLM {group.llmConditionCount}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TaskDetailPanel({
  tasks,
  loading,
  totalTasks,
}: {
  tasks?: TaskRecord[];
  loading?: boolean;
  totalTasks: number;
}) {
  const [expandedTaskId, setExpandedTaskId] = React.useState<string | null>(null);

  return (
    <div>
      <p className="text-xs font-medium text-[#8B95A1] mb-2">
        개별 작업 ({totalTasks}건)
      </p>
      {loading ? (
        <div className="flex items-center gap-2 py-3">
          <Loader2 className="h-4 w-4 animate-spin text-[#3182F6]" />
          <span className="text-xs text-[#8B95A1]">로딩 중...</span>
        </div>
      ) : tasks && tasks.length > 0 ? (
        <div className="max-h-[500px] overflow-y-auto rounded border border-[#E5E8EB] bg-white divide-y divide-[#F2F4F6]">
          {tasks.map((t) => {
            const isOpen = expandedTaskId === t.taskId;
            const hasResult = t.result && typeof t.result === "object";
            const cacheInfo = t.result?.cache && typeof t.result.cache === "object"
              ? t.result.cache as Record<string, unknown>
              : undefined;
            const conditionSummary = t.result?.condition_summary && typeof t.result.condition_summary === "object"
              ? t.result.condition_summary as Record<string, unknown>
              : undefined;
            const detectedFacts = t.result?.detected_facts && typeof t.result.detected_facts === "object"
              ? t.result.detected_facts as Record<string, unknown>
              : undefined;
            const parseWarning = typeof t.result?.parse_warning === "string"
              ? t.result.parse_warning
              : "";
            const rawResponse = typeof t.result?.raw_response === "string"
              ? t.result.raw_response
              : "";
            const ruleCount = readMetricNumber(conditionSummary, "rule_count");
            const llmCount = readMetricNumber(conditionSummary, "llm_count");
            const isResultCacheHit = cacheInfo?.result_hit === true;
            const isParseCacheHit = cacheInfo?.parse_hit === true;
            const savedInputTokens = readMetricNumber(cacheInfo, "saved_input_tokens");
            const savedOutputTokens = readMetricNumber(cacheInfo, "saved_output_tokens");
            const establishmentDate = typeof detectedFacts?.establishment_date === "string"
              ? detectedFacts.establishment_date
              : "";
            const businessAgeYears = typeof detectedFacts?.business_age_years === "number"
              ? detectedFacts.business_age_years
              : null;
            const revenueCandidates = Array.isArray(detectedFacts?.revenue_candidates)
              ? detectedFacts.revenue_candidates
                  .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
                  .slice(0, 3)
              : [];
            return (
              <div key={t.taskId}>
                {/* Task row */}
                <button
                  type="button"
                  className="flex w-full items-center gap-2.5 px-3 py-2 text-left hover:bg-[#FAFBFC] transition-colors text-xs"
                  onClick={() => setExpandedTaskId(isOpen ? null : t.taskId)}
                >
                  {hasResult ? (
                    isOpen
                      ? <ChevronDown className="h-3 w-3 shrink-0 text-[#8B95A1]" />
                      : <ChevronRight className="h-3 w-3 shrink-0 text-[#8B95A1]" />
                  ) : (
                    <span className="w-3" />
                  )}
                  <span className="font-mono text-[#8B95A1] w-8 shrink-0 tabular-nums">{t.taskIndex}</span>
                  <Badge tone={taskStatusTone(t.status)}>
                    {taskStatusLabel(t.status)}
                  </Badge>
                  <span className="min-w-0 flex-1 truncate text-[#4E5968]">
                    {t.result?.filename || t.result?.company_name || t.fileId}
                  </span>
                  {t.result?.elapsed_s != null && (
                    <span className="text-[#B0B8C1] tabular-nums shrink-0">{t.result.elapsed_s}s</span>
                  )}
                  {parseWarning && (
                    <span className="shrink-0 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                      복구 응답
                    </span>
                  )}
                  {isResultCacheHit && (
                    <span className="shrink-0 rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700">
                      결과 캐시
                    </span>
                  )}
                  {!isResultCacheHit && isParseCacheHit && (
                    <span className="shrink-0 rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-[10px] font-medium text-sky-700">
                      파싱 캐시
                    </span>
                  )}
                  {ruleCount > 0 && (
                    <span className="shrink-0 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                      규칙 {ruleCount}
                    </span>
                  )}
                  {llmCount > 0 && (
                    <span className="shrink-0 rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-[10px] font-medium text-violet-700">
                      LLM {llmCount}
                    </span>
                  )}
                  {t.startedAt && t.endedAt && (
                    <span className="text-[#B0B8C1] shrink-0 hidden sm:inline">
                      {new Date(t.startedAt).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}
                      {" → "}
                      {new Date(t.endedAt).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  )}
                  {t.error && !hasResult && (
                    <span className="text-rose-500 truncate max-w-[150px] shrink-0">{t.error}</span>
                  )}
                </button>

                {/* Expanded detail */}
                {isOpen && hasResult && (
                  <div className="px-4 pb-3 pt-1 bg-[#FAFBFC] border-t border-[#F2F4F6] space-y-3">
                    {/* Meta row */}
                    <div className="flex flex-wrap gap-3 text-[11px]">
                      {t.result?.filename && (
                        <span><span className="text-[#8B95A1]">파일:</span> {t.result.filename}</span>
                      )}
                      {t.result?.company_name && (
                        <span><span className="text-[#8B95A1]">회사:</span> {t.result.company_name}</span>
                      )}
                      {t.result?.method && (
                        <span><span className="text-[#8B95A1]">방식:</span> {t.result.method}</span>
                      )}
                      {t.result?.pages != null && (
                        <span><span className="text-[#8B95A1]">페이지:</span> {t.result.pages}</span>
                      )}
                      {t.result?.text_chars != null && (
                        <span><span className="text-[#8B95A1]">텍스트:</span> {Number(t.result.text_chars).toLocaleString()}자</span>
                      )}
                    </div>

                    {(isResultCacheHit || isParseCacheHit) && (
                      <div className="rounded border border-blue-200 bg-blue-50 px-3 py-2">
                        <p className="text-[11px] font-medium text-blue-800">
                          {isResultCacheHit ? "이전 조건 검사 결과를 재사용했습니다." : "이전 문서 파싱 결과를 재사용했습니다."}
                        </p>
                        {(savedInputTokens > 0 || savedOutputTokens > 0) && (
                          <p className="mt-1 text-[11px] text-blue-700">
                            절감 토큰 추정치: 입력 {savedInputTokens.toLocaleString()} / 출력 {savedOutputTokens.toLocaleString()}
                          </p>
                        )}
                      </div>
                    )}

                    {(establishmentDate || revenueCandidates.length > 0) && (
                      <div className="rounded border border-[#E5E8EB] bg-white px-3 py-2">
                        <p className="text-[11px] font-medium text-[#8B95A1]">추출 팩트</p>
                        <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-[#4E5968]">
                          {establishmentDate && (
                            <span>
                              <span className="text-[#8B95A1]">설립/개업일:</span> {establishmentDate}
                            </span>
                          )}
                          {businessAgeYears != null && (
                            <span>
                              <span className="text-[#8B95A1]">업력:</span> {businessAgeYears.toFixed(2)}년
                            </span>
                          )}
                        </div>
                        {revenueCandidates.length > 0 && (
                          <div className="mt-2 space-y-1">
                            {revenueCandidates.map((candidate, index) => (
                              <div key={index} className="rounded bg-[#FAFBFC] px-2.5 py-2 text-[11px] text-[#4E5968]">
                                <span className="font-medium text-[#191F28]">
                                  {typeof candidate.display === "string" ? candidate.display : "-"}
                                </span>
                                {typeof candidate.year === "number" && (
                                  <span className="ml-1 text-[#8B95A1]">({candidate.year}년)</span>
                                )}
                                {typeof candidate.snippet === "string" && (
                                  <p className="mt-1 text-[#8B95A1]">{candidate.snippet}</p>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Error */}
                    {(t.error || t.result?.error) && (
                      <div className="rounded bg-rose-50 border border-rose-200 px-3 py-2">
                        <p className="text-[11px] text-rose-700 font-mono break-all">
                          {t.error || t.result?.error}
                        </p>
                      </div>
                    )}

                    {parseWarning && (
                      <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2">
                        <p className="text-[11px] font-medium text-amber-800">
                          모델 응답을 복구해서 결과를 생성했습니다.
                        </p>
                        <p className="mt-1 text-[11px] text-amber-700 leading-relaxed">
                          {parseWarning}
                        </p>
                        {rawResponse && (
                          <details className="mt-2">
                            <summary className="cursor-pointer text-[11px] font-medium text-amber-800">
                              원본 응답 일부 보기
                            </summary>
                            <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-all rounded border border-amber-200 bg-white/80 p-2 font-mono text-[10px] text-amber-900">
                              {rawResponse.slice(0, 2000)}
                              {rawResponse.length > 2000 ? "\n..." : ""}
                            </pre>
                          </details>
                        )}
                      </div>
                    )}

                    {/* Condition results */}
                    {t.result?.conditions && t.result.conditions.length > 0 && (
                      <div className="space-y-1.5">
                        <p className="text-[11px] font-medium text-[#8B95A1]">조건 검사 결과</p>
                        {t.result.conditions.map((cr, idx) => (
                          <div
                            key={idx}
                            className={cn(
                              "rounded-lg px-3 py-2 border text-[11px]",
                              cr.result
                                ? "bg-emerald-50 border-emerald-200"
                                : "bg-rose-50 border-rose-200",
                            )}
                          >
                            <div className="flex items-start gap-2">
                              <span className={cn(
                                "shrink-0 font-bold",
                                cr.result ? "text-emerald-600" : "text-rose-600",
                              )}>
                                {cr.result ? "✓" : "✗"}
                              </span>
                              <div className="min-w-0 flex-1">
                                {cr.condition && (
                                  <p className="font-medium text-[#191F28]">{cr.condition}</p>
                                )}
                                {cr.evidence && (
                                  <p className="mt-0.5 text-[#4E5968] leading-relaxed">{cr.evidence}</p>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-xs text-[#8B95A1] py-2">작업 정보가 없습니다.</p>
      )}
    </div>
  );
}
