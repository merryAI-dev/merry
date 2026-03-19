/**
 * Sanity checks and cross-validation for financial calculation results.
 */

export type ValidationWarning = {
  field: string;
  message: string;
  severity: "warn" | "error";
};

const RANGES: Record<string, { min?: number; max?: number; warnMsg: string }> = {
  irr: { min: -1, max: 10, warnMsg: "IRR이 -100%~1000% 범위를 벗어남" },
  multiple: { min: 0, max: 100, warnMsg: "Multiple이 0~100x 범위를 벗어남" },
  enterpriseValue: { min: 0, warnMsg: "기업가치가 음수" },
  proceeds: { min: 0, warnMsg: "회수금액이 음수" },
  npv: { min: 0, warnMsg: "NPV가 음수" },
  exercisePrice: { min: 0, warnMsg: "행사가가 음수" },
  totalProceeds: { min: 0, warnMsg: "총 회수금액이 음수" },
};

/** Check a single value against known ranges. */
export function checkRange(field: string, value: number): ValidationWarning | null {
  if (!Number.isFinite(value)) {
    return { field, message: `${field} 값이 유효하지 않음 (NaN/Infinity)`, severity: "error" };
  }
  const range = RANGES[field];
  if (!range) return null;
  if (range.min !== undefined && value < range.min) {
    return { field, message: range.warnMsg, severity: value < 0 ? "error" : "warn" };
  }
  if (range.max !== undefined && value > range.max) {
    return { field, message: range.warnMsg, severity: "warn" };
  }
  return null;
}

/** Validate all fields in a result object. */
export function validateResult(result: Record<string, unknown>): ValidationWarning[] {
  const warnings: ValidationWarning[] = [];
  for (const [key, value] of Object.entries(result)) {
    if (typeof value !== "number") continue;
    const w = checkRange(key, value);
    if (w) warnings.push(w);
  }
  return warnings;
}

/** Cross-validate: proceeds should equal perShareValue * shares. */
export function crossValidateProceeds(
  proceeds: number,
  perShareValue: number,
  shares: number,
  tolerance = 0.01,
): ValidationWarning | null {
  const expected = perShareValue * shares;
  if (expected === 0) return null;
  const diff = Math.abs(proceeds - expected) / Math.abs(expected);
  if (diff > tolerance) {
    return {
      field: "proceeds",
      message: `회수금액 역산 불일치: ${proceeds.toLocaleString()} vs 예상 ${expected.toLocaleString()} (차이 ${(diff * 100).toFixed(1)}%)`,
      severity: "warn",
    };
  }
  return null;
}

/** Cross-validate: multiple should equal proceeds / investmentAmount. */
export function crossValidateMultiple(
  multiple: number,
  proceeds: number,
  investmentAmount: number,
  tolerance = 0.01,
): ValidationWarning | null {
  if (investmentAmount === 0) return null;
  const expected = proceeds / investmentAmount;
  const diff = Math.abs(multiple - expected);
  if (diff > tolerance) {
    return {
      field: "multiple",
      message: `Multiple 역산 불일치: ${multiple.toFixed(2)}x vs 예상 ${expected.toFixed(2)}x`,
      severity: "warn",
    };
  }
  return null;
}

/** Validate inputs before calculation. */
export function validateInputs(params: Record<string, unknown>): ValidationWarning[] {
  const warnings: ValidationWarning[] = [];

  for (const [key, value] of Object.entries(params)) {
    if (typeof value !== "number") continue;
    if (!Number.isFinite(value)) {
      warnings.push({ field: key, message: `${key}이(가) 유효하지 않음`, severity: "error" });
    }
  }

  const holdingYears = params.holdingYears;
  if (typeof holdingYears === "number" && holdingYears <= 0) {
    warnings.push({ field: "holdingYears", message: "투자 기간이 0 이하", severity: "error" });
  }

  const investmentAmount = params.investmentAmount;
  if (typeof investmentAmount === "number" && investmentAmount <= 0) {
    warnings.push({ field: "investmentAmount", message: "투자금액이 0 이하", severity: "error" });
  }

  const totalShares = params.totalShares;
  if (typeof totalShares === "number" && totalShares <= 0) {
    warnings.push({ field: "totalShares", message: "총발행주식수가 0 이하", severity: "error" });
  }

  return warnings;
}
