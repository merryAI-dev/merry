"use client";

import * as React from "react";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  AlertTriangle,
  ArrowDownToLine,
  ArrowUpFromLine,
  Clock,
  Cpu,
  Loader2,
  RefreshCw,
  Zap,
} from "lucide-react";

import { Badge, type BadgeProps } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { apiFetch } from "@/lib/apiClient";
import { cn } from "@/lib/cn";

/* ── Types ── */

type SqsStats = {
  messagesVisible: number;
  messagesInFlight: number;
  messagesDelayed: number;
};

type RunningJob = {
  teamId: string;
  jobId: string;
  status: string;
  title: string;
  type: string;
  createdAt: string;
  fanout: boolean;
  totalTasks: number;
  processedCount: number;
  failedCount: number;
  fanoutStatus: string | null;
};

type RecentStats = {
  total: number;
  failed: number;
  failureRate: number;
  totalTokens: number;
};

type AdminData = {
  ok: boolean;
  error?: string;
  sqs: SqsStats;
  runningJobs: number;
  runningJobDetails: RunningJob[];
  recentStats: RecentStats;
  teamId: string;
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
};

function fanoutStatusLabel(s: string | null): string {
  switch (s) {
    case "splitting": return "분할 중";
    case "running": return "실행 중";
    case "assembling": return "취합 중";
    case "succeeded": return "완료";
    case "failed": return "실패";
    default: return s ?? "-";
  }
}

function fanoutStatusTone(s: string | null): BadgeProps["tone"] {
  switch (s) {
    case "succeeded": return "success";
    case "failed": return "danger";
    case "running": return "accent";
    case "assembling": return "warn";
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
  const days = Math.floor(hours / 24);
  return `${days}일 전`;
}

function formatTokens(n: number): string {
  if (n < 1_000) return String(n);
  if (n < 1_000_000) return `${(n / 1_000).toFixed(1)}K`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

function estimateCost(totalTokens: number): string {
  // Rough average: mix of input ($0.0008/1K) and output ($0.0032/1K)
  // Assume ~80% input, 20% output for typical workload
  const inputTokens = totalTokens * 0.8;
  const outputTokens = totalTokens * 0.2;
  const cost = (inputTokens / 1000) * 0.0008 + (outputTokens / 1000) * 0.0032;
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

/* ── Stat Card ── */

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  tone = "default",
}: {
  icon: LucideIcon;
  label: string;
  value: string | number;
  sub?: string;
  tone?: "default" | "danger" | "accent" | "success";
}) {
  const toneMap = {
    default: { bg: "bg-[#F2F4F6]", text: "text-[#4E5968]" },
    danger: { bg: "bg-rose-50", text: "text-rose-600" },
    accent: { bg: "bg-[#EBF3FF]", text: "text-[#3182F6]" },
    success: { bg: "bg-emerald-50", text: "text-emerald-600" },
  };
  const t = toneMap[tone];

  return (
    <Card className="flex items-start gap-3 p-4">
      <div className={cn("rounded-xl p-2.5", t.bg)}>
        <Icon className={cn("h-5 w-5", t.text)} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs text-[#8B95A1]">{label}</p>
        <p className={cn("mt-0.5 text-xl font-bold tabular-nums", t.text)}>
          {typeof value === "number" ? value.toLocaleString() : value}
        </p>
        {sub && <p className="mt-0.5 text-[11px] text-[#B0B8C1]">{sub}</p>}
      </div>
    </Card>
  );
}

/* ── Page ── */

const REFRESH_INTERVAL = 10_000; // 10 seconds

export default function AdminPage() {
  const [data, setData] = React.useState<AdminData | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = React.useState<Date | null>(null);

  const fetchData = React.useCallback(async (showLoader = false) => {
    if (showLoader) setLoading(true);
    setError(null);
    try {
      const json = await apiFetch<AdminData & { ok: boolean }>("/api/admin/status");
      setData(json as AdminData);
      setLastUpdated(new Date());
    } catch (e) {
      if (e instanceof Error && e.message === "FORBIDDEN") {
        setError("접근 권한이 없습니다. 관리자 팀에 속해 있는지 확인해주세요.");
      } else {
        setError(e instanceof Error ? e.message : "데이터를 불러올 수 없습니다.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load + auto-refresh
  React.useEffect(() => {
    fetchData(true);
    const timer = setInterval(() => fetchData(false), REFRESH_INTERVAL);
    return () => clearInterval(timer);
  }, [fetchData]);

  const sqsTotal = data
    ? data.sqs.messagesVisible + data.sqs.messagesInFlight + data.sqs.messagesDelayed
    : 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#191F28]">관리자 대시보드</h1>
          <p className="mt-1 text-sm text-[#8B95A1]">
            시스템 상태, 큐 깊이, 실행 중인 작업을 실시간으로 모니터링합니다.
            {lastUpdated && (
              <span className="ml-2 text-[#B0B8C1]">
                마지막 업데이트: {lastUpdated.toLocaleTimeString("ko-KR")}
              </span>
            )}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => fetchData(true)}
          disabled={loading}
        >
          <RefreshCw className={cn("mr-1.5 h-4 w-4", loading && "animate-spin")} />
          새로고침
        </Button>
      </div>

      {/* Error */}
      {error && (
        <Card className="border-rose-200 bg-rose-50 p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0" />
            <p className="text-sm text-rose-700">{error}</p>
          </div>
        </Card>
      )}

      {/* Loading */}
      {loading && !data && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-[#3182F6]" />
          <span className="ml-2 text-sm text-[#8B95A1]">불러오는 중...</span>
        </div>
      )}

      {data && (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard
              icon={ArrowDownToLine}
              label="SQS 대기 메시지"
              value={data.sqs.messagesVisible}
              sub={sqsTotal > 0 ? `총 ${sqsTotal.toLocaleString()}건` : "큐 비어있음"}
              tone={data.sqs.messagesVisible > 50 ? "danger" : data.sqs.messagesVisible > 0 ? "accent" : "default"}
            />
            <StatCard
              icon={Cpu}
              label="처리 중 (In-Flight)"
              value={data.sqs.messagesInFlight}
              sub={data.sqs.messagesDelayed > 0 ? `지연: ${data.sqs.messagesDelayed}건` : undefined}
              tone={data.sqs.messagesInFlight > 0 ? "accent" : "default"}
            />
            <StatCard
              icon={Activity}
              label="실행 중인 Job"
              value={data.runningJobs}
              tone={data.runningJobs > 0 ? "accent" : "success"}
            />
            <StatCard
              icon={AlertTriangle}
              label="최근 실패율"
              value={`${data.recentStats.failureRate}%`}
              sub={`${data.recentStats.failed}/${data.recentStats.total}건 실패`}
              tone={data.recentStats.failureRate > 20 ? "danger" : data.recentStats.failureRate > 0 ? "default" : "success"}
            />
          </div>

          {/* Token Usage + Cost */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <StatCard
              icon={Zap}
              label="최근 총 토큰 사용량"
              value={formatTokens(data.recentStats.totalTokens)}
              sub={`최근 ${data.recentStats.total}건 기준`}
            />
            <StatCard
              icon={Clock}
              label="예상 API 비용"
              value={estimateCost(data.recentStats.totalTokens)}
              sub="Nova Pro 기준 추정치"
              tone="accent"
            />
          </div>

          {/* SQS Detail Bar */}
          {sqsTotal > 0 && (
            <Card className="p-4">
              <p className="text-xs font-medium text-[#8B95A1] mb-3">SQS 큐 상세</p>
              <div className="flex h-4 rounded-full overflow-hidden bg-[#F2F4F6]">
                {data.sqs.messagesInFlight > 0 && (
                  <div
                    className="bg-[#3182F6] transition-all"
                    style={{ width: `${(data.sqs.messagesInFlight / sqsTotal) * 100}%` }}
                    title={`처리 중: ${data.sqs.messagesInFlight}`}
                  />
                )}
                {data.sqs.messagesVisible > 0 && (
                  <div
                    className="bg-amber-400 transition-all"
                    style={{ width: `${(data.sqs.messagesVisible / sqsTotal) * 100}%` }}
                    title={`대기: ${data.sqs.messagesVisible}`}
                  />
                )}
                {data.sqs.messagesDelayed > 0 && (
                  <div
                    className="bg-[#B0B8C1] transition-all"
                    style={{ width: `${(data.sqs.messagesDelayed / sqsTotal) * 100}%` }}
                    title={`지연: ${data.sqs.messagesDelayed}`}
                  />
                )}
              </div>
              <div className="mt-2 flex gap-4 text-xs">
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-[#3182F6]" />
                  처리 중 ({data.sqs.messagesInFlight})
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                  대기 ({data.sqs.messagesVisible})
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-[#B0B8C1]" />
                  지연 ({data.sqs.messagesDelayed})
                </span>
              </div>
            </Card>
          )}

          {/* Running Jobs Table */}
          <Card className="overflow-hidden p-0">
            <div className="px-5 py-4 border-b border-[#F2F4F6]">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-[#191F28]">실행 중인 작업</p>
                  <p className="mt-0.5 text-xs text-[#8B95A1]">
                    전체 팀의 진행 중인 작업 목록
                  </p>
                </div>
                <Badge tone={data.runningJobs > 0 ? "accent" : "neutral"}>
                  {data.runningJobs}건
                </Badge>
              </div>
            </div>

            {data.runningJobDetails.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12">
                <Activity className="h-8 w-8 text-[#D1D6DB]" />
                <p className="mt-2 text-sm text-[#8B95A1]">현재 실행 중인 작업이 없습니다.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-[#F9FAFB] border-b border-[#E5E8EB]">
                    <tr>
                      <th className="px-4 py-2.5 text-left text-[#8B95A1] font-medium">팀</th>
                      <th className="px-4 py-2.5 text-left text-[#8B95A1] font-medium">작업</th>
                      <th className="px-4 py-2.5 text-left text-[#8B95A1] font-medium">유형</th>
                      <th className="px-4 py-2.5 text-left text-[#8B95A1] font-medium">상태</th>
                      <th className="px-4 py-2.5 text-left text-[#8B95A1] font-medium">진행률</th>
                      <th className="px-4 py-2.5 text-left text-[#8B95A1] font-medium">시작</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#F2F4F6]">
                    {data.runningJobDetails.map((job) => {
                      const pct = job.fanout && job.totalTasks > 0
                        ? Math.round(((job.processedCount + job.failedCount) / job.totalTasks) * 100)
                        : null;
                      return (
                        <tr key={`${job.teamId}-${job.jobId}`} className="hover:bg-[#FAFBFC]">
                          <td className="px-4 py-2.5 font-mono text-[#4E5968] max-w-[100px] truncate">
                            {job.teamId}
                          </td>
                          <td className="px-4 py-2.5">
                            <p className="text-[#191F28] font-medium truncate max-w-[200px]">
                              {job.title || job.jobId}
                            </p>
                            <p className="font-mono text-[#B0B8C1] text-[10px]">{job.jobId}</p>
                          </td>
                          <td className="px-4 py-2.5 text-[#4E5968]">
                            {JOB_TYPE_LABELS[job.type] || job.type}
                          </td>
                          <td className="px-4 py-2.5">
                            {job.fanout ? (
                              <Badge tone={fanoutStatusTone(job.fanoutStatus)}>
                                {fanoutStatusLabel(job.fanoutStatus)}
                              </Badge>
                            ) : (
                              <Badge tone="accent">{job.status}</Badge>
                            )}
                          </td>
                          <td className="px-4 py-2.5">
                            {job.fanout && job.totalTasks > 0 ? (
                              <div className="flex items-center gap-2 min-w-[120px]">
                                <div className="flex-1 h-1.5 rounded-full bg-[#E5E8EB] overflow-hidden">
                                  <div
                                    className={cn(
                                      "h-full rounded-full transition-all",
                                      job.failedCount > 0 ? "bg-amber-400" : "bg-[#3182F6]",
                                    )}
                                    style={{ width: `${pct}%` }}
                                  />
                                </div>
                                <span className="text-[#4E5968] tabular-nums whitespace-nowrap">
                                  {job.processedCount}/{job.totalTasks}
                                  {job.failedCount > 0 && (
                                    <span className="text-rose-500 ml-1">({job.failedCount}err)</span>
                                  )}
                                </span>
                              </div>
                            ) : (
                              <span className="text-[#B0B8C1]">-</span>
                            )}
                          </td>
                          <td className="px-4 py-2.5 text-[#8B95A1] whitespace-nowrap">
                            {relativeTime(job.createdAt)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {/* Recent Stats Summary */}
          <Card className="p-4">
            <p className="text-xs font-medium text-[#8B95A1] mb-3">
              최근 작업 통계 (최근 {data.recentStats.total}건, 팀: {data.teamId})
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="rounded-xl bg-[#F9FAFB] px-3 py-2.5 border border-[#E5E8EB]">
                <p className="text-[11px] text-[#8B95A1]">총 작업</p>
                <p className="text-lg font-bold text-[#191F28] tabular-nums">
                  {data.recentStats.total}
                </p>
              </div>
              <div className={cn(
                "rounded-xl px-3 py-2.5 border",
                data.recentStats.failed > 0
                  ? "bg-rose-50 border-rose-200"
                  : "bg-[#F9FAFB] border-[#E5E8EB]",
              )}>
                <p className="text-[11px] text-[#8B95A1]">실패</p>
                <p className={cn(
                  "text-lg font-bold tabular-nums",
                  data.recentStats.failed > 0 ? "text-rose-600" : "text-[#191F28]",
                )}>
                  {data.recentStats.failed}
                </p>
              </div>
              <div className={cn(
                "rounded-xl px-3 py-2.5 border",
                data.recentStats.failureRate > 20
                  ? "bg-rose-50 border-rose-200"
                  : data.recentStats.failureRate > 0
                    ? "bg-amber-50 border-amber-200"
                    : "bg-emerald-50 border-emerald-200",
              )}>
                <p className="text-[11px] text-[#8B95A1]">실패율</p>
                <p className={cn(
                  "text-lg font-bold tabular-nums",
                  data.recentStats.failureRate > 20
                    ? "text-rose-600"
                    : data.recentStats.failureRate > 0
                      ? "text-amber-600"
                      : "text-emerald-600",
                )}>
                  {data.recentStats.failureRate}%
                </p>
              </div>
              <div className="rounded-xl bg-[#EBF3FF] px-3 py-2.5 border border-[#C0D8FF]">
                <p className="text-[11px] text-[#8B95A1]">총 토큰</p>
                <p className="text-lg font-bold text-[#3182F6] tabular-nums">
                  {formatTokens(data.recentStats.totalTokens)}
                </p>
              </div>
            </div>
          </Card>

          {/* Auto-refresh indicator */}
          <div className="flex items-center justify-center gap-1.5 text-[11px] text-[#B0B8C1]">
            <ArrowUpFromLine className="h-3 w-3" />
            <span>10초마다 자동 갱신</span>
          </div>
        </>
      )}
    </div>
  );
}
