"use client";

import Link from "next/link";
import * as React from "react";
import { ArrowRight, RefreshCw, Search } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";

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

function stepLabel(step: number) {
  if (step === 1) return "펀드/기업 선택";
  if (step === 2) return "보고서 메타";
  return "생성";
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

  React.useEffect(() => {
    loadFunds();
  }, []);

  React.useEffect(() => {
    loadCompanies(fundId);
    setCompanyId("");
    setCompanyName("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fundId]);

  const filteredFunds = React.useMemo(() => {
    const needle = fundQ.trim().toLowerCase();
    const list = (funds || []).filter((f) => {
      if (!needle) return true;
      return `${f.name || ""} ${f.vintage || ""}`.toLowerCase().includes(needle);
    });
    list.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    return list;
  }, [funds, fundQ]);

  const filteredCompanies = React.useMemo(() => {
    const needle = companyQ.trim().toLowerCase();
    const list = (companies || []).filter((c) => {
      if (!needle) return true;
      return `${c.name || ""} ${c.stage || ""} ${c.category || ""}`.toLowerCase().includes(needle);
    });
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
      const msg = e instanceof Error ? e.message : "FAILED";
      setError(msg || "세션 생성에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-[color:var(--muted)]">Investment Report</div>
          <h1 className="mt-1 font-[family-name:var(--font-display)] text-3xl tracking-tight text-[color:var(--ink)]">
            새 투자심사 세션
          </h1>
          <div className="mt-2 text-sm text-[color:var(--muted)]">
            펀드/투자기업을 고르고, 메타데이터를 입력한 뒤 세션 URL로 공유합니다.
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Link href="/report" className="inline-flex">
            <Button variant="secondary">세션 목록</Button>
          </Link>
          <Button variant="secondary" onClick={loadFunds} disabled={fundBusy}>
            <RefreshCw className="h-4 w-4" />
            데이터 새로고침
          </Button>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-900">
          {error}
        </div>
      ) : null}

      <Card variant="strong" className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm font-semibold text-[color:var(--ink)]">
            Step {step} · {stepLabel(step)}
          </div>
          <div className="flex items-center gap-2">
            <Badge tone={step === 1 ? "accent" : "neutral"}>1</Badge>
            <Badge tone={step === 2 ? "accent" : "neutral"}>2</Badge>
            <Badge tone={step === 3 ? "accent" : "neutral"}>3</Badge>
          </div>
        </div>
      </Card>

      {step === 1 ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card variant="strong" className="p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-[color:var(--ink)]">펀드 선택(선택사항)</div>
                <div className="mt-1 text-sm text-[color:var(--muted)]">Airtable 연동이 없으면 생략해도 됩니다.</div>
              </div>
              <Badge tone="neutral">{filteredFunds.length}</Badge>
            </div>

            <div className="mt-4">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-black/50" />
                <Input
                  className="pl-9"
                  placeholder="펀드 검색"
                  value={fundQ}
                  onChange={(e) => setFundQ(e.target.value)}
                />
              </div>
            </div>

            <div className="mt-3 max-h-[360px] space-y-2 overflow-auto">
              <Button
                variant={fundId ? "secondary" : "primary"}
                className="w-full justify-between"
                onClick={() => {
                  setFundId("");
                  setFundName("");
                }}
                disabled={fundBusy}
              >
                펀드 없이 진행
              </Button>

              {filteredFunds.map((f) => {
                const active = f.fundId === fundId;
                return (
                  <Button
                    key={f.fundId}
                    variant={active ? "primary" : "secondary"}
                    className="w-full justify-between"
                    onClick={() => {
                      setFundId(f.fundId);
                      setFundName(f.name);
                    }}
                    disabled={fundBusy}
                  >
                    <span className="truncate">{f.name}</span>
                    <span className="text-xs opacity-70">{f.vintage ? `Vintage ${f.vintage}` : "—"}</span>
                  </Button>
                );
              })}
            </div>
          </Card>

          <Card variant="strong" className="p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-[color:var(--ink)]">투자기업 선택</div>
                <div className="mt-1 text-sm text-[color:var(--muted)]">
                  펀드가 연결되면 해당 펀드의 투자기업 목록을 불러옵니다.
                </div>
              </div>
              <Badge tone="neutral">{filteredCompanies.length}</Badge>
            </div>

            <div className="mt-4 grid gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-black/50" />
                <Input
                  className="pl-9"
                  placeholder="기업 검색"
                  value={companyQ}
                  onChange={(e) => setCompanyQ(e.target.value)}
                  disabled={companyBusy || !companies.length}
                />
              </div>

              <Input
                placeholder="또는 기업명 직접 입력"
                value={manualCompanyName}
                onChange={(e) => setManualCompanyName(e.target.value)}
              />
            </div>

            <div className="mt-3 max-h-[320px] space-y-2 overflow-auto">
              {companyBusy ? (
                <div className="text-sm text-[color:var(--muted)]">기업 목록 불러오는 중...</div>
              ) : null}
              {!companyBusy && !companies.length ? (
                <div className="text-sm text-[color:var(--muted)]">
                  펀드를 선택하면 투자기업을 불러올 수 있습니다. 없으면 기업명을 직접 입력하세요.
                </div>
              ) : null}
              {filteredCompanies.map((c) => {
                const active = c.companyId === companyId;
                return (
                  <Button
                    key={c.companyId}
                    variant={active ? "primary" : "secondary"}
                    className="w-full justify-between"
                    onClick={() => {
                      setCompanyId(c.companyId);
                      setCompanyName(c.name);
                      setManualCompanyName("");
                    }}
                  >
                    <span className="truncate">{c.name}</span>
                    <span className="text-xs opacity-70">{c.stage || c.category || ""}</span>
                  </Button>
                );
              })}
            </div>

            <div className="mt-4 flex justify-end">
              <Button
                variant="primary"
                onClick={() => setStep(2)}
                disabled={!effectiveCompanyName}
              >
                다음 <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          </Card>
        </div>
      ) : null}

      {step === 2 ? (
        <Card variant="strong" className="p-5">
          <div className="text-sm font-semibold text-[color:var(--ink)]">보고서 메타데이터</div>
          <div className="mt-2 grid gap-3 md:grid-cols-2">
            <div>
              <div className="text-xs font-medium text-[color:var(--muted)]">기업명</div>
              <Input value={effectiveCompanyName} readOnly />
            </div>
            <div>
              <div className="text-xs font-medium text-[color:var(--muted)]">작성자</div>
              <Input value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="작성자" />
            </div>
            <div>
              <div className="text-xs font-medium text-[color:var(--muted)]">작성 일자</div>
              <Input value={reportDate} onChange={(e) => setReportDate(e.target.value)} placeholder="YYYY-MM-DD" />
            </div>
            <div>
              <div className="text-xs font-medium text-[color:var(--muted)]">파일 제목(세션 제목)</div>
              <Input value={fileTitle} onChange={(e) => setFileTitle(e.target.value)} placeholder="예: 투자심사 보고서" />
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
            <Button variant="secondary" onClick={() => setStep(1)} disabled={busy}>
              이전
            </Button>
            <Button variant="primary" onClick={() => setStep(3)} disabled={busy || !effectiveCompanyName || !fileTitle.trim()}>
              다음 <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </Card>
      ) : null}

      {step === 3 ? (
        <Card variant="strong" className="p-5">
          <div className="text-sm font-semibold text-[color:var(--ink)]">세션 생성</div>
          <div className="mt-2 text-sm text-[color:var(--muted)]">
            생성 후 `/report/&lt;slug&gt;` URL을 팀원에게 공유해 함께 작성할 수 있습니다.
          </div>

          <div className="mt-4 grid gap-2 text-sm">
            <div>기업: <span className="font-medium text-[color:var(--ink)]">{effectiveCompanyName}</span></div>
            <div>작성자: <span className="font-medium text-[color:var(--ink)]">{author || initialAuthor || "—"}</span></div>
            <div>작성일: <span className="font-mono text-[color:var(--ink)]">{reportDate || "—"}</span></div>
            <div>제목: <span className="font-medium text-[color:var(--ink)]">{fileTitle}</span></div>
            <div>펀드: <span className="font-medium text-[color:var(--ink)]">{fundName || fundId || "—"}</span></div>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
            <Button variant="secondary" onClick={() => setStep(2)} disabled={busy}>
              이전
            </Button>
            <Button variant="primary" onClick={createSession} disabled={busy}>
              {busy ? "생성 중..." : "세션 생성"}
            </Button>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
