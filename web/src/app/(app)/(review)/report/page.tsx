"use client";

import Link from "next/link";
import * as React from "react";
import { Files, Plus, RefreshCw, Search } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { apiFetch } from "@/lib/apiClient";

type ReportSession = {
  sessionId: string;
  slug: string;
  title: string;
  createdAt?: string;
  fundName?: string;
  companyName?: string;
  reportDate?: string;
  author?: string;
};

const REVIEW_HOME_PAGE_SIZE = 30;

function SessionCard({ s }: { s: ReportSession }) {
  return (
    <Link href={`/review/${s.slug}`} className="block group">
      <div
        className="rounded-2xl bg-white p-5 transition-all hover:shadow-md"
        style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px #E5E8EB" }}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="truncate text-[14px] font-bold text-[#191F28]">{s.title}</div>
            <div className="mt-1 text-[11.5px] text-[#8B95A1]">
              {s.createdAt
                ? new Date(s.createdAt).toLocaleString("ko-KR", {
                    timeZone: "Asia/Seoul",
                    year: "numeric",
                    month: "2-digit",
                    day: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "—"}
            </div>
          </div>
          <Badge tone="accent">열기</Badge>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1 text-[12px]">
          <div>
            <span className="text-[#8B95A1]">기업 </span>
            <span className="font-medium text-[#191F28]">{s.companyName || "—"}</span>
          </div>
          <div>
            <span className="text-[#8B95A1]">작성자 </span>
            <span className="font-medium text-[#191F28]">{s.author || "—"}</span>
          </div>
          <div>
            <span className="text-[#8B95A1]">작성일 </span>
            <span className="font-medium text-[#191F28]">{s.reportDate || "—"}</span>
          </div>
          <div>
            <span className="text-[#8B95A1]">펀드 </span>
            <span className="font-medium text-[#191F28]">{s.fundName || "—"}</span>
          </div>
        </div>
      </div>
    </Link>
  );
}

function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-2xl bg-white p-5" style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px #E5E8EB" }}>
      <div className="h-4 w-2/3 rounded-lg bg-[#F2F4F6]" />
      <div className="mt-2 h-3 w-1/3 rounded-lg bg-[#F2F4F6]" />
      <div className="mt-4 grid grid-cols-2 gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-3 rounded-lg bg-[#F2F4F6]" />
        ))}
      </div>
    </div>
  );
}

export default function ReportSessionsPage() {
  const [sessions, setSessions] = React.useState<ReportSession[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [loadingMore, setLoadingMore] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [q, setQ] = React.useState("");
  const [total, setTotal] = React.useState(0);
  const [hasMore, setHasMore] = React.useState(false);

  const load = React.useCallback(async (nextOffset = 0, append = false) => {
    if (append) setLoadingMore(true);
    else setBusy(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        limit: String(REVIEW_HOME_PAGE_SIZE),
        offset: String(nextOffset),
        q,
      });
      const res = await apiFetch<{
        sessions?: ReportSession[];
        total?: number;
        offset?: number;
        hasMore?: boolean;
      }>(`/api/review/sessions?${params.toString()}`);
      const nextSessions = res.sessions || [];
      setSessions((prev) => (append ? [...prev, ...nextSessions] : nextSessions));
      setTotal(res.total ?? nextSessions.length);
      setHasMore(res.hasMore ?? false);
    } catch {
      setError("세션을 불러오지 못했습니다. 환경변수/인증을 확인하세요.");
      if (!append) {
        setSessions([]);
        setTotal(0);
        setHasMore(false);
      }
    } finally {
      setBusy(false);
      setLoadingMore(false);
    }
  }, [q]);

  React.useEffect(() => {
    load(0, false);
  }, [load]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-[12px] font-semibold uppercase tracking-widest text-[#8B95A1]">
            Investment Report
          </div>
          <h1 className="mt-1 text-2xl font-black tracking-tight text-[#191F28]">투자심사 세션</h1>
          <div className="mt-1 text-[13px] text-[#8B95A1]">
            세션 URL로 공유해 여러 명이 함께 초안을 만들고 드래프트로 이어갑니다.
          </div>
          <div className="mt-2 text-[12px] font-medium text-[#8B95A1]">
            {total.toLocaleString()}개 세션
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#B0B8C1]" />
            <Input
              className="w-64 pl-9"
              placeholder="세션 검색"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <Button variant="secondary" size="sm" onClick={() => load(0, false)} disabled={busy}>
            <RefreshCw className="h-3.5 w-3.5" />
            새로고침
          </Button>
          <Link href="/documents">
            <Button variant="secondary" size="sm">
              <Files className="h-3.5 w-3.5" />
              문서 추출
            </Button>
          </Link>
          <Link href="/review/new">
            <Button variant="primary" size="sm">
              <Plus className="h-3.5 w-3.5" />
              새 보고서
            </Button>
          </Link>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {busy && !sessions.length
          ? Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
          : sessions.map((s) => <SessionCard key={s.sessionId} s={s} />)
        }
      </div>

      {!busy && !error && !sessions.length && (
        <div className="rounded-2xl bg-white py-16 text-center" style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px #E5E8EB" }}>
          <div className="text-[15px] font-semibold text-[#191F28]">세션이 없어요</div>
          <div className="mt-1 text-[13px] text-[#8B95A1]">새 보고서를 만들어 시작하세요.</div>
          <div className="mt-4 flex items-center justify-center gap-2">
            <Link href="/documents">
              <Button variant="secondary" size="sm">
                <Files className="h-3.5 w-3.5" />
                문서 추출부터
              </Button>
            </Link>
            <Link href="/review/new">
              <Button variant="primary" size="sm">
                <Plus className="h-3.5 w-3.5" />
                새 보고서
              </Button>
            </Link>
          </div>
        </div>
      )}

      {!busy && hasMore && (
        <div className="flex justify-center">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => load(sessions.length, true)}
            disabled={loadingMore}
          >
            <RefreshCw className={loadingMore ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} />
            더 보기
          </Button>
        </div>
      )}
    </div>
  );
}
