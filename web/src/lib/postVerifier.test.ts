import { describe, it, expect } from "vitest";
import {
  extractNumbersFromText,
  buildTrustedPool,
  findUnverifiedClaims,
  annotateUnverifiedClaims,
} from "./postVerifier";

describe("extractNumbersFromText", () => {
  it("extracts plain numbers", () => {
    const nums = extractNumbersFromText("투자금액 300,000,000원");
    expect(nums.has(300000000)).toBe(true);
  });

  it("extracts Korean unit numbers", () => {
    const nums = extractNumbersFromText("매출 100억원, 시장규모 2.8조");
    expect(nums.has(100e8)).toBe(true);
    expect(nums.has(2.8e12)).toBe(true);
  });

  it("extracts percentages", () => {
    const nums = extractNumbersFromText("IRR 28.5%");
    expect(nums.has(28.5)).toBe(true);
  });

  it("extracts multiples", () => {
    const nums = extractNumbersFromText("PER 10x, Multiple 3.2배");
    expect(nums.has(10)).toBe(true);
    expect(nums.has(3.2)).toBe(true);
  });

  it("extracts dollar amounts", () => {
    const nums = extractNumbersFromText("시장규모 $200B");
    expect(nums.has(200)).toBe(true);
  });
});

describe("buildTrustedPool", () => {
  it("combines numbers from all sources", () => {
    const pool = buildTrustedPool({
      assumptionPackSummary: "투자금액: 300000000\nPER: 10",
      computeSnapshotSummary: "IRR 28.5%, Multiple 3.2x",
    });
    expect(pool.numbers.has(300000000)).toBe(true);
    expect(pool.numbers.has(28.5)).toBe(true);
    expect(pool.numbers.has(3.2)).toBe(true);
  });

  it("includes years as safe", () => {
    const pool = buildTrustedPool({});
    expect(pool.numbers.has(2025)).toBe(true);
    expect(pool.numbers.has(2030)).toBe(true);
  });
});

describe("findUnverifiedClaims", () => {
  it("flags numbers not in trusted pool", () => {
    const pool = buildTrustedPool({
      assumptionPackSummary: "투자금액: 300000000",
    });
    const text = "글로벌 AI 반도체 시장은 2030년 $200B 규모입니다.";
    const claims = findUnverifiedClaims(text, pool);
    expect(claims.length).toBeGreaterThan(0);
    expect(claims[0].numbers.some(n => n === 200)).toBe(true);
  });

  it("does not flag trusted numbers", () => {
    const pool = buildTrustedPool({
      assumptionPackSummary: "투자금액: 300000000\nIRR: 28.5",
    });
    const text = "투자금액은 300,000,000원이고 IRR은 28.5%입니다.";
    const claims = findUnverifiedClaims(text, pool);
    expect(claims.length).toBe(0);
  });

  it("ignores small numbers and years", () => {
    const pool = buildTrustedPool({});
    const text = "2025년에 설립된 회사로, 팀원 6명이 근무합니다.";
    const claims = findUnverifiedClaims(text, pool);
    expect(claims.length).toBe(0);
  });
});

describe("annotateUnverifiedClaims", () => {
  it("adds [확인 필요] to unverified claims", () => {
    const pool = buildTrustedPool({
      assumptionPackSummary: "투자금액: 300000000",
    });
    const text = "글로벌 AI 반도체 시장은 2030년 $200B 규모이다.";
    const { annotated, claimCount } = annotateUnverifiedClaims(text, pool);
    expect(annotated).toContain("[확인 필요]");
    expect(claimCount).toBeGreaterThan(0);
  });

  it("does not modify text with only trusted numbers", () => {
    const pool = buildTrustedPool({
      assumptionPackSummary: "투자금액: 300000000",
      computeSnapshotSummary: "IRR: 28.5",
    });
    const text = "투자금액 3억원, IRR 28.5%입니다.";
    const { annotated, claimCount } = annotateUnverifiedClaims(text, pool);
    expect(claimCount).toBe(0);
    expect(annotated).toBe(text);
  });

  it("does not double-tag already tagged sentences", () => {
    const pool = buildTrustedPool({});
    const text = "시장규모 $500B [확인 필요]";
    const { annotated } = annotateUnverifiedClaims(text, pool);
    const count = (annotated.match(/\[확인 필요\]/g) || []).length;
    expect(count).toBe(1);
  });
});
