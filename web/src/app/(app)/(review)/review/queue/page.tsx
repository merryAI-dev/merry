"use client";

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Eye,
  Loader2,
  PauseCircle,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

import { Badge, type BadgeProps } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { apiFetch } from "@/lib/apiClient";
import { cn } from "@/lib/cn";

type ReviewQueueReason =
  | "task_error"
  | "company_unrecognized"
  | "parse_warning"
  | "alias_correction"
  | "evidence_missing";

type ReviewQueueStatus =
  | "queued"
  | "in_review"
  | "resolved_correct"
  | "resolved_incorrect"
  | "resolved_ambiguous"
  | "suppressed";

type ReviewQueueItem = {
  queueId: string;
  jobId: string;
  taskId: string;
  filename: string;
  companyGroupName: string;
  companyGroupKey: string;
  jobTitle: string;
  policyText: string;
  queueReason: ReviewQueueReason;
  severity: "high" | "medium" | "low";
  status: ReviewQueueStatus;
  autoResult?: boolean;
  reviewedResult?: boolean;
  evidence: string;
  parseWarning: string;
  error: string;
  aliasFrom: string;
  reviewComment?: string;
  assignedTo?: string;
  createdAt: string;
  updatedAt: string;
  resolvedAt?: string;
};

type ReviewQueueResponse = {
  ok: boolean;
  items: ReviewQueueItem[];
  summary: Record<string, number>;
  syncedCandidates: number;
};

const STATUS_OPTIONS: Array<{ value: ReviewQueueStatus | "open" | "all"; label: string }> = [
  { value: "open", label: "열린 항목" },
  { value: "all", label: "전체" },
  { value: "queued", label: "대기" },
  { value: "in_review", label: "검토 중" },
  { value: "resolved_correct", label: "정답 확인" },
  { value: "resolved_incorrect", label: "오답 확인" },
  { value: "resolved_ambiguous", label: "애매함" },
  { value: "suppressed", label: "보류" },
];

const REASON_LABELS: Record<ReviewQueueReason, string> = {
  task_error: "실패/에러",
  company_unrecognized: "기업 미인식",
  parse_warning: "파싱 경고",
  alias_correction: "alias 보정",
  evidence_missing: "근거 부족",
};

const REASON_OPTIONS: Array<{ value: ReviewQueueReason | "all"; label: string }> = [
  { value: "all", label: "전체 사유" },
  { value: "task_error", label: REASON_LABELS.task_error },
  { value: "company_unrecognized", label: REASON_LABELS.company_unrecognized },
  { value: "parse_warning", label: REASON_LABELS.parse_warning },
  { value: "alias_correction", label: REASON_LABELS.alias_correction },
  { value: "evidence_missing", label: REASON_LABELS.evidence_missing },
];

function statusTone(status: ReviewQueueStatus): BadgeProps["tone"] {
  switch (status) {
    case "queued": return "warn";
    case "in_review": return "accent";
    case "resolved_correct": return "success";
    case "resolved_incorrect": return "danger";
    case "resolved_ambiguous": return "warn";
    case "suppressed": return "neutral";
    default: return "neutral";
  }
}

function statusLabel(status: ReviewQueueStatus): string {
  switch (status) {
    case "queued": return "대기";
    case "in_review": return "검토 중";
    case "resolved_correct": return "정답 확인";
    case "resolved_incorrect": return "오답 확인";
    case "resolved_ambiguous": return "애매함";
    case "suppressed": return "보류";
    default: return status;
  }
}

function severityTone(value: "high" | "medium" | "low"): BadgeProps["tone"] {
  switch (value) {
    case "high": return "danger";
    case "medium": return "warn";
    default: return "neutral";
  }
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "방금 전";
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

export default function ReviewQueuePage() {
  const [items, setItems] = React.useState<ReviewQueueItem[]>([]);
  const [summary, setSummary] = React.useState<Record<string, number>>({});
  const [loading, setLoading] = React.useState(true);
  const [refreshing, setRefreshing] = React.useState(false);
  const [statusFilter, setStatusFilter] = React.useState<ReviewQueueStatus | "open" | "all">("open");
  const [reasonFilter, setReasonFilter] = React.useState<ReviewQueueReason | "all">("all");
  const [search, setSearch] = React.useState("");
  const [busyId, setBusyId] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async (showLoader = false) => {
    if (showLoader) setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        status: statusFilter,
        reason: reasonFilter,
        limit: "120",
      });
      const data = await apiFetch<ReviewQueueResponse>(`/api/review-queue?${params}`);
      setItems(data.items || []);
      setSummary(data.summary || {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "FAILED");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [reasonFilter, statusFilter]);

  React.useEffect(() => {
    load(true);
  }, [load]);

  const filteredItems = React.useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) => {
      return [
        item.filename,
        item.companyGroupName,
        item.policyText,
        item.jobTitle,
        item.assignedTo,
      ].some((value) => String(value || "").toLowerCase().includes(q));
    });
  }, [items, search]);

  async function act(
    queueId: string,
    kind: "claim" | "correct" | "incorrect" | "ambiguous" | "suppress",
  ) {
    setBusyId(queueId);
    try {
      if (kind === "claim") {
        await apiFetch(`/api/review-queue/${queueId}/claim`, { method: "POST" });
      } else if (kind === "suppress") {
        await apiFetch(`/api/review-queue/${queueId}/suppress`, {
          method: "POST",
          body: JSON.stringify({ reviewComment: "임시 보류" }),
        });
      } else {
        const status = kind === "correct"
          ? "resolved_correct"
          : kind === "incorrect"
            ? "resolved_incorrect"
            : "resolved_ambiguous";
        await apiFetch(`/api/review-queue/${queueId}/resolve`, {
          method: "POST",
          body: JSON.stringify({
            status,
            reviewedResult: kind === "correct" ? true : kind === "incorrect" ? false : undefined,
          }),
        });
      }
      await load(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "FAILED");
    } finally {
      setBusyId(null);
    }
  }

  const openCount = (summary.queued ?? 0) + (summary.in_review ?? 0);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest text-[#8B95A1]">RALPH REVIEW</div>
          <h1 className="mt-1 text-2xl font-bold text-[#191F28]">검토 큐</h1>
          <p className="mt-1 text-sm text-[#8B95A1]">
            parse warning, 기업 미인식, alias 보정, 근거 부족 같은 항목만 사람이 검토합니다.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => load(false)} disabled={refreshing}>
          <RefreshCw className={cn("mr-1.5 h-4 w-4", refreshing && "animate-spin")} />
          새로고침
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={ShieldAlert} label="열린 항목" value={openCount} sub={`${summary.total ?? 0}개 중`} tone="danger" />
        <StatCard icon={Eye} label="검토 중" value={summary.in_review ?? 0} sub="claim된 항목" tone="accent" />
        <StatCard icon={Sparkles} label="alias 보정" value={summary.alias_correction ?? 0} sub="자동 보정 발생" tone="default" />
        <StatCard icon={AlertTriangle} label="파싱 경고" value={summary.parse_warning ?? 0} sub="응답 복구 필요" tone="warn" />
      </div>

      <Card className="flex flex-wrap items-center gap-3 p-3">
        <div className="min-w-[220px] flex-1">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="파일명, 기업명, 정책으로 검색"
            className="h-9 text-sm"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as ReviewQueueStatus | "open" | "all")}
          className="h-9 rounded-lg border border-[#E5E8EB] bg-white px-3 text-sm text-[#4E5968]"
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
        <select
          value={reasonFilter}
          onChange={(e) => setReasonFilter(e.target.value as ReviewQueueReason | "all")}
          className="h-9 rounded-lg border border-[#E5E8EB] bg-white px-3 text-sm text-[#4E5968]"
        >
          {REASON_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </Card>

      {error && (
        <Card className="border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {error}
        </Card>
      )}

      {loading ? (
        <Card className="flex items-center gap-3 p-6 text-sm text-[#8B95A1]">
          <Loader2 className="h-4 w-4 animate-spin" />
          검토 큐를 불러오는 중입니다.
        </Card>
      ) : filteredItems.length === 0 ? (
        <Card className="p-8 text-center text-sm text-[#8B95A1]">
          현재 필터 기준으로 검토할 항목이 없습니다.
        </Card>
      ) : (
        <div className="space-y-3">
          {filteredItems.map((item) => {
            const busy = busyId === item.queueId;
            const open = item.status === "queued" || item.status === "in_review";
            return (
              <Card key={item.queueId} className="space-y-4 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="truncate text-sm font-semibold text-[#191F28]">{item.filename}</h2>
                      <Badge tone={statusTone(item.status)}>{statusLabel(item.status)}</Badge>
                      <Badge tone={severityTone(item.severity)}>{item.severity.toUpperCase()}</Badge>
                      <Badge tone="neutral">{REASON_LABELS[item.queueReason]}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-[#8B95A1]">
                      {item.jobTitle} · {item.companyGroupName || "기업 미인식"} · {relativeTime(item.createdAt)}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {item.assignedTo && (
                      <span className="text-xs text-[#8B95A1]">담당 {item.assignedTo}</span>
                    )}
                    {open && (
                      <Button variant="secondary" size="sm" onClick={() => act(item.queueId, "claim")} disabled={busy}>
                        {busy ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Clock3 className="mr-1.5 h-3.5 w-3.5" />}
                        Claim
                      </Button>
                    )}
                  </div>
                </div>

                <div className="grid gap-3 lg:grid-cols-[1.4fr_1fr]">
                  <div className="space-y-2 rounded-xl border border-[#E5E8EB] bg-[#FCFCFD] p-3">
                    <Row label="정책" value={item.policyText || "-"} />
                    <Row label="자동 판정" value={typeof item.autoResult === "boolean" ? (item.autoResult ? "충족" : "미충족") : "-"} />
                    <Row label="근거" value={item.evidence || "-"} />
                    <Row label="파싱 경고" value={item.parseWarning || "-"} />
                    <Row label="에러" value={item.error || "-"} />
                    <Row label="alias 보정" value={item.aliasFrom ? `${item.aliasFrom} -> ${item.companyGroupName || item.companyGroupKey}` : "-"} />
                  </div>
                  <div className="space-y-2 rounded-xl border border-[#E5E8EB] bg-white p-3">
                    <Row label="Queue ID" value={item.queueId} mono />
                    <Row label="Job ID" value={item.jobId} mono />
                    <Row label="Task ID" value={item.taskId} mono />
                    <Row label="기업 그룹" value={item.companyGroupName || item.companyGroupKey || "-"} />
                    <Row label="코멘트" value={item.reviewComment || "-"} />
                  </div>
                </div>

                {open && (
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" onClick={() => act(item.queueId, "correct")} disabled={busy}>
                      <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />
                      정답 확인
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => act(item.queueId, "incorrect")} disabled={busy}>
                      <AlertTriangle className="mr-1.5 h-3.5 w-3.5" />
                      오답 확인
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => act(item.queueId, "ambiguous")} disabled={busy}>
                      <Eye className="mr-1.5 h-3.5 w-3.5" />
                      애매함
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => act(item.queueId, "suppress")} disabled={busy}>
                      <PauseCircle className="mr-1.5 h-3.5 w-3.5" />
                      보류
                    </Button>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  tone = "default",
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
  sub?: string;
  tone?: "default" | "danger" | "accent" | "warn";
}) {
  const toneClass = {
    default: "bg-[#F2F4F6] text-[#4E5968]",
    danger: "bg-rose-50 text-rose-600",
    accent: "bg-[#EBF3FF] text-[#3182F6]",
    warn: "bg-amber-50 text-amber-700",
  }[tone];

  return (
    <Card className="flex items-start gap-3 p-4">
      <div className={cn("rounded-xl p-2.5", toneClass)}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-xs text-[#8B95A1]">{label}</p>
        <p className="mt-0.5 text-xl font-bold text-[#191F28]">{value.toLocaleString()}</p>
        {sub && <p className="mt-0.5 text-[11px] text-[#B0B8C1]">{sub}</p>}
      </div>
    </Card>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[92px_1fr]">
      <span className="text-[11px] text-[#8B95A1]">{label}</span>
      <span className={cn("text-sm text-[#191F28]", mono && "font-mono text-xs")}>{value}</span>
    </div>
  );
}
