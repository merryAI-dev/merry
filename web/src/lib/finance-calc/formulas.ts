/**
 * Pure financial calculation functions for VC investment analysis.
 * No side effects, no I/O — fully testable.
 */

/** Simple IRR: compound annual growth rate. */
export function simpleIrr(multiple: number, years: number): number {
  if (!Number.isFinite(multiple) || !Number.isFinite(years)) return NaN;
  if (years <= 0 || multiple <= 0) return NaN;
  return Math.pow(multiple, 1 / years) - 1;
}

/**
 * XIRR: Internal rate of return for irregular cash flows.
 * Uses Newton-Raphson iteration.
 */
export function xirr(
  cashflows: { amount: number; daysFromStart: number }[],
  guess = 0.1,
  maxIter = 100,
  tolerance = 1e-7,
): number {
  if (cashflows.length < 2) return NaN;

  let rate = guess;
  for (let i = 0; i < maxIter; i++) {
    let npv = 0;
    let dnpv = 0;
    for (const cf of cashflows) {
      const t = cf.daysFromStart / 365;
      const factor = Math.pow(1 + rate, t);
      if (!Number.isFinite(factor) || factor === 0) break;
      npv += cf.amount / factor;
      dnpv -= (t * cf.amount) / (factor * (1 + rate));
    }
    if (!Number.isFinite(npv) || !Number.isFinite(dnpv) || dnpv === 0) return NaN;
    const next = rate - npv / dnpv;
    if (Math.abs(next - rate) < tolerance) return next;
    rate = next;
  }
  return NaN; // did not converge
}

/** PER-based exit valuation. */
export function calculateExitValuation(params: {
  netIncome: number;
  per: number;
  totalShares: number;
  shares: number;
  investmentAmount: number;
  holdingYears: number;
}): {
  enterpriseValue: number;
  perShareValue: number;
  proceeds: number;
  multiple: number;
  irr: number;
} {
  const { netIncome, per, totalShares, shares, investmentAmount, holdingYears } = params;

  const enterpriseValue = netIncome * per;
  const perShareValue = totalShares > 0 ? enterpriseValue / totalShares : 0;
  const proceeds = perShareValue * shares;
  const multiple = investmentAmount > 0 ? proceeds / investmentAmount : 0;
  const irr = simpleIrr(multiple, holdingYears);

  return { enterpriseValue, perShareValue, proceeds, multiple, irr };
}

/** Call option exercise calculation. */
export function calculateCallOption(params: {
  pricePerShare: number;
  multiplier: number;
  shares: number;
  investmentAmount: number;
  holdingYears: number;
}): {
  exercisePrice: number;
  totalProceeds: number;
  multiple: number;
  irr: number;
} {
  const { pricePerShare, multiplier, shares, investmentAmount, holdingYears } = params;

  const exercisePrice = pricePerShare * multiplier;
  const totalProceeds = exercisePrice * shares;
  const multiple = investmentAmount > 0 ? totalProceeds / investmentAmount : 0;
  const irr = simpleIrr(multiple, holdingYears);

  return { exercisePrice, totalProceeds, multiple, irr };
}

/** SAFE conversion dilution calculation. */
export function calculateSafeDilution(params: {
  safeAmount: number;
  valuationCap: number;
  totalSharesBefore: number;
  shares: number;
  netIncome: number;
  per: number;
  investmentAmount: number;
  holdingYears: number;
}): {
  safeShares: number;
  totalSharesAfter: number;
  ownershipBefore: number;
  ownershipAfter: number;
  dilutedPerShareValue: number;
  dilutedProceeds: number;
  dilutedMultiple: number;
  dilutedIrr: number;
} {
  const { safeAmount, valuationCap, totalSharesBefore, shares, netIncome, per, investmentAmount, holdingYears } = params;

  const safeShares = valuationCap > 0
    ? Math.round((safeAmount / valuationCap) * totalSharesBefore)
    : 0;
  const totalSharesAfter = totalSharesBefore + safeShares;
  const ownershipBefore = totalSharesBefore > 0 ? shares / totalSharesBefore : 0;
  const ownershipAfter = totalSharesAfter > 0 ? shares / totalSharesAfter : 0;

  const enterpriseValue = netIncome * per;
  const dilutedPerShareValue = totalSharesAfter > 0 ? enterpriseValue / totalSharesAfter : 0;
  const dilutedProceeds = dilutedPerShareValue * shares;
  const dilutedMultiple = investmentAmount > 0 ? dilutedProceeds / investmentAmount : 0;
  const dilutedIrr = simpleIrr(dilutedMultiple, holdingYears);

  return {
    safeShares,
    totalSharesAfter,
    ownershipBefore,
    ownershipAfter,
    dilutedPerShareValue,
    dilutedProceeds,
    dilutedMultiple,
    dilutedIrr,
  };
}

/** Partial exit (two-stage) calculation using XIRR. */
export function calculatePartialExit(params: {
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
}): {
  firstProceeds: number;
  secondProceeds: number;
  totalProceeds: number;
  combinedMultiple: number;
  combinedIrr: number;
} {
  const { netIncomeY1, netIncomeY2, per, totalShares, shares, investmentAmount, partialRatio, exitYear1, exitYear2, investmentYear } = params;

  const ev1 = netIncomeY1 * per;
  const ev2 = netIncomeY2 * per;
  const sp1 = totalShares > 0 ? ev1 / totalShares : 0;
  const sp2 = totalShares > 0 ? ev2 / totalShares : 0;

  const firstProceeds = sp1 * shares * partialRatio;
  const secondProceeds = sp2 * shares * (1 - partialRatio);
  const totalProceeds = firstProceeds + secondProceeds;
  const combinedMultiple = investmentAmount > 0 ? totalProceeds / investmentAmount : 0;

  // Use XIRR for accurate IRR with two exit dates
  const combinedIrr = xirr([
    { amount: -investmentAmount, daysFromStart: 0 },
    { amount: firstProceeds, daysFromStart: (exitYear1 - investmentYear) * 365 },
    { amount: secondProceeds, daysFromStart: (exitYear2 - investmentYear) * 365 },
  ]);

  return { firstProceeds, secondProceeds, totalProceeds, combinedMultiple, combinedIrr };
}

/** NPV analysis. */
export function calculateNpv(params: {
  proceeds: number;
  discountRate: number;
  holdingYears: number;
  investmentAmount: number;
}): {
  npv: number;
  npvMultiple: number;
  npvIrr: number;
} {
  const { proceeds, discountRate, holdingYears, investmentAmount } = params;

  const npv = holdingYears > 0 ? proceeds / Math.pow(1 + discountRate, holdingYears) : proceeds;
  const npvMultiple = investmentAmount > 0 ? npv / investmentAmount : 0;
  const npvIrr = simpleIrr(npvMultiple, holdingYears);

  return { npv, npvMultiple, npvIrr };
}

/** Evaluate a safe math expression (no eval, basic operations only). */
export function calculateExpression(expression: string): number {
  // Only allow digits, operators, parentheses, decimals, spaces, and common math functions
  const sanitized = expression.trim();
  if (!/^[\d\s+\-*/().,%eE]+$/.test(sanitized)) {
    return NaN;
  }
  try {
    // Use Function constructor with restricted scope
    const fn = new Function("return (" + sanitized + ")");
    const result = fn();
    return typeof result === "number" && Number.isFinite(result) ? result : NaN;
  } catch {
    return NaN;
  }
}
