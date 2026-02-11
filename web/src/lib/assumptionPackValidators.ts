import type { Assumption, AssumptionEvidenceRef, AssumptionPack, CheckResult, ValidationStatus } from "@/lib/reportPacks";

export type ValidationResult = {
  status: ValidationStatus;
  checks: CheckResult[];
  normalizedPack: AssumptionPack;
};

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function hasEvidence(evidence: AssumptionEvidenceRef[] | undefined): boolean {
  if (!Array.isArray(evidence) || !evidence.length) return false;
  for (const e of evidence) {
    if (!e || typeof e !== "object") continue;
    const rec = e as Record<string, unknown>;
    if (typeof rec["factId"] === "string" && rec["factId"].trim()) return true;
    if (typeof rec["note"] === "string" && rec["note"].trim()) return true;
  }
  return false;
}

export function getAssumption(pack: AssumptionPack, key: string): Assumption | undefined {
  const k = (key ?? "").trim();
  if (!k) return undefined;
  return (pack.assumptions || []).find((a) => (a?.key ?? "").trim() === k);
}

export function getAssumptionNumber(pack: AssumptionPack, key: string): number | undefined {
  const a = getAssumption(pack, key);
  if (!a) return undefined;
  return asNumber(a.numberValue);
}

export function getAssumptionString(pack: AssumptionPack, key: string): string | undefined {
  const a = getAssumption(pack, key);
  if (!a) return undefined;
  return asString(a.stringValue);
}

export function getAssumptionNumberArray(pack: AssumptionPack, key: string): number[] | undefined {
  const a = getAssumption(pack, key);
  if (!a) return undefined;
  const arr = Array.isArray(a.numberArrayValue) ? a.numberArrayValue : undefined;
  if (!arr?.length) return undefined;
  const nums = arr.map((n) => (typeof n === "number" ? n : Number(n))).filter((n) => Number.isFinite(n));
  return nums.length ? nums : undefined;
}

function ensureRequiredAssumptions(pack: AssumptionPack): AssumptionPack {
  const requiredKeys: Array<{ key: string; valueType: Assumption["valueType"]; unit?: string }> = [
    { key: "target_year", valueType: "number", unit: "year" },
    { key: "investment_year", valueType: "number", unit: "year" },
    { key: "investment_date", valueType: "string" },
    { key: "investment_amount", valueType: "number", unit: "KRW" },
    { key: "shares", valueType: "number", unit: "shares" },
    { key: "total_shares", valueType: "number", unit: "shares" },
    { key: "price_per_share", valueType: "number", unit: "KRW" },
    { key: "net_income_target_year", valueType: "number", unit: "KRW" },
    { key: "per_multiples", valueType: "number_array", unit: "x" },
  ];

  const existing = new Set((pack.assumptions || []).map((a) => (a?.key ?? "").trim()).filter(Boolean));
  const additions: Assumption[] = [];
  for (const r of requiredKeys) {
    if (existing.has(r.key)) continue;
    additions.push({
      key: r.key,
      valueType: r.valueType,
      unit: r.unit,
      required: true,
      evidence: [{ note: "확인 필요" }],
    });
  }

  if (!additions.length) return pack;
  return { ...pack, assumptions: [...(pack.assumptions || []), ...additions] };
}

function normalizePerMultiples(values: number[]): { normalized: number[]; changed: boolean } {
  const raw = (values || []).map((n) => (typeof n === "number" ? n : Number(n))).filter((n) => Number.isFinite(n));
  const filtered = raw.filter((n) => n >= 1 && n <= 200);
  const dedup = Array.from(new Set(filtered)).sort((a, b) => a - b).slice(0, 12);
  const changed = raw.length !== dedup.length || raw.some((n, i) => dedup[i] !== n);
  return { normalized: dedup.length ? dedup : [10, 20, 30], changed: changed || !dedup.length };
}

function normalizePack(pack: AssumptionPack): { pack: AssumptionPack; notes: CheckResult[] } {
  const notes: CheckResult[] = [];
  let next = ensureRequiredAssumptions(pack);

  // Normalize per_multiples array.
  const per = getAssumptionNumberArray(next, "per_multiples") ?? [];
  const { normalized, changed } = normalizePerMultiples(per);
  if (changed) {
    notes.push({ check: "RangeCheck", status: "warn", message: "per_multiples를 1~200 범위로 정규화/중복 제거했습니다." });
    next = {
      ...next,
      assumptions: (next.assumptions || []).map((a) => {
        if ((a?.key ?? "").trim() !== "per_multiples") return a;
        return { ...a, valueType: "number_array", numberArrayValue: normalized, unit: a.unit || "x" };
      }),
    };
  }

  // Complexity gate (soft).
  const assumptionCount = (next.assumptions || []).length;
  if (assumptionCount > 40) {
    notes.push({ check: "ComplexityGate", status: "warn", message: `가정 개수가 많습니다(${assumptionCount}). 핵심만 남기세요.` });
  }
  const scenarioCount = (next.scenarios || []).length;
  if (scenarioCount > 5) {
    notes.push({ check: "ComplexityGate", status: "warn", message: `시나리오 개수가 많습니다(${scenarioCount}). base/bull/bear로 시작하세요.` });
  }

  return { pack: next, notes };
}

export function validateAssumptionPack(pack: AssumptionPack, prevLocked?: AssumptionPack | null): ValidationResult {
  const { pack: normalizedPack, notes } = normalizePack(pack);
  const checks: CheckResult[] = [];

  const requiredKeys = ["target_year", "investment_amount", "shares", "total_shares", "per_multiples"] as const;
  for (const k of requiredKeys) {
    const a = getAssumption(normalizedPack, k);
    const ok =
      a?.valueType === "number"
        ? typeof a.numberValue === "number" && Number.isFinite(a.numberValue)
        : a?.valueType === "number_array"
          ? Array.isArray(a.numberArrayValue) && a.numberArrayValue.length > 0
          : false;
    if (!ok) checks.push({ check: "RequiredFieldsCheck", status: "fail", message: `필수 가정 누락/비어있음: ${k}` });
  }

  const hasInvestmentYear = typeof getAssumptionNumber(normalizedPack, "investment_year") === "number";
  const investmentDate = getAssumptionString(normalizedPack, "investment_date");
  let investYear = getAssumptionNumber(normalizedPack, "investment_year");
  if (!investYear && investmentDate) {
    const m = investmentDate.match(/^(\d{4})/);
    if (m) investYear = Number(m[1]);
  }
  if (!hasInvestmentYear && !investYear) {
    checks.push({
      check: "RequiredFieldsCheck",
      status: "fail",
      message: "investment_year 또는 YYYY-MM-DD 형태의 investment_date 중 하나가 필요합니다.",
    });
  }

  const hasNetIncome = typeof getAssumptionNumber(normalizedPack, "net_income_target_year") === "number";
  if (!hasNetIncome) {
    checks.push({ check: "RequiredFieldsCheck", status: "fail", message: "net_income_target_year(목표연도 순이익)가 필요합니다." });
  }

  // Year math check.
  const targetYear = getAssumptionNumber(normalizedPack, "target_year");
  // investYear is computed above.
  if (typeof targetYear === "number" && typeof investYear === "number") {
    const holding = targetYear - investYear;
    if (!Number.isFinite(holding) || holding <= 0) {
      checks.push({ check: "YearMathCheck", status: "fail", message: `보유기간 계산이 비정상입니다: target_year(${targetYear}) - investment_year(${investYear}) = ${holding}` });
    } else if (holding > 30) {
      checks.push({ check: "YearMathCheck", status: "warn", message: `보유기간이 깁니다(${holding}년). 연도 입력을 확인하세요.` });
    } else {
      checks.push({ check: "YearMathCheck", status: "pass", message: `보유기간: ${holding}년` });
    }
  }

  // Investment math check.
  const shares = getAssumptionNumber(normalizedPack, "shares");
  const pricePerShare = getAssumptionNumber(normalizedPack, "price_per_share");
  const investmentAmount = getAssumptionNumber(normalizedPack, "investment_amount");
  if (typeof shares === "number" && typeof pricePerShare === "number" && typeof investmentAmount === "number") {
    const implied = shares * pricePerShare;
    const diff = Math.abs(implied - investmentAmount);
    const ratio = investmentAmount ? diff / investmentAmount : 0;
    if (ratio >= 0.1) {
      checks.push({ check: "InvestmentMathCheck", status: "warn", message: `shares*price_per_share(${Math.round(implied)})와 investment_amount(${Math.round(investmentAmount)})가 10% 이상 차이납니다.` });
    } else {
      checks.push({ check: "InvestmentMathCheck", status: "pass", message: "투자금/주식수/주당가가 일관됩니다." });
    }
  } else if (typeof pricePerShare !== "number") {
    checks.push({ check: "InvestmentMathCheck", status: "warn", message: "price_per_share가 없어서 투자금 검증이 약합니다." });
  }

  // Evidence coverage check.
  const mustHaveEvidence = ["target_year", "investment_amount", "shares", "total_shares", "net_income_target_year", "per_multiples"];
  for (const k of mustHaveEvidence) {
    const a = getAssumption(normalizedPack, k);
    if (!a) continue;
    if (!hasEvidence(a.evidence)) {
      checks.push({ check: "EvidenceCoverageCheck", status: "warn", message: `근거 연결이 부족합니다: ${k} (factId 또는 note 필요)` });
    }
  }

  // Drift check (optional): compare with previous locked pack.
  if (prevLocked) {
    const driftKeys = ["investment_amount", "shares", "total_shares", "net_income_target_year"] as const;
    for (const k of driftKeys) {
      const prev = getAssumptionNumber(prevLocked, k);
      const cur = getAssumptionNumber(normalizedPack, k);
      if (typeof prev === "number" && typeof cur === "number" && prev > 0) {
        const ratio = cur / prev;
        if (ratio >= 2 || ratio <= 0.5) {
          checks.push({ check: "DriftCheck", status: "warn", message: `이전 locked pack 대비 ${k} 값이 크게 변했습니다(${prev} → ${cur}).` });
        }
      }
    }
  }

  // Add normalization notes.
  checks.push(...notes);

  const hasFail = checks.some((c) => c.status === "fail");
  const hasWarn = checks.some((c) => c.status === "warn");
  const status: ValidationStatus = hasFail ? "fail" : hasWarn ? "warn" : "pass";
  return { status, checks, normalizedPack };
}
