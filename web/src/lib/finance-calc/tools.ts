/**
 * Finance calculation tool definitions.
 * Each tool: validate inputs → compute → validate results → return with warnings.
 */

import {
  calculateExitValuation,
  calculateCallOption,
  calculateSafeDilution,
  calculatePartialExit,
  calculateNpv,
  calculateExpression,
} from "./formulas";
import { validateInputs, validateResult, crossValidateProceeds, crossValidateMultiple, type ValidationWarning } from "./validators";

export type ToolResult<T = Record<string, unknown>> = {
  ok: boolean;
  result?: T;
  warnings?: ValidationWarning[];
  error?: string;
};

function fmt(n: number, decimals = 2): string {
  if (!Number.isFinite(n)) return "N/A";
  return n.toLocaleString("ko-KR", { maximumFractionDigits: decimals });
}

function fmtPct(n: number): string {
  if (!Number.isFinite(n)) return "N/A";
  return (n * 100).toFixed(1) + "%";
}

function fmtKrw(n: number): string {
  if (!Number.isFinite(n)) return "N/A";
  if (Math.abs(n) >= 1e8) return fmt(n / 1e8) + "억원";
  if (Math.abs(n) >= 1e4) return fmt(n / 1e4) + "만원";
  return fmt(n) + "원";
}

export function runExitValuation(params: {
  netIncome: number;
  per: number;
  totalShares: number;
  shares: number;
  investmentAmount: number;
  holdingYears: number;
}): ToolResult {
  const inputWarnings = validateInputs(params);
  if (inputWarnings.some((w) => w.severity === "error")) {
    return { ok: false, error: inputWarnings.map((w) => w.message).join("; "), warnings: inputWarnings };
  }

  const r = calculateExitValuation(params);
  const warnings = [...inputWarnings, ...validateResult(r)];

  const cv1 = crossValidateProceeds(r.proceeds, r.perShareValue, params.shares);
  if (cv1) warnings.push(cv1);
  const cv2 = crossValidateMultiple(r.multiple, r.proceeds, params.investmentAmount);
  if (cv2) warnings.push(cv2);

  return {
    ok: true,
    result: {
      ...r,
      summary: `PER ${params.per}x 기준: 기업가치 ${fmtKrw(r.enterpriseValue)}, 주당가치 ${fmt(r.perShareValue)}원, 회수금액 ${fmtKrw(r.proceeds)}, Multiple ${fmt(r.multiple)}x, IRR ${fmtPct(r.irr)}`,
    },
    warnings: warnings.length ? warnings : undefined,
  };
}

export function runCallOption(params: {
  pricePerShare: number;
  multiplier: number;
  shares: number;
  investmentAmount: number;
  holdingYears: number;
}): ToolResult {
  const inputWarnings = validateInputs(params);
  if (inputWarnings.some((w) => w.severity === "error")) {
    return { ok: false, error: inputWarnings.map((w) => w.message).join("; "), warnings: inputWarnings };
  }

  const r = calculateCallOption(params);
  const warnings = [...inputWarnings, ...validateResult(r)];

  return {
    ok: true,
    result: {
      ...r,
      summary: `콜옵션 ${params.multiplier}x 행사: 행사가 ${fmt(r.exercisePrice)}원, 회수금액 ${fmtKrw(r.totalProceeds)}, Multiple ${fmt(r.multiple)}x, IRR ${fmtPct(r.irr)}`,
    },
    warnings: warnings.length ? warnings : undefined,
  };
}

export function runSafeDilution(params: {
  safeAmount: number;
  valuationCap: number;
  totalSharesBefore: number;
  shares: number;
  netIncome: number;
  per: number;
  investmentAmount: number;
  holdingYears: number;
}): ToolResult {
  const inputWarnings = validateInputs(params);
  if (inputWarnings.some((w) => w.severity === "error")) {
    return { ok: false, error: inputWarnings.map((w) => w.message).join("; "), warnings: inputWarnings };
  }

  const r = calculateSafeDilution(params);
  const warnings = [...inputWarnings, ...validateResult(r)];

  return {
    ok: true,
    result: {
      ...r,
      summary: `SAFE 전환: ${r.safeShares}주 신규 발행, 총주식수 ${r.totalSharesAfter}주, 지분율 ${fmtPct(r.ownershipBefore)} → ${fmtPct(r.ownershipAfter)}, 희석 후 Multiple ${fmt(r.dilutedMultiple)}x, IRR ${fmtPct(r.dilutedIrr)}`,
    },
    warnings: warnings.length ? warnings : undefined,
  };
}

export function runPartialExit(params: {
  netIncomeY1: number;
  netIncomeY2: number;
  per: number;
  totalShares: number;
  shares: number;
  investmentAmount: number;
  partialRatio: number;
  exitYear1: number;
  exitYear2: number;
  investmentYear: number;
}): ToolResult {
  const inputWarnings = validateInputs(params);
  if (inputWarnings.some((w) => w.severity === "error")) {
    return { ok: false, error: inputWarnings.map((w) => w.message).join("; "), warnings: inputWarnings };
  }

  const r = calculatePartialExit(params);
  const warnings = [...inputWarnings, ...validateResult(r)];

  return {
    ok: true,
    result: {
      ...r,
      summary: `부분매각 (${(params.partialRatio * 100).toFixed(0)}/${((1 - params.partialRatio) * 100).toFixed(0)}): 1차 ${fmtKrw(r.firstProceeds)} (${params.exitYear1}), 2차 ${fmtKrw(r.secondProceeds)} (${params.exitYear2}), 총 ${fmtKrw(r.totalProceeds)}, Multiple ${fmt(r.combinedMultiple)}x, XIRR ${fmtPct(r.combinedIrr)}`,
    },
    warnings: warnings.length ? warnings : undefined,
  };
}

export function runNpv(params: {
  proceeds: number;
  discountRate: number;
  holdingYears: number;
  investmentAmount: number;
}): ToolResult {
  const inputWarnings = validateInputs(params);
  if (inputWarnings.some((w) => w.severity === "error")) {
    return { ok: false, error: inputWarnings.map((w) => w.message).join("; "), warnings: inputWarnings };
  }

  const r = calculateNpv(params);
  const warnings = [...inputWarnings, ...validateResult(r)];

  return {
    ok: true,
    result: {
      ...r,
      summary: `NPV (할인율 ${(params.discountRate * 100).toFixed(0)}%): NPV ${fmtKrw(r.npv)}, NPV Multiple ${fmt(r.npvMultiple)}x, NPV IRR ${fmtPct(r.npvIrr)}`,
    },
    warnings: warnings.length ? warnings : undefined,
  };
}

export function runExpression(expression: string): ToolResult {
  const result = calculateExpression(expression);
  if (!Number.isFinite(result)) {
    return { ok: false, error: `수식 계산 실패: ${expression}` };
  }
  return { ok: true, result: { value: result, expression, summary: `${expression} = ${fmt(result, 6)}` } };
}

/** Dispatch a tool call by name. */
export function dispatchTool(toolName: string, params: Record<string, unknown>): ToolResult {
  switch (toolName) {
    case "calculate_exit_valuation":
      return runExitValuation(params as Parameters<typeof runExitValuation>[0]);
    case "calculate_call_option":
      return runCallOption(params as Parameters<typeof runCallOption>[0]);
    case "calculate_safe_dilution":
      return runSafeDilution(params as Parameters<typeof runSafeDilution>[0]);
    case "calculate_partial_exit":
      return runPartialExit(params as Parameters<typeof runPartialExit>[0]);
    case "calculate_npv":
      return runNpv(params as Parameters<typeof runNpv>[0]);
    case "calculate_expression":
      return runExpression(params.expression as string);
    default:
      return { ok: false, error: `알 수 없는 도구: ${toolName}` };
  }
}
