"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import * as React from "react";
import { ArrowLeft, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { CompanyDetail } from "@/lib/companies";
import { apiFetch } from "@/lib/apiClient";


function fmtCompact(n?: number) {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("ko-KR", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

function fmtMultiple(n?: number) {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return `${n.toFixed(2)}x`;
}

function friendlyAirtableError(code: string): string | null {
  if (!code.startsWith("AIRTABLE_")) return null;
  if (code === "AIRTABLE_TIMEOUT") return "Airtable 응답이 지연되었습니다. 잠시 후 다시 시도하세요.";
  if (code === "AIRTABLE_RATE_LIMITED") return "Airtable 요청이 너무 많습니다(429). 10-20초 후 다시 시도하세요.";
  if (code === "AIRTABLE_UNAUTHORIZED") return "Airtable 토큰/권한이 없습니다. Base 공유/토큰 Scope를 확인하세요.";
  if (code === "AIRTABLE_NOT_FOUND") return "Airtable Base ID 또는 테이블 이름/ID가 올바르지 않습니다.";
  if (code.includes("AUTHENTICATION") || code.includes("INVALID_PERMISSIONS")) {
    return "Airtable 권한이 부족합니다. 해당 Base에 읽기 권한이 있는 PAT인지 확인하세요.";
  }
  return `Airtable 오류: ${code.replace("AIRTABLE_", "")}`;
}

export default function CompanyDetailPage() {
  const params = useParams<{ companyId: string }>();
  const sp = useSearchParams();
  const companyId = params.companyId;
  const fromFundId = (sp.get("fundId") ?? "").trim();

  const [company, setCompany] = React.useState<CompanyDetail | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch<{ company: CompanyDetail }>(`/api/companies/${companyId}`);
      setCompany(res.company);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "FAILED";
      if (msg === "UNAUTHORIZED") {
        setError("로그인이 필요합니다. 다시 로그인 후 시도하세요.");
      } else if (msg === "AIRTABLE_NOT_CONFIGURED") {
        setError("Airtable 환경변수(AIRTABLE_API_TOKEN 또는 AIRTABLE_API_KEY / AIRTABLE_BASE_ID)를 설정해야 합니다.");
      } else if (msg.startsWith("AIRTABLE_")) {
        setError(friendlyAirtableError(msg) ?? "기업 상세를 불러오지 못했습니다. Airtable 연결/권한을 확인하세요.");
      } else {
        setError("기업 상세를 불러오지 못했습니다. Airtable 연결/권한을 확인하세요.");
      }
    } finally {
      setBusy(false);
    }
  }

  React.useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId]);

  const backHref = fromFundId ? `/funds/${fromFundId}` : "/funds";

  if (!company && busy) {
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
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Link href={backHref} className="inline-flex items-center gap-2 text-sm text-[#8B95A1] hover:text-[#191F28]">
          <ArrowLeft className="h-4 w-4" />
          돌아가기
        </Link>
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-900">
          {error}
        </div>
      </div>
    );
  }

  if (!company) {
    return (
      <div className="space-y-4">
        <Link href={backHref} className="inline-flex items-center gap-2 text-sm text-[#8B95A1] hover:text-[#191F28]">
          <ArrowLeft className="h-4 w-4" />
          돌아가기
        </Link>
        <div className="text-sm text-[#8B95A1]">기업을 찾지 못했습니다.</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <Link
            href={backHref}
            className="inline-flex items-center gap-2 text-sm text-[#8B95A1] hover:text-[#191F28]"
          >
            <ArrowLeft className="h-4 w-4" />
            {fromFundId ? "펀드로 돌아가기" : "펀드 목록"}
          </Link>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <h1 className="min-w-0 truncate font-[family-name:var(--font-display)] text-3xl tracking-tight text-[#191F28]">
              {company.name}
            </h1>
            <Badge tone="accent">Airtable</Badge>
            {company.stage ? <Badge tone="neutral">{company.stage}</Badge> : null}
            {company.category ? <Badge tone="neutral">{company.category}</Badge> : null}
            {company.investmentType ? <Badge tone="neutral">{company.investmentType}</Badge> : null}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-[#8B95A1]">
            {company.investedAt ? (
              <span>
                투자일 <span className="font-mono text-[#191F28]">{company.investedAt}</span>
              </span>
            ) : null}
            <span className="font-mono">ID {company.companyId}</span>
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
          <div className="text-xs font-medium text-[#8B95A1]">Invested</div>
          <div className="mt-2 font-[family-name:var(--font-display)] text-2xl tracking-tight text-[#191F28]">
            {fmtCompact(company.investedAmount)}
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <div className="rounded-2xl border border-[#E5E8EB] bg-white p-3">
              <div className="text-[11px] font-medium text-[#8B95A1]">Principal</div>
              <div className="mt-1 font-mono text-sm text-[#191F28]">{fmtCompact(company.returnedPrincipal)}</div>
            </div>
            <div className="rounded-2xl border border-[#E5E8EB] bg-white p-3">
              <div className="text-[11px] font-medium text-[#8B95A1]">Profit</div>
              <div className="mt-1 font-mono text-sm text-[#191F28]">{fmtCompact(company.returnedProfit)}</div>
            </div>
          </div>
        </Card>

        <Card variant="strong" className="rounded-3xl p-5">
          <div className="text-xs font-medium text-[#8B95A1]">NAV</div>
          <div className="mt-2 font-[family-name:var(--font-display)] text-2xl tracking-tight text-[#191F28]">
            {fmtCompact(company.nav)}
          </div>
          <div className="mt-4 text-xs text-[#8B95A1]">미회수투자자산 기준</div>
        </Card>

        <Card variant="strong" className="rounded-3xl p-5">
          <div className="text-xs font-medium text-[#8B95A1]">Multiple</div>
          <div className="mt-2 font-[family-name:var(--font-display)] text-2xl tracking-tight text-[#191F28]">
            {fmtMultiple(company.multiple)}
          </div>
          <div className="mt-4 text-xs text-[#8B95A1]">Airtable formula 기반</div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card variant="strong" className="rounded-3xl p-5">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <div className="text-sm font-semibold text-[#191F28]">기업 정보</div>
              <div className="mt-1 text-xs text-[#8B95A1]">핵심 필드만 노출</div>
            </div>
            <Badge tone="neutral">Profile</Badge>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-[#E5E8EB] bg-white p-3">
              <div className="text-[11px] font-medium text-[#8B95A1]">본점 소재지</div>
              <div className="mt-1 text-sm text-[#191F28]">{company.location ?? "—"}</div>
            </div>
            <div className="rounded-2xl border border-[#E5E8EB] bg-white p-3">
              <div className="text-[11px] font-medium text-[#8B95A1]">설립일</div>
              <div className="mt-1 text-sm text-[#191F28]">{company.foundedAt ?? "—"}</div>
            </div>
            <div className="rounded-2xl border border-[#E5E8EB] bg-white p-3">
              <div className="text-[11px] font-medium text-[#8B95A1]">대표자</div>
              <div className="mt-1 text-sm text-[#191F28]">{company.ceo ?? "—"}</div>
            </div>
            <div className="rounded-2xl border border-[#E5E8EB] bg-white p-3">
              <div className="text-[11px] font-medium text-[#8B95A1]">연락처</div>
              <div className="mt-1 text-sm text-[#191F28]">{company.contact ?? "—"}</div>
            </div>
          </div>
        </Card>

        <Card variant="strong" className="rounded-3xl p-5">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <div className="text-sm font-semibold text-[#191F28]">제품/서비스</div>
              <div className="mt-1 text-xs text-[#8B95A1]">요약 텍스트</div>
            </div>
            <Badge tone="neutral">Notes</Badge>
          </div>
          <div className="mt-4 whitespace-pre-wrap text-sm text-[#191F28]">
            {company.products ?? "—"}
          </div>
        </Card>
      </div>

      {(company.investmentPoint || company.exitPlan || company.exitExpectation) ? (
        <Card variant="strong" className="rounded-3xl p-5">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <div className="text-sm font-semibold text-[#191F28]">투자 메모</div>
              <div className="mt-1 text-xs text-[#8B95A1]">Airtable 원본 기준</div>
            </div>
            <Badge tone="neutral">Memo</Badge>
          </div>
          <div className="mt-4 grid gap-3 lg:grid-cols-3">
            <div className="rounded-2xl border border-[#E5E8EB] bg-white p-4">
              <div className="text-xs font-semibold text-[#191F28]">투자포인트</div>
              <div className="mt-2 whitespace-pre-wrap text-sm text-[#8B95A1]">{company.investmentPoint ?? "—"}</div>
            </div>
            <div className="rounded-2xl border border-[#E5E8EB] bg-white p-4">
              <div className="text-xs font-semibold text-[#191F28]">Exit 방안</div>
              <div className="mt-2 whitespace-pre-wrap text-sm text-[#8B95A1]">{company.exitPlan ?? "—"}</div>
            </div>
            <div className="rounded-2xl border border-[#E5E8EB] bg-white p-4">
              <div className="text-xs font-semibold text-[#191F28]">Exit 예상</div>
              <div className="mt-2 whitespace-pre-wrap text-sm text-[#8B95A1]">{company.exitExpectation ?? "—"}</div>
            </div>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
