"use client";

import Link from "next/link";
import * as React from "react";
import { Plus, RefreshCw, Search } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

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

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.error || "FAILED");
  return json as T;
}

function SessionCard({ s }: { s: ReportSession }) {
  return (
    <Link href={`/report/${s.slug}`} className="block group">
      <div
        className="rounded-2xl bg-white p-5 transition-all hover:shadow-md"
        style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px #E5E8EB" }}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="truncate text-[14px] font-bold text-[#191F28]">{s.title}</div>
            <div className="mt-1 text-[11.5px] text-[#8B95A1]">
              {s.createdAt ? s.createdAt.slice(0, 16).replace("T", " ") : "—"}
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
  const [error, setError] = React.useState<string | null>(null);
  const [q, setQ] = React.useState("");

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetchJson<{ sessions: ReportSession[] }>("/api/report/sessions");
      setSessions(res.sessions || []);
    } catch {
      setError("세션을 불러오지 못했습니다. 환경변수/인증을 확인하세요.");
      setSessions([]);
    } finally {
      setBusy(false);
    }
  }

  React.useEffect(() => { load(); }, []);

  const filtered = React.useMemo(() => {
    const needle = q.trim().toLowerCase();
    const list = sessions.filter((s) => {
      if (!needle) return true;
      return `${s.title} ${s.companyName || ""} ${s.fundName || ""} ${s.author || ""}`.toLowerCase().includes(needle);
    });
    list.sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""));
    return list;
  }, [sessions, q]);

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
          <Button variant="secondary" size="sm" onClick={load} disabled={busy}>
            <RefreshCw className="h-3.5 w-3.5" />
            새로고침
          </Button>
          <Link href="/report/new">
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
        {busy && !filtered.length
          ? Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
          : filtered.map((s) => <SessionCard key={s.sessionId} s={s} />)
        }
      </div>

      {!busy && !error && !filtered.length && (
        <div className="rounded-2xl bg-white py-16 text-center" style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px #E5E8EB" }}>
          <div className="text-[15px] font-semibold text-[#191F28]">세션이 없어요</div>
          <div className="mt-1 text-[13px] text-[#8B95A1]">새 보고서를 만들어 시작하세요.</div>
          <div className="mt-4">
            <Link href="/report/new">
              <Button variant="primary" size="sm">
                <Plus className="h-3.5 w-3.5" />
                새 보고서
              </Button>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
