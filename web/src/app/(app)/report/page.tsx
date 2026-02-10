"use client";

import Link from "next/link";
import * as React from "react";
import { RefreshCw, Search } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
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

  React.useEffect(() => {
    load();
  }, []);

  const filtered = React.useMemo(() => {
    const needle = q.trim().toLowerCase();
    const list = (sessions || []).filter((s) => {
      if (!needle) return true;
      const hay = `${s.title || ""} ${s.companyName || ""} ${s.fundName || ""} ${s.author || ""}`.toLowerCase();
      return hay.includes(needle);
    });
    list.sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""));
    return list;
  }, [sessions, q]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-[color:var(--muted)]">Investment Report</div>
          <h1 className="mt-1 font-[family-name:var(--font-display)] text-3xl tracking-tight text-[color:var(--ink)]">
            투자심사 세션
          </h1>
          <div className="mt-2 text-sm text-[color:var(--muted)]">
            세션 URL로 공유해 여러 명이 동시에 초안을 만들고, 드래프트 리뷰로 이어갑니다.
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-black/50" />
            <Input
              className="w-[18rem] pl-9"
              placeholder="세션 검색 (제목/기업/작성자)"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <Button variant="secondary" onClick={load} disabled={busy}>
            <RefreshCw className="h-4 w-4" />
            새로고침
          </Button>
          <Link href="/report/new" className="inline-flex">
            <Button variant="primary">새 보고서</Button>
          </Link>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-900">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {busy && !filtered.length ? (
          Array.from({ length: 6 }).map((_, idx) => (
            <div key={idx} className="m-card animate-pulse rounded-3xl p-5" aria-label="loading">
              <div className="h-2 w-24 rounded-full bg-black/10" />
              <div className="mt-4 h-6 w-2/3 rounded-xl bg-black/10" />
              <div className="mt-3 h-4 w-1/2 rounded-xl bg-black/10" />
              <div className="mt-5 h-16 rounded-2xl bg-black/5" />
            </div>
          ))
        ) : null}

        {filtered.map((s) => (
          <Link key={s.sessionId} href={`/report/${s.slug}`} className="block">
            <Card variant="strong" className="group relative overflow-hidden rounded-3xl p-5 transition-colors hover:bg-white/95">
              <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[color:var(--accent)] via-[color:color-mix(in_oklab,var(--accent),white_24%)] to-[color:var(--accent-2)]" />

              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold text-[color:var(--ink)]">{s.title}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[color:var(--muted)]">
                    <span className="font-mono">{s.sessionId}</span>
                    {s.createdAt ? (
                      <>
                        <span>·</span>
                        <span>{s.createdAt.slice(0, 16).replace("T", " ")}</span>
                      </>
                    ) : null}
                  </div>
                </div>
                <Badge tone="accent">열기</Badge>
              </div>

              <div className="mt-4 grid gap-2 text-xs text-[color:var(--muted)]">
                <div>기업: <span className="text-[color:var(--ink)]">{s.companyName || "—"}</span></div>
                <div>작성자: <span className="text-[color:var(--ink)]">{s.author || "—"}</span></div>
                <div>작성일: <span className="text-[color:var(--ink)]">{s.reportDate || "—"}</span></div>
                <div>펀드: <span className="text-[color:var(--ink)]">{s.fundName || "—"}</span></div>
              </div>

              <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-[color:color-mix(in_oklab,var(--accent),white_70%)] blur-2xl opacity-0 transition-opacity group-hover:opacity-100" />
            </Card>
          </Link>
        ))}
      </div>

      {!busy && !error && !filtered.length ? (
        <div className="text-sm text-[color:var(--muted)]">
          표시할 세션이 없습니다. 새 보고서를 만들어 시작하세요.
        </div>
      ) : null}
    </div>
  );
}

