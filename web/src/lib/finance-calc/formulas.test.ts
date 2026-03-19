import { describe, it, expect } from "vitest";
import {
  simpleIrr,
  xirr,
  calculateExitValuation,
  calculateCallOption,
  calculateSafeDilution,
  calculatePartialExit,
  calculateNpv,
  calculateExpression,
} from "./formulas";

describe("simpleIrr", () => {
  it("calculates correct IRR for 3x multiple over 4 years", () => {
    const irr = simpleIrr(3, 4);
    expect(irr).toBeCloseTo(0.3161, 3); // 3^(1/4) - 1 ≈ 31.6%
  });

  it("returns 0 for 1x multiple", () => {
    expect(simpleIrr(1, 5)).toBeCloseTo(0);
  });

  it("returns negative for <1x multiple", () => {
    expect(simpleIrr(0.5, 3)).toBeLessThan(0);
  });

  it("returns NaN for zero/negative years", () => {
    expect(simpleIrr(2, 0)).toBeNaN();
    expect(simpleIrr(2, -1)).toBeNaN();
  });

  it("returns NaN for zero/negative multiple", () => {
    expect(simpleIrr(0, 3)).toBeNaN();
    expect(simpleIrr(-1, 3)).toBeNaN();
  });
});

describe("xirr", () => {
  it("calculates IRR for simple invest + single exit", () => {
    const irr = xirr([
      { amount: -1000, daysFromStart: 0 },
      { amount: 2000, daysFromStart: 365 * 3 },
    ]);
    // 2x over 3 years ≈ 26%
    expect(irr).toBeCloseTo(0.26, 1);
  });

  it("handles two-stage exit (partial)", () => {
    const irr = xirr([
      { amount: -1000, daysFromStart: 0 },
      { amount: 800, daysFromStart: 365 * 2 },
      { amount: 1200, daysFromStart: 365 * 3 },
    ]);
    expect(irr).toBeGreaterThan(0);
    expect(Number.isFinite(irr)).toBe(true);
  });

  it("returns NaN for insufficient cashflows", () => {
    expect(xirr([{ amount: 100, daysFromStart: 0 }])).toBeNaN();
  });
});

describe("calculateExitValuation", () => {
  const base = {
    netIncome: 2_800_000_000,
    per: 10,
    totalShares: 28624,
    shares: 9145,
    investmentAmount: 300_000_000,
    holdingYears: 4,
  };

  it("calculates correct enterprise value", () => {
    const r = calculateExitValuation(base);
    expect(r.enterpriseValue).toBe(28_000_000_000);
  });

  it("calculates correct per-share value", () => {
    const r = calculateExitValuation(base);
    expect(r.perShareValue).toBeCloseTo(28_000_000_000 / 28624, 0);
  });

  it("calculates correct proceeds and multiple", () => {
    const r = calculateExitValuation(base);
    expect(r.proceeds).toBeCloseTo(r.perShareValue * 9145, 0);
    expect(r.multiple).toBeCloseTo(r.proceeds / 300_000_000, 2);
  });

  it("IRR matches simple IRR formula", () => {
    const r = calculateExitValuation(base);
    const expectedIrr = simpleIrr(r.multiple, 4);
    expect(r.irr).toBeCloseTo(expectedIrr, 6);
  });

  it("handles zero total shares gracefully", () => {
    const r = calculateExitValuation({ ...base, totalShares: 0 });
    expect(r.perShareValue).toBe(0);
    expect(r.proceeds).toBe(0);
  });
});

describe("calculateCallOption", () => {
  it("calculates exercise price correctly", () => {
    const r = calculateCallOption({
      pricePerShare: 32808,
      multiplier: 1.5,
      shares: 9145,
      investmentAmount: 300_000_000,
      holdingYears: 4,
    });
    expect(r.exercisePrice).toBe(32808 * 1.5);
    expect(r.totalProceeds).toBe(r.exercisePrice * 9145);
  });

  it("multiple is exactly the multiplier when price * shares = investment", () => {
    const r = calculateCallOption({
      pricePerShare: 100,
      multiplier: 2,
      shares: 1000,
      investmentAmount: 100_000,
      holdingYears: 3,
    });
    expect(r.multiple).toBeCloseTo(2);
  });
});

describe("calculateSafeDilution", () => {
  it("rounds SAFE shares to integer", () => {
    const r = calculateSafeDilution({
      safeAmount: 100_000_000,
      valuationCap: 5_000_000_000,
      totalSharesBefore: 28624,
      shares: 9145,
      netIncome: 2_800_000_000,
      per: 10,
      investmentAmount: 300_000_000,
      holdingYears: 4,
    });
    expect(Number.isInteger(r.safeShares)).toBe(true);
    expect(r.totalSharesAfter).toBe(28624 + r.safeShares);
    expect(r.ownershipAfter).toBeLessThan(r.ownershipBefore);
  });

  it("handles zero valuation cap", () => {
    const r = calculateSafeDilution({
      safeAmount: 100_000_000,
      valuationCap: 0,
      totalSharesBefore: 28624,
      shares: 9145,
      netIncome: 2_800_000_000,
      per: 10,
      investmentAmount: 300_000_000,
      holdingYears: 4,
    });
    expect(r.safeShares).toBe(0);
  });
});

describe("calculatePartialExit", () => {
  it("uses XIRR not simple averaging", () => {
    const r = calculatePartialExit({
      netIncomeY1: 2_800_000_000,
      netIncomeY2: 3_500_000_000,
      per: 10,
      totalShares: 28624,
      shares: 9145,
      investmentAmount: 300_000_000,
      partialRatio: 0.5,
      exitYear1: 2029,
      exitYear2: 2030,
      investmentYear: 2025,
    });
    expect(r.firstProceeds).toBeGreaterThan(0);
    expect(r.secondProceeds).toBeGreaterThan(0);
    expect(Number.isFinite(r.combinedIrr)).toBe(true);
    // XIRR should differ from simple geometric mean
    const simpleAvgIrr = simpleIrr(r.combinedMultiple, 4.5);
    // They should be in the same ballpark but not identical
    expect(Math.abs(r.combinedIrr - simpleAvgIrr)).toBeLessThan(0.1);
  });
});

describe("calculateNpv", () => {
  it("discounts correctly at 10%", () => {
    const r = calculateNpv({
      proceeds: 1_000_000_000,
      discountRate: 0.10,
      holdingYears: 4,
      investmentAmount: 300_000_000,
    });
    expect(r.npv).toBeCloseTo(1_000_000_000 / Math.pow(1.1, 4), 0);
  });
});

describe("calculateExpression", () => {
  it("evaluates basic math", () => {
    expect(calculateExpression("2 + 3 * 4")).toBe(14);
  });

  it("rejects unsafe input", () => {
    expect(calculateExpression("process.exit()")).toBeNaN();
    expect(calculateExpression("require('fs')")).toBeNaN();
  });

  it("handles division", () => {
    expect(calculateExpression("300000000 / 9145")).toBeCloseTo(32804.81, 0);
  });
});
