"use client";

import * as React from "react";
import { ArrowLeft, ArrowRight, Check, Search, X } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { apiFetch } from "@/lib/apiClient";

/* ── Types ── */

type FundSummary = { fundId: string; name: string };
type CompanySummary = { companyId: string; name: string; stage?: string; category?: string };

export type ReportSessionModalProps = {
  onClose: () => void;
  initialAuthor?: string;
  /** 문서 추출에서 넘어온 컨텍스트 (마크다운 요약) */
  extractedContext?: string;
  /** 추출 결과에서 감지된 기업명 힌트 */
  initialCompanyName?: string;
};

/* ── Constants ── */

const FUNDS: FundSummary[] = [
  { fundId: "fund_01", name: "코리아임팩트스케일업 투자조합" },
  { fundId: "fund_02", name: "다날-EMA 경기 시드 레벨업" },
  { fundId: "fund_03", name: "우리강산 푸르게 푸르게 임팩트 펀드 2호" },
  { fundId: "fund_04", name: "제주 초기스타트업 육성 펀드" },
  { fundId: "fund_05", name: "엑스트라마일 임팩트 6호 벤처투자조합" },
  { fundId: "fund_06", name: "카이스트-미스크 더블임팩트 펀드" },
  { fundId: "fund_07", name: "인구활력 HGI-MYSC 투자조합" },
  { fundId: "fund_08", name: "엑스트라마일 임팩트 7호 개인투자조합" },
  { fundId: "fund_09", name: "엑스트라마일 라이콘 펀드" },
  { fundId: "fund_10", name: "어 모어 뷰티풀 챌린지 펀드 2호" },
];

const STEPS = [
  { n: 1, label: "펀드 선택" },
  { n: 2, label: "기업 정보" },
  { n: 3, label: "확인" },
];

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

/* ── Sub-components ── */

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
                  "flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-all",
                  done
                    ? "bg-[var(--accent)] text-white"
                    : active
                    ? "bg-[var(--accent)] text-white ring-4 ring-[var(--accent)]/20"
                    : "bg-[#F2F4F6] text-[#B0B8C1]",
                )}
              >
                {done ? <Check className="h-3.5 w-3.5" /> : s.n}
              </div>
              <span
                className={cn(
                  "text-[11px] font-medium whitespace-nowrap",
                  active ? "text-[var(--accent)]" : done ? "text-[#4E5968]" : "text-[#B0B8C1]",
                )}
              >
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={cn(
                  "mb-5 h-[2px] flex-1 min-w-[40px] transition-all",
                  current > s.n ? "bg-[var(--accent)]" : "bg-[#E5E8EB]",
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
  label, sub, selected, onClick,
}: {
  label: string; sub?: string; selected: boolean; onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-center justify-between rounded-xl px-4 py-3 text-left transition-all",
        selected
          ? "bg-[#EBF3FF] ring-1 ring-[var(--accent)]"
          : "bg-white border border-[#E5E8EB] hover:border-[#C7CDD3] hover:bg-[#F8F9FA]",
      )}
    >
      <div>
        <div className={cn("text-[13px] font-semibold", selected ? "text-[var(--accent)]" : "text-[#191F28]")}>
          {label}
        </div>
        {sub && <div className="mt-0.5 text-[11px] text-[#8B95A1]">{sub}</div>}
      </div>
      {selected && (
        <div className="ml-3 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--accent)]">
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

/* ── Main Modal ── */

export function ReportSessionModal({
  onClose,
  initialAuthor = "",
  extractedContext,
  initialCompanyName = "",
}: ReportSessionModalProps) {
  const [step, setStep] = React.useState(1);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Fund
  const [fundQ, setFundQ] = React.useState("");
  const [fundId, setFundId] = React.useState("");
  const [fundName, setFundName] = React.useState("");

  // Company
  const [companies, setCompanies] = React.useState<CompanySummary[]>([]);
  const [companyBusy, setCompanyBusy] = React.useState(false);
  const [companyQ, setCompanyQ] = React.useState("");
  const [companyId, setCompanyId] = React.useState("");
  const [companyName, setCompanyName] = React.useState("");
  const [manualCompanyName, setManualCompanyName] = React.useState(initialCompanyName);

  // Metadata
  const [author, setAuthor] = React.useState(initialAuthor);
  const [reportDate, setReportDate] = React.useState(todayIso());
  const [fileTitle, setFileTitle] = React.useState("투자심사 보고서");

  const effectiveCompanyName = (companyName || manualCompanyName).trim();

  // Update title when company name changes
  React.useEffect(() => {
    const cn = effectiveCompanyName;
    if (cn) setFileTitle(`${cn} 투자심사 보고서`);
  }, [effectiveCompanyName]);

  async function loadCompanies(selectedFundId: string) {
    if (!selectedFundId) { setCompanies([]); return; }
    setCompanyBusy(true);
    try {
      const res = await apiFetch<{ companies?: CompanySummary[]; fund?: { name?: string } }>(
        `/api/funds/${selectedFundId}`,
      );
      setCompanies(res.companies ?? []);
      const nm = res.fund?.name;
      if (nm && !fundName) setFundName(nm);
    } catch {
      setCompanies([]);
    } finally {
      setCompanyBusy(false);
    }
  }

  React.useEffect(() => {
    loadCompanies(fundId);
    setCompanyId("");
    setCompanyName("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fundId]);

  const filteredFunds = React.useMemo(() => {
    const needle = fundQ.trim().toLowerCase();
    return FUNDS.filter((f) => !needle || f.name.toLowerCase().includes(needle));
  }, [fundQ]);

  const filteredCompanies = React.useMemo(() => {
    const needle = companyQ.trim().toLowerCase();
    return companies
      .filter((c) => !needle || `${c.name} ${c.stage ?? ""} ${c.category ?? ""}`.toLowerCase().includes(needle))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [companies, companyQ]);

  async function createSession() {
    setBusy(true);
    setError(null);
    try {
      const cn = effectiveCompanyName;
      if (!cn) throw new Error("기업명을 입력하세요.");
      const title = fileTitle.trim() || `${cn} 투자심사 보고서`;
      const payload = {
        title,
        fileTitle: fileTitle.trim(),
        reportDate: reportDate.trim(),
        author: author.trim() || initialAuthor,
        fundId: fundId || undefined,
        fundName: fundName.trim() || undefined,
        companyId: companyId || undefined,
        companyName: cn,
        ...(extractedContext ? { context: extractedContext } : {}),
      };
      const res = await apiFetch<{ sessionId: string; slug?: string }>("/api/review/sessions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      const slug = res.slug ?? (res.sessionId ?? "").replace(/^report_/, "");
      window.location.href = `/review/${slug}`;
    } catch (e) {
      setError(e instanceof Error ? e.message : "세션 생성에 실패했습니다.");
      setBusy(false);
    }
  }

  // ESC to close
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(3px)" }}
    >
      {/* Panel */}
      <div
        className="relative w-full max-w-lg rounded-2xl bg-white shadow-2xl"
        style={{ maxHeight: "90vh", overflowY: "auto" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#F2F4F6] px-6 py-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-widest text-[#8B95A1]">
              투자심사 세션
            </div>
            <h2 className="mt-0.5 text-[17px] font-black text-[#191F28]">
              새 보고서 시작
            </h2>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-full text-[#8B95A1] hover:bg-[#F2F4F6] transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Step bar */}
        <div className="px-6 pt-5 pb-4">
          <StepBar current={step} />
        </div>

        {/* Error */}
        {error && (
          <div className="mx-6 mb-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        {/* Body */}
        <div className="px-6 pb-6">

          {/* Step 1 — 펀드 선택 */}
          {step === 1 && (
            <div className="space-y-3">
              <div>
                <div className="text-[14px] font-bold text-[#191F28]">펀드를 선택하세요</div>
                <div className="mt-0.5 text-[12.5px] text-[#8B95A1]">
                  투자심사에 연결할 펀드를 선택하세요. 없으면 건너뛸 수 있어요.
                </div>
              </div>

              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#B0B8C1]" />
                <Input
                  className="pl-9"
                  placeholder="펀드명으로 검색"
                  value={fundQ}
                  onChange={(e) => setFundQ(e.target.value)}
                />
              </div>

              <div className="max-h-[280px] space-y-1.5 overflow-auto">
                <SelectRow
                  label="펀드 없이 진행"
                  sub="특정 펀드에 연결하지 않습니다"
                  selected={!fundId}
                  onClick={() => { setFundId(""); setFundName(""); }}
                />
                {filteredFunds.map((f) => (
                  <SelectRow
                    key={f.fundId}
                    label={f.name}
                    selected={f.fundId === fundId}
                    onClick={() => { setFundId(f.fundId); setFundName(f.name); }}
                  />
                ))}
              </div>

              <div className="flex justify-end pt-1">
                <Button variant="primary" onClick={() => setStep(2)}>
                  다음 <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}

          {/* Step 2 — 기업 정보 */}
          {step === 2 && (
            <div className="space-y-3">
              <div>
                <div className="text-[14px] font-bold text-[#191F28]">투자기업을 입력하세요</div>
                <div className="mt-0.5 text-[12.5px] text-[#8B95A1]">
                  {fundId
                    ? `${fundName || fundId} 펀드의 투자기업 목록입니다.`
                    : "목록에 없으면 아래에서 직접 입력할 수 있어요."}
                </div>
              </div>

              {/* Company list from fund */}
              {(companies.length > 0 || companyBusy) && (
                <>
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#B0B8C1]" />
                    <Input
                      className="pl-9"
                      placeholder="기업명 검색"
                      value={companyQ}
                      onChange={(e) => setCompanyQ(e.target.value)}
                      disabled={companyBusy}
                    />
                  </div>
                  <div className="max-h-[200px] space-y-1.5 overflow-auto">
                    {companyBusy && (
                      <div className="py-4 text-center text-sm text-[#8B95A1]">기업 목록 불러오는 중...</div>
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
                  </div>
                  <div className="border-t border-[#F2F4F6] pt-3">
                    <FieldRow label="목록에 없으면 직접 입력">
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
                </>
              )}

              {/* No fund selected — just manual input */}
              {!fundId && companies.length === 0 && !companyBusy && (
                <FieldRow label="기업명">
                  <Input
                    placeholder="예: (주)머리회사"
                    value={manualCompanyName}
                    autoFocus
                    onChange={(e) => setManualCompanyName(e.target.value)}
                  />
                </FieldRow>
              )}

              {/* Metadata fields */}
              <div className="grid grid-cols-2 gap-3 pt-1">
                <FieldRow label="작성자">
                  <Input
                    value={author}
                    onChange={(e) => setAuthor(e.target.value)}
                    placeholder="작성자"
                  />
                </FieldRow>
                <FieldRow label="작성 일자">
                  <Input
                    value={reportDate}
                    onChange={(e) => setReportDate(e.target.value)}
                    placeholder="YYYY-MM-DD"
                  />
                </FieldRow>
              </div>
              <FieldRow label="보고서 제목">
                <Input
                  value={fileTitle}
                  onChange={(e) => setFileTitle(e.target.value)}
                  placeholder="예: 투자심사 보고서"
                />
              </FieldRow>

              <div className="flex items-center justify-between pt-1">
                <Button variant="ghost" size="sm" onClick={() => setStep(1)}>
                  <ArrowLeft className="h-4 w-4" /> 이전
                </Button>
                <Button
                  variant="primary"
                  onClick={() => setStep(3)}
                  disabled={!effectiveCompanyName}
                >
                  다음 <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}

          {/* Step 3 — 확인 */}
          {step === 3 && (
            <div className="space-y-4">
              <div>
                <div className="text-[14px] font-bold text-[#191F28]">세션을 생성할게요</div>
                <div className="mt-0.5 text-[12.5px] text-[#8B95A1]">
                  생성 후 URL을 팀원에게 공유하면 함께 작성할 수 있어요.
                </div>
              </div>

              <div className="divide-y divide-[#F2F4F6] overflow-hidden rounded-xl border border-[#E5E8EB]">
                {[
                  { label: "기업", value: effectiveCompanyName },
                  { label: "펀드", value: fundName || (fundId ? fundId : "없음") },
                  { label: "작성자", value: author || initialAuthor || "—" },
                  { label: "작성일", value: reportDate || "—" },
                  { label: "제목", value: fileTitle },
                  ...(extractedContext
                    ? [{ label: "추출 문서", value: "자동 주입됨 ✓" }]
                    : []),
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between px-4 py-3">
                    <span className="text-[12px] font-semibold text-[#8B95A1]">{label}</span>
                    <span className={cn(
                      "text-[13px] font-medium",
                      value === "자동 주입됨 ✓" ? "text-emerald-600" : "text-[#191F28]",
                    )}>
                      {value}
                    </span>
                  </div>
                ))}
              </div>

              <div className="flex items-center justify-between">
                <Button variant="ghost" size="sm" onClick={() => setStep(2)} disabled={busy}>
                  <ArrowLeft className="h-4 w-4" /> 이전
                </Button>
                <Button variant="primary" onClick={createSession} disabled={busy} size="md">
                  {busy ? "생성 중..." : "세션 생성 →"}
                </Button>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
