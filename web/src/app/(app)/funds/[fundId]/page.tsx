"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import * as React from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Brush,
} from "recharts";
import { ArrowLeft, RefreshCw, Search } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import type { CompanySummary } from "@/lib/companies";
import type { FundDetail, FundSnapshot } from "@/lib/funds";

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

function fmtRatio(n?: number) {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

function tickShortDate(s: string) {
  if (!s) return "";
  // s is expected to be YYYY-MM-DD
  return s.slice(2).replace("-", ".");
}

function TooltipBox({ label, rows }: { label?: string; rows: Array<{ name: string; value: string; color?: string }> }) {
  return (
    <div className="rounded-2xl border border-[color:var(--line)] bg-white/95 px-3 py-2 shadow-sm">
      {label ? <div className="text-xs font-medium text-[color:var(--muted)]">{label}</div> : null}
      <div className="mt-1 space-y-1">
        {rows.map((r) => (
          <div key={r.name} className="flex items-center justify-between gap-4 text-xs">
            <div className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: r.color ?? "rgba(0,0,0,0.25)" }}
              />
              <span className="text-[color:var(--muted)]">{r.name}</span>
            </div>
            <span className="font-mono text-[color:var(--ink)]">{r.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ensureSeries(fund: FundDetail, snapshots: FundSnapshot[]): FundSnapshot[] {
  const base = (snapshots || []).filter((s): s is FundSnapshot => !!s && typeof s.date === "string").slice();
  if (base.length) return base;

  const date = (fund.updatedAt || new Date().toISOString().slice(0, 10)).slice(0, 10);
  return [
    {
      date,
      nav: fund.nav,
      called: fund.called,
      distributed: fund.distributed,
      tvpi: fund.tvpi,
      dpi: fund.dpi,
      irr: fund.irr,
    },
  ];
}

export default function FundDetailPage() {
  const params = useParams<{ fundId: string }>();
  const fundId = params.fundId;

  const [fund, setFund] = React.useState<FundDetail | null>(null);
  const [snapshots, setSnapshots] = React.useState<FundSnapshot[]>([]);
  const [companies, setCompanies] = React.useState<CompanySummary[]>([]);
  const [warnings, setWarnings] = React.useState<string[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [companyQ, setCompanyQ] = React.useState("");

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetchJson<{ fund: FundDetail; snapshots: FundSnapshot[]; companies?: CompanySummary[]; warnings?: string[] }>(`/api/funds/${fundId}`);
      setFund(res.fund);
      setSnapshots(res.snapshots || []);
      setCompanies(res.companies || []);
      setWarnings(res.warnings || []);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "FAILED";
      if (msg === "UNAUTHORIZED") {
        setError("로그인이 필요합니다. 다시 로그인 후 시도하세요.");
      } else if (msg === "AIRTABLE_NOT_CONFIGURED") {
        setError("Airtable 환경변수(AIRTABLE_API_TOKEN 또는 AIRTABLE_API_KEY / AIRTABLE_BASE_ID)를 설정해야 합니다.");
      } else {
        setError("펀드 상세를 불러오지 못했습니다. Airtable 연결/권한을 확인하세요.");
      }
    } finally {
      setBusy(false);
    }
  }

  React.useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fundId]);

  const filteredCompanies = React.useMemo(() => {
    const needle = companyQ.trim().toLowerCase();
    if (!needle) return companies || [];
    return (companies || []).filter((c) => {
      const hay = `${c.name || ""} ${c.stage || ""} ${c.category || ""}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [companies, companyQ]);

  if (!fund && busy) {
    return (
      <div className="space-y-4">
        <div className="m-card animate-pulse rounded-3xl p-6">
          <div className="h-2 w-24 rounded-full bg-black/10" />
          <div className="mt-4 h-7 w-2/3 rounded-xl bg-black/10" />
          <div className="mt-3 h-4 w-1/2 rounded-xl bg-black/10" />
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="m-card h-44 animate-pulse rounded-3xl" />
          <div className="m-card h-44 animate-pulse rounded-3xl" />
          <div className="m-card h-44 animate-pulse rounded-3xl" />
        </div>
        <div className="m-card h-[360px] animate-pulse rounded-3xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Link href="/funds" className="inline-flex items-center gap-2 text-sm text-[color:var(--muted)] hover:text-[color:var(--ink)]">
          <ArrowLeft className="h-4 w-4" />
          펀드 목록
        </Link>
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-900">
          {error}
        </div>
      </div>
    );
  }

  if (!fund) {
    return (
      <div className="space-y-4">
        <Link href="/funds" className="inline-flex items-center gap-2 text-sm text-[color:var(--muted)] hover:text-[color:var(--ink)]">
          <ArrowLeft className="h-4 w-4" />
          펀드 목록
        </Link>
        <div className="text-sm text-[color:var(--muted)]">펀드를 찾지 못했습니다.</div>
      </div>
    );
  }

  const series = ensureSeries(fund, snapshots);
  const last = series.at(-1) ?? series[0];

  const committed = typeof fund.committed === "number" ? fund.committed : undefined;
  const called = typeof last?.called === "number" ? last.called : typeof fund.called === "number" ? fund.called : undefined;
  const calledPct = committed && called ? Math.max(0, Math.min(1, called / committed)) : undefined;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <Link
            href="/funds"
            className="inline-flex items-center gap-2 text-sm text-[color:var(--muted)] hover:text-[color:var(--ink)]"
          >
            <ArrowLeft className="h-4 w-4" />
            펀드 목록
          </Link>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <h1 className="min-w-0 truncate font-[family-name:var(--font-display)] text-3xl tracking-tight text-[color:var(--ink)]">
              {fund.name}
            </h1>
            <Badge tone="accent">Airtable</Badge>
            {fund.vintage ? <Badge tone="neutral">Vintage {fund.vintage}</Badge> : null}
            {fund.manager ? <Badge tone="neutral">{fund.manager}</Badge> : null}
          </div>
          <div className="mt-2 text-sm text-[color:var(--muted)]">
            마지막 스냅샷:{" "}
            <span className="font-mono text-[color:var(--ink)]">{last?.date ?? "—"}</span>
            {warnings.length ? (
              <span className="ml-2 text-xs text-[color:var(--muted)]">
                (일부 데이터/스냅샷을 불러오지 못했을 수 있습니다)
              </span>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={load} disabled={busy}>
            <RefreshCw className="h-4 w-4" />
            새로고침
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card variant="strong" className="rounded-3xl p-5">
          <div className="text-xs font-medium text-[color:var(--muted)]">Committed</div>
          <div className="mt-2 font-[family-name:var(--font-display)] text-2xl tracking-tight text-[color:var(--ink)]">
            {fmtCompact(fund.committed)}
          </div>
          <div className="mt-3 text-xs text-[color:var(--muted)]">Deploy</div>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-black/10">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[color:var(--accent)] to-[color:var(--accent-2)]"
              style={{ width: `${Math.round((calledPct ?? 0) * 100)}%` }}
            />
          </div>
          <div className="mt-2 flex items-center justify-between text-xs">
            <span className="text-[color:var(--muted)]">Called</span>
            <span className="font-mono text-[color:var(--ink)]">
              {fmtCompact(called)} {calledPct != null ? `(${Math.round(calledPct * 100)}%)` : ""}
            </span>
          </div>
        </Card>

        <Card variant="strong" className="rounded-3xl p-5">
          <div className="text-xs font-medium text-[color:var(--muted)]">NAV</div>
          <div className="mt-2 font-[family-name:var(--font-display)] text-2xl tracking-tight text-[color:var(--ink)]">
            {fmtCompact(last?.nav ?? fund.nav)}
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
              <div className="text-[11px] font-medium text-[color:var(--muted)]">Distributed</div>
              <div className="mt-1 font-mono text-sm text-[color:var(--ink)]">{fmtCompact(last?.distributed ?? fund.distributed)}</div>
            </div>
            <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
              <div className="text-[11px] font-medium text-[color:var(--muted)]">Called</div>
              <div className="mt-1 font-mono text-sm text-[color:var(--ink)]">{fmtCompact(called)}</div>
            </div>
          </div>
        </Card>

        <Card variant="strong" className="rounded-3xl p-5">
          <div className="text-xs font-medium text-[color:var(--muted)]">Performance</div>
          <div className="mt-3 grid grid-cols-3 gap-2">
            <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
              <div className="text-[11px] font-medium text-[color:var(--muted)]">TVPI</div>
              <div className="mt-1 font-mono text-sm text-[color:var(--ink)]">{fmtMultiple(last?.tvpi ?? fund.tvpi)}</div>
            </div>
            <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
              <div className="text-[11px] font-medium text-[color:var(--muted)]">DPI</div>
              <div className="mt-1 font-mono text-sm text-[color:var(--ink)]">{fmtMultiple(last?.dpi ?? fund.dpi)}</div>
            </div>
            <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
              <div className="text-[11px] font-medium text-[color:var(--muted)]">IRR</div>
              <div className="mt-1 font-mono text-sm text-[color:var(--ink)]">{fmtPct(last?.irr ?? fund.irr)}</div>
            </div>
          </div>
          <div className="mt-3 text-xs text-[color:var(--muted)]">
            모델/지표 정의는 Airtable 원본을 기준으로 표시합니다.
          </div>
        </Card>
      </div>

      <Card variant="strong" className="rounded-3xl p-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-[color:var(--ink)]">기본 정보</div>
            <div className="mt-1 text-xs text-[color:var(--muted)]">약정/투자/회수 등 핵심 항목만 표시합니다.</div>
          </div>
          <Badge tone="neutral">Terms</Badge>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
            <div className="text-[11px] font-medium text-[color:var(--muted)]">구분</div>
            <div className="mt-1 text-sm text-[color:var(--ink)]">{fund.strategy ?? "—"}</div>
          </div>
          <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
            <div className="text-[11px] font-medium text-[color:var(--muted)]">존속기간</div>
            <div className="mt-1 text-sm text-[color:var(--ink)]">{fund.lifeTerm ?? "—"}</div>
          </div>
          <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
            <div className="text-[11px] font-medium text-[color:var(--muted)]">투자기간</div>
            <div className="mt-1 text-sm text-[color:var(--ink)]">{fund.investmentTerm ?? "—"}</div>
          </div>
          <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
            <div className="text-[11px] font-medium text-[color:var(--muted)]">투자건수</div>
            <div className="mt-1 font-mono text-sm text-[color:var(--ink)]">
              {typeof fund.dealCount === "number" && Number.isFinite(fund.dealCount) ? Math.round(fund.dealCount) : "—"}
            </div>
          </div>
          <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
            <div className="text-[11px] font-medium text-[color:var(--muted)]">투자가용금액</div>
            <div className="mt-1 font-mono text-sm text-[color:var(--ink)]">{fmtCompact(fund.availableCapital)}</div>
          </div>
          <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
            <div className="text-[11px] font-medium text-[color:var(--muted)]">MYSC 출자</div>
            <div className="mt-1 flex items-baseline justify-between gap-2">
              <span className="font-mono text-sm text-[color:var(--ink)]">{fmtCompact(fund.myscCommitment)}</span>
              <span className="text-xs text-[color:var(--muted)]">{fmtRatio(fund.myscRatio)}</span>
            </div>
          </div>
        </div>
      </Card>

      <Card variant="strong" className="rounded-3xl p-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-[color:var(--ink)]">투자기업</div>
            <div className="mt-1 text-xs text-[color:var(--muted)]">
              {companyQ.trim()
                ? `검색 결과 ${filteredCompanies.length} / ${companies.length}개`
                : `연결된 스타트업 ${companies.length}개`}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-black/50" />
              <Input
                className="w-[18rem] pl-9"
                placeholder="기업 검색 (이름/단계/카테고리)"
                value={companyQ}
                onChange={(e) => setCompanyQ(e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filteredCompanies.map((c) => (
            <Link
              key={c.companyId}
              href={`/companies/${c.companyId}?fundId=${encodeURIComponent(fundId)}`}
              className="block"
            >
              <Card
                className="group relative overflow-hidden rounded-3xl p-4 transition-colors hover:bg-white/95"
              >
                <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[color:var(--accent)] via-[color:color-mix(in_oklab,var(--accent),white_24%)] to-[color:var(--accent-2)]" />

                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold text-[color:var(--ink)]">
                      {c.name}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[color:var(--muted)]">
                      {c.stage ? <span>{c.stage}</span> : null}
                      {c.category ? (
                        <>
                          <span>·</span>
                          <span>{c.category}</span>
                        </>
                      ) : null}
                      {c.investedAt ? (
                        <>
                          <span>·</span>
                          <span className="font-mono">{c.investedAt}</span>
                        </>
                      ) : null}
                    </div>
                  </div>
                  <Badge tone="accent">상세</Badge>
                </div>

                <div className="mt-4 grid grid-cols-3 gap-2">
                  <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
                    <div className="text-[11px] font-medium text-[color:var(--muted)]">Invested</div>
                    <div className="mt-1 font-mono text-sm text-[color:var(--ink)]">{fmtCompact(c.investedAmount)}</div>
                  </div>
                  <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
                    <div className="text-[11px] font-medium text-[color:var(--muted)]">Multiple</div>
                    <div className="mt-1 font-mono text-sm text-[color:var(--ink)]">
                      {typeof c.multiple === "number" && Number.isFinite(c.multiple) ? `${c.multiple.toFixed(2)}x` : "—"}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
                    <div className="text-[11px] font-medium text-[color:var(--muted)]">NAV</div>
                    <div className="mt-1 font-mono text-sm text-[color:var(--ink)]">{fmtCompact(c.nav)}</div>
                  </div>
                </div>

                {c.categories?.length ? (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {c.categories.slice(0, 4).map((t) => (
                      <span
                        key={t}
                        className="rounded-full border border-[color:var(--line)] bg-black/[0.03] px-2 py-0.5 text-[11px] text-[color:var(--muted)]"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                ) : null}

                <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-[color:color-mix(in_oklab,var(--accent),white_70%)] blur-2xl opacity-0 transition-opacity group-hover:opacity-100" />
              </Card>
            </Link>
          ))}
        </div>

        {!busy && !filteredCompanies.length ? (
          <div className="mt-4 text-sm text-[color:var(--muted)]">
            {companyQ.trim()
              ? "검색 결과가 없습니다."
              : "표시할 투자기업이 없습니다. Airtable의 펀드-투자기업 링크 필드를 확인하세요."}
          </div>
        ) : null}
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card variant="strong" className="rounded-3xl p-5">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <div className="text-sm font-semibold text-[color:var(--ink)]">NAV 추이</div>
              <div className="mt-1 text-xs text-[color:var(--muted)]">그라데이션 영역 + 브러시로 구간 확대</div>
            </div>
            <Badge tone={series.length >= 2 ? "accent" : "neutral"}>{series.length >= 2 ? "시계열" : "단일 시점"}</Badge>
          </div>
          <div className="mt-4 h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="navGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.28} />
                    <stop offset="70%" stopColor="var(--accent)" stopOpacity={0.06} />
                    <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(16,24,39,0.10)" vertical={false} />
                <XAxis dataKey="date" tickFormatter={tickShortDate} tick={{ fontSize: 11, fill: "rgba(16,24,39,0.55)" }} />
                <YAxis tickFormatter={(v) => fmtCompact(typeof v === "number" ? v : undefined)} tick={{ fontSize: 11, fill: "rgba(16,24,39,0.55)" }} width={56} />
                <Tooltip
                  content={(p) => {
                    if (!p || !p.active) return null;
                    const payload = (p.payload || []) as Array<{ name?: string; value?: unknown; color?: string }>;
                    const navV = payload.find((x) => x.name === "nav")?.value;
                    return (
                      <TooltipBox
                        label={typeof p.label === "string" ? p.label : ""}
                        rows={[
                          { name: "NAV", value: fmtCompact(typeof navV === "number" ? navV : undefined), color: "var(--accent)" },
                        ]}
                      />
                    );
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="nav"
                  name="nav"
                  stroke="var(--accent)"
                  strokeWidth={2.2}
                  fill="url(#navGradient)"
                  dot={false}
                  activeDot={{ r: 4 }}
                />
                {series.length >= 12 ? <Brush dataKey="date" height={24} stroke="var(--accent)" travellerWidth={10} /> : null}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card variant="strong" className="rounded-3xl p-5">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <div className="text-sm font-semibold text-[color:var(--ink)]">투입/회수</div>
              <div className="mt-1 text-xs text-[color:var(--muted)]">스냅샷 기준 Called vs Distributed</div>
            </div>
            <Badge tone="neutral">Cashflow</Badge>
          </div>
          <div className="mt-4 h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={series} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="calledGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.9} />
                    <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.25} />
                  </linearGradient>
                  <linearGradient id="distGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent-2)" stopOpacity={0.9} />
                    <stop offset="100%" stopColor="var(--accent-2)" stopOpacity={0.25} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(16,24,39,0.10)" vertical={false} />
                <XAxis dataKey="date" tickFormatter={tickShortDate} tick={{ fontSize: 11, fill: "rgba(16,24,39,0.55)" }} />
                <YAxis tickFormatter={(v) => fmtCompact(typeof v === "number" ? v : undefined)} tick={{ fontSize: 11, fill: "rgba(16,24,39,0.55)" }} width={56} />
                <Tooltip
                  content={(p) => {
                    if (!p || !p.active) return null;
                    const payload = (p.payload || []) as Array<{ name?: string; value?: unknown }>;
                    const calledV = payload.find((x) => x.name === "called")?.value;
                    const distV = payload.find((x) => x.name === "distributed")?.value;
                    return (
                      <TooltipBox
                        label={typeof p.label === "string" ? p.label : ""}
                        rows={[
                          { name: "Called", value: fmtCompact(typeof calledV === "number" ? calledV : undefined), color: "var(--accent)" },
                          { name: "Distributed", value: fmtCompact(typeof distV === "number" ? distV : undefined), color: "var(--accent-2)" },
                        ]}
                      />
                    );
                  }}
                />
                <Bar dataKey="called" name="called" fill="url(#calledGradient)" radius={[10, 10, 0, 0]} />
                <Bar dataKey="distributed" name="distributed" fill="url(#distGradient)" radius={[10, 10, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card variant="strong" className="rounded-3xl p-5">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <div className="text-sm font-semibold text-[color:var(--ink)]">Multiples (TVPI / DPI)</div>
            <div className="mt-1 text-xs text-[color:var(--muted)]">라인 차트 + 툴팁</div>
          </div>
          <Badge tone="neutral">Performance</Badge>
        </div>
        <div className="mt-4 h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="rgba(16,24,39,0.10)" vertical={false} />
              <XAxis dataKey="date" tickFormatter={tickShortDate} tick={{ fontSize: 11, fill: "rgba(16,24,39,0.55)" }} />
              <YAxis tick={{ fontSize: 11, fill: "rgba(16,24,39,0.55)" }} width={56} />
              <Tooltip
                content={(p) => {
                  if (!p || !p.active) return null;
                  const payload = (p.payload || []) as Array<{ name?: string; value?: unknown }>;
                  const tvpiV = payload.find((x) => x.name === "tvpi")?.value;
                  const dpiV = payload.find((x) => x.name === "dpi")?.value;
                  return (
                    <TooltipBox
                      label={typeof p.label === "string" ? p.label : ""}
                      rows={[
                        { name: "TVPI", value: fmtMultiple(typeof tvpiV === "number" ? tvpiV : undefined), color: "var(--accent)" },
                        { name: "DPI", value: fmtMultiple(typeof dpiV === "number" ? dpiV : undefined), color: "var(--accent-2)" },
                      ]}
                    />
                  );
                }}
              />
              <Line type="monotone" dataKey="tvpi" name="tvpi" stroke="var(--accent)" strokeWidth={2.4} dot={false} activeDot={{ r: 4 }} />
              <Line type="monotone" dataKey="dpi" name="dpi" stroke="var(--accent-2)" strokeWidth={2.4} dot={false} activeDot={{ r: 4 }} />
              {series.length >= 12 ? <Brush dataKey="date" height={24} stroke="rgba(16,24,39,0.25)" travellerWidth={10} /> : null}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}
