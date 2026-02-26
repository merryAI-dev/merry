"use client";

import Link from "next/link";
import * as React from "react";
import { ArrowLeft, ArrowRight, Check, RefreshCw, Search } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";

type FundSummary = { fundId: string; name: string; vintage?: string };
type CompanySummary = { companyId: string; name: string; stage?: string; category?: string };

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.error || "FAILED");
  return json as T;
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

const STEPS = [
  { n: 1, label: "펀드 선택" },
  { n: 2, label: "기업 선택" },
  { n: 3, label: "기본 정보" },
  { n: 4, label: "생성" },
];

function StepBar({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-0">
      {STEPS.map((s, i) => {
        const done = current > s.n;
        const active = current === s.n;
        return (
          <React.Fragment key={s.n}>
            <div className="flex flex-col items-center gap-1.5">
              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold transition-all",
                  done
                    ? "bg-[#3182F6] text-white"
                    : active
                    ? "bg-[#3182F6] text-white ring-4 ring-[#3182F6]/20"
                    : "bg-[#F2F4F6] text-[#B0B8C1]",
                )}
              >
                {done ? <Check className="h-4 w-4" /> : s.n}
              </div>
              <span
                className={cn(
                  "text-[11px] font-medium whitespace-nowrap",
                  active ? "text-[#3182F6]" : done ? "text-[#4E5968]" : "text-[#B0B8C1]",
                )}
              >
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={cn(
                  "mb-5 h-[2px] flex-1 min-w-[32px] transition-all",
                  current > s.n ? "bg-[#3182F6]" : "bg-[#E5E8EB]",
                )}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function SelectRow({
  label,
  sub,
  selected,
  onClick,
}: {
  label: string;
  sub?: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-center justify-between rounded-xl px-4 py-3 text-left transition-all",
        selected
          ? "bg-[#EBF3FF] ring-1 ring-[#3182F6]"
          : "bg-white border border-[#E5E8EB] hover:border-[#C7CDD3] hover:bg-[#F8F9FA]",
      )}
    >
      <div>
        <div className={cn("text-[13.5px] font-semibold", selected ? "text-[#3182F6]" : "text-[#191F28]")}>
          {label}
        </div>
        {sub && (
          <div className="mt-0.5 text-[11.5px] text-[#8B95A1]">{sub}</div>
        )}
      </div>
      {selected && (
        <div className="ml-3 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#3182F6]">
          <Check className="h-3 w-3 text-white" />
        </div>
      )}
    </button>
  );
}

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <label className="text-[12px] font-semibold text-[#4E5968]">{label}</label>
      {children}
    </div>
  );
}

export function ReportNewWizard({ initialAuthor }: { initialAuthor: string }) {
  const [step, setStep] = React.useState(1);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [funds, setFunds] = React.useState<FundSummary[]>([]);
  const [fundBusy, setFundBusy] = React.useState(false);
  const [fundQ, setFundQ] = React.useState("");
  const [fundId, setFundId] = React.useState("");
  const [fundName, setFundName] = React.useState("");

  const [companies, setCompanies] = React.useState<CompanySummary[]>([]);
  const [companyBusy, setCompanyBusy] = React.useState(false);
  const [companyQ, setCompanyQ] = React.useState("");
  const [companyId, setCompanyId] = React.useState("");
  const [companyName, setCompanyName] = React.useState("");
  const [manualCompanyName, setManualCompanyName] = React.useState("");

  const [author, setAuthor] = React.useState(initialAuthor || "");
  const [reportDate, setReportDate] = React.useState(todayIso());
  const [fileTitle, setFileTitle] = React.useState("투자심사 보고서");

  const effectiveCompanyName = (companyName || manualCompanyName).trim();

  async function loadFunds() {
    setFundBusy(true);
    setError(null);
    try {
      const res = await fetchJson<{ funds: FundSummary[] }>("/api/funds");
      setFunds(res.funds || []);
    } catch {
      setFunds([]);
    } finally {
      setFundBusy(false);
    }
  }

  async function loadCompanies(selectedFundId: string) {
    const id = selectedFundId.trim();
    if (!id) {
      setCompanies([]);
      return;
    }
    setCompanyBusy(true);
    setError(null);
    try {
      const res = await fetchJson<{ companies?: CompanySummary[]; fund?: { name?: string } }>(`/api/funds/${id}`);
      setCompanies(res.companies || []);
      const nm = typeof res.fund?.name === "string" ? res.fund.name : "";
      if (nm && !fundName) setFundName(nm);
    } catch {
      setCompanies([]);
    } finally {
      setCompanyBusy(false);
    }
  }

  React.useEffect(() => { loadFunds(); }, []);
  React.useEffect(() => {
    loadCompanies(fundId);
    setCompanyId("");
    setCompanyName("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fundId]);

  const filteredFunds = React.useMemo(() => {
    const needle = fundQ.trim().toLowerCase();
    const list = funds.filter((f) =>
      !needle || `${f.name} ${f.vintage || ""}`.toLowerCase().includes(needle)
    );
    list.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    return list;
  }, [funds, fundQ]);

  const filteredCompanies = React.useMemo(() => {
    const needle = companyQ.trim().toLowerCase();
    const list = companies.filter((c) =>
      !needle || `${c.name} ${c.stage || ""} ${c.category || ""}`.toLowerCase().includes(needle)
    );
    list.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    return list;
  }, [companies, companyQ]);

  async function createSession() {
    setBusy(true);
    setError(null);
    try {
      const cn = effectiveCompanyName;
      if (!cn) throw new Error("기업명을 입력하세요.");
      const title = (fileTitle || "").trim() || `${cn} 투자심사 보고서`;
      const payload = {
        title,
        fileTitle: (fileTitle || "").trim(),
        reportDate: (reportDate || "").trim(),
        author: (author || "").trim() || initialAuthor || "",
        fundId: fundId || undefined,
        fundName: (fundName || "").trim() || undefined,
        companyId: companyId || undefined,
        companyName: cn,
      };
      const res = await fetchJson<{ sessionId: string }>("/api/report/sessions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      const slug = res.sessionId.replace(/^report_/, "");
      window.location.href = `/report/${slug}`;
    } catch (e) {
      setError(e instanceof Error ? e.message : "세션 생성에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 pb-10">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[12px] font-semibold uppercase tracking-widest text-[#8B95A1]">
            Investment Report
          </div>
          <h1 className="mt-1 text-2xl font-black tracking-tight text-[#191F28]">
            새 투자심사 세션
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/report">
            <Button variant="ghost" size="sm">세션 목록</Button>
          </Link>
          <Button variant="ghost" size="sm" onClick={loadFunds} disabled={fundBusy}>
            <RefreshCw className={cn("h-3.5 w-3.5", fundBusy && "animate-spin")} />
            새로고침
          </Button>
        </div>
      </div>

      {/* Step bar */}
      <div className="rounded-2xl bg-white p-5" style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px #E5E8EB" }}>
        <StepBar current={step} />
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {/* Step 1: 펀드 선택 */}
      {step === 1 && (
        <div className="rounded-2xl bg-white p-5" style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px #E5E8EB" }}>
          <div className="mb-4">
            <div className="text-[15px] font-bold text-[#191F28]">펀드를 선택하세요</div>
            <div className="mt-1 text-[13px] text-[#8B95A1]">
              Airtable과 연동된 펀드를 고릅니다. 없으면 건너뛸 수 있어요.
            </div>
          </div>

          <div className="relative mb-3">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#B0B8C1]" />
            <Input
              className="pl-9"
              placeholder="펀드명으로 검색"
              value={fundQ}
              onChange={(e) => setFundQ(e.target.value)}
            />
          </div>

          <div className="max-h-[360px] space-y-1.5 overflow-auto">
            <SelectRow
              label="펀드 없이 진행"
              sub="특정 펀드에 연결하지 않습니다"
              selected={!fundId}
              onClick={() => { setFundId(""); setFundName(""); }}
            />
            {fundBusy && (
              <div className="py-6 text-center text-sm text-[#8B95A1]">펀드 목록 불러오는 중...</div>
            )}
            {filteredFunds.map((f) => (
              <SelectRow
                key={f.fundId}
                label={f.name}
                sub={f.vintage ? `Vintage ${f.vintage}` : undefined}
                selected={f.fundId === fundId}
                onClick={() => { setFundId(f.fundId); setFundName(f.name); }}
              />
            ))}
          </div>

          <div className="mt-4 flex justify-end">
            <Button variant="primary" onClick={() => setStep(2)}>
              다음 <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Step 2: 기업 선택 */}
      {step === 2 && (
        <div className="rounded-2xl bg-white p-5" style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px #E5E8EB" }}>
          <div className="mb-4">
            <div className="text-[15px] font-bold text-[#191F28]">투자기업을 선택하세요</div>
            <div className="mt-1 text-[13px] text-[#8B95A1]">
              {fundId
                ? `${fundName || fundId} 펀드의 투자기업 목록입니다.`
                : "목록에 없으면 아래에서 직접 입력할 수 있어요."}
            </div>
          </div>

          {companies.length > 0 && (
            <div className="relative mb-3">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#B0B8C1]" />
              <Input
                className="pl-9"
                placeholder="기업명 검색"
                value={companyQ}
                onChange={(e) => setCompanyQ(e.target.value)}
                disabled={companyBusy}
              />
            </div>
          )}

          <div className="max-h-[300px] space-y-1.5 overflow-auto">
            {companyBusy && (
              <div className="py-6 text-center text-sm text-[#8B95A1]">기업 목록 불러오는 중...</div>
            )}
            {!companyBusy && filteredCompanies.map((c) => (
              <SelectRow
                key={c.companyId}
                label={c.name}
                sub={[c.stage, c.category].filter(Boolean).join(" · ") || undefined}
                selected={c.companyId === companyId}
                onClick={() => { setCompanyId(c.companyId); setCompanyName(c.name); setManualCompanyName(""); }}
              />
            ))}
            {!companyBusy && !companies.length && (
              <div className="rounded-xl bg-[#F8F9FA] px-4 py-4 text-sm text-[#8B95A1]">
                연결된 투자기업이 없습니다. 아래에서 직접 입력하세요.
              </div>
            )}
          </div>

          <div className="mt-3 border-t border-[#F2F4F6] pt-3">
            <FieldRow label="기업명 직접 입력">
              <Input
                placeholder="예: (주)머리회사"
                value={manualCompanyName}
                onChange={(e) => {
                  setManualCompanyName(e.target.value);
                  if (e.target.value) { setCompanyId(""); setCompanyName(""); }
                }}
              />
            </FieldRow>
          </div>

          <div className="mt-4 flex items-center justify-between gap-2">
            <Button variant="ghost" size="sm" onClick={() => setStep(1)} disabled={busy}>
              <ArrowLeft className="h-4 w-4" /> 이전
            </Button>
            <Button variant="primary" onClick={() => setStep(3)} disabled={!effectiveCompanyName}>
              다음 <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: 기본 정보 */}
      {step === 3 && (
        <div className="rounded-2xl bg-white p-5" style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px #E5E8EB" }}>
          <div className="mb-4">
            <div className="text-[15px] font-bold text-[#191F28]">기본 정보를 입력하세요</div>
            <div className="mt-1 text-[13px] text-[#8B95A1]">
              보고서 제목, 작성자, 날짜를 확인하고 필요 시 수정하세요.
            </div>
          </div>

          <div className="grid gap-4">
            <FieldRow label="기업명">
              <Input value={effectiveCompanyName} readOnly />
            </FieldRow>
            <div className="grid grid-cols-2 gap-4">
              <FieldRow label="작성자">
                <Input value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="작성자" />
              </FieldRow>
              <FieldRow label="작성 일자">
                <Input value={reportDate} onChange={(e) => setReportDate(e.target.value)} placeholder="YYYY-MM-DD" />
              </FieldRow>
            </div>
            <FieldRow label="세션 제목">
              <Input
                value={fileTitle}
                onChange={(e) => setFileTitle(e.target.value)}
                placeholder="예: 투자심사 보고서"
              />
            </FieldRow>
          </div>

          <div className="mt-4 flex items-center justify-between gap-2">
            <Button variant="ghost" size="sm" onClick={() => setStep(2)} disabled={busy}>
              <ArrowLeft className="h-4 w-4" /> 이전
            </Button>
            <Button
              variant="primary"
              onClick={() => setStep(4)}
              disabled={!effectiveCompanyName || !fileTitle.trim()}
            >
              다음 <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Step 4: 생성 확인 */}
      {step === 4 && (
        <div className="rounded-2xl bg-white p-5" style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px #E5E8EB" }}>
          <div className="mb-4">
            <div className="text-[15px] font-bold text-[#191F28]">세션을 생성할게요</div>
            <div className="mt-1 text-[13px] text-[#8B95A1]">
              생성 후 URL을 팀원에게 공유하면 함께 작성할 수 있어요.
            </div>
          </div>

          <div className="divide-y divide-[#F2F4F6] rounded-xl border border-[#E5E8EB] overflow-hidden">
            {[
              { label: "기업", value: effectiveCompanyName },
              { label: "펀드", value: fundName || fundId || "없음" },
              { label: "작성자", value: author || initialAuthor || "—" },
              { label: "작성일", value: reportDate || "—" },
              { label: "제목", value: fileTitle },
            ].map(({ label, value }) => (
              <div key={label} className="flex items-center justify-between px-4 py-3">
                <span className="text-[12px] font-semibold text-[#8B95A1]">{label}</span>
                <span className="text-[13.5px] font-medium text-[#191F28]">{value}</span>
              </div>
            ))}
          </div>

          <div className="mt-4 flex items-center justify-between gap-2">
            <Button variant="ghost" size="sm" onClick={() => setStep(3)} disabled={busy}>
              <ArrowLeft className="h-4 w-4" /> 이전
            </Button>
            <Button variant="primary" onClick={createSession} disabled={busy} size="md">
              {busy ? "생성 중..." : "세션 생성"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
