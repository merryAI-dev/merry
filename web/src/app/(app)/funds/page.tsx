"use client";

import Link from "next/link";
import * as React from "react";
import { RefreshCw, Search } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import type { FundSummary } from "@/lib/funds";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.error || "FAILED");
  return json as T;
}

function fmtCompact(n?: number) {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("ko-KR", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

function fmtMultiple(n?: number) {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return `${n.toFixed(2)}x`;
}

function fmtPct(n?: number) {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return `${n.toFixed(1)}%`;
}

export default function FundsPage() {
  const [funds, setFunds] = React.useState<FundSummary[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [q, setQ] = React.useState("");

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetchJson<{ funds: FundSummary[] }>("/api/funds");
      setFunds(res.funds || []);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "FAILED";
      if (msg === "AIRTABLE_NOT_CONFIGURED") {
        setError("Airtable 환경변수(AIRTABLE_API_TOKEN / AIRTABLE_BASE_ID)를 설정해야 합니다.");
      } else {
        setError("펀드 목록을 불러오지 못했습니다. Airtable 연결/권한을 확인하세요.");
      }
    } finally {
      setBusy(false);
    }
  }

  React.useEffect(() => {
    load();
  }, []);

  const filtered = React.useMemo(() => {
    const needle = q.trim().toLowerCase();
    const list = (funds || []).filter((f) => {
      if (!needle) return true;
      const hay = `${f.name || ""} ${f.vintage || ""}`.toLowerCase();
      return hay.includes(needle);
    });
    list.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    return list;
  }, [funds, q]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-[color:var(--muted)]">Fund Intelligence</div>
          <h1 className="mt-1 font-[family-name:var(--font-display)] text-3xl tracking-tight text-[color:var(--ink)]">
            펀드
          </h1>
          <div className="mt-2 text-sm text-[color:var(--muted)]">
            Airtable에서 펀드 메타데이터를 가져와 KPI와 성과 추이를 한 눈에 봅니다.
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-black/50" />
            <Input
              className="w-[18rem] pl-9"
              placeholder="펀드 검색 (이름/빈티지)"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <Button variant="secondary" onClick={load} disabled={busy}>
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

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {busy && !filtered.length ? (
          Array.from({ length: 6 }).map((_, idx) => (
            <div
              key={idx}
              className="m-card animate-pulse rounded-3xl p-5"
              aria-label="loading"
            >
              <div className="h-2 w-20 rounded-full bg-black/10" />
              <div className="mt-4 h-6 w-2/3 rounded-xl bg-black/10" />
              <div className="mt-3 h-4 w-1/2 rounded-xl bg-black/10" />
              <div className="mt-5 h-20 rounded-2xl bg-black/5" />
            </div>
          ))
        ) : null}

        {filtered.map((f) => (
          <Link key={f.fundId} href={`/funds/${f.fundId}`} className="block">
            <Card
              variant="strong"
              className="group relative overflow-hidden rounded-3xl p-5 transition-colors hover:bg-white/95"
            >
              <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[color:var(--accent)] via-[color:color-mix(in_oklab,var(--accent),white_24%)] to-[color:var(--accent-2)]" />

              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold text-[color:var(--ink)]">
                    {f.name}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[color:var(--muted)]">
                    {f.vintage ? <span>Vintage {f.vintage}</span> : <span>Vintage —</span>}
                    <span>·</span>
                    <span className="font-mono">{f.fundId}</span>
                  </div>
                </div>
                <Badge tone="accent">상세</Badge>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-2">
                <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
                  <div className="text-[11px] font-medium text-[color:var(--muted)]">TVPI</div>
                  <div className="mt-1 font-mono text-sm text-[color:var(--ink)]">{fmtMultiple(f.tvpi)}</div>
                </div>
                <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
                  <div className="text-[11px] font-medium text-[color:var(--muted)]">DPI</div>
                  <div className="mt-1 font-mono text-sm text-[color:var(--ink)]">{fmtMultiple(f.dpi)}</div>
                </div>
                <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
                  <div className="text-[11px] font-medium text-[color:var(--muted)]">IRR</div>
                  <div className="mt-1 font-mono text-sm text-[color:var(--ink)]">{fmtPct(f.irr)}</div>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-4 gap-2 text-xs">
                <div className="rounded-2xl bg-black/[0.03] p-3">
                  <div className="font-medium text-[color:var(--muted)]">Committed</div>
                  <div className="mt-1 font-mono text-[color:var(--ink)]">{fmtCompact(f.committed)}</div>
                </div>
                <div className="rounded-2xl bg-black/[0.03] p-3">
                  <div className="font-medium text-[color:var(--muted)]">Called</div>
                  <div className="mt-1 font-mono text-[color:var(--ink)]">{fmtCompact(f.called)}</div>
                </div>
                <div className="rounded-2xl bg-black/[0.03] p-3">
                  <div className="font-medium text-[color:var(--muted)]">Dist.</div>
                  <div className="mt-1 font-mono text-[color:var(--ink)]">{fmtCompact(f.distributed)}</div>
                </div>
                <div className="rounded-2xl bg-black/[0.03] p-3">
                  <div className="font-medium text-[color:var(--muted)]">NAV</div>
                  <div className="mt-1 font-mono text-[color:var(--ink)]">{fmtCompact(f.nav)}</div>
                </div>
              </div>

              <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-[color:color-mix(in_oklab,var(--accent),white_70%)] blur-2xl opacity-0 transition-opacity group-hover:opacity-100" />
            </Card>
          </Link>
        ))}
      </div>

      {!busy && !error && !filtered.length ? (
        <div className="text-sm text-[color:var(--muted)]">
          표시할 펀드가 없습니다. Airtable 테이블/뷰 설정을 확인하세요.
        </div>
      ) : null}
    </div>
  );
}

