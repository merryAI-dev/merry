import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  DEFAULT_AFTER_LOGIN_PATH,
  PRODUCTS,
  getProductBySlug,
  getVisibleProducts,
  productNavLabel,
} from "./products";

describe("products", () => {
  const originalRollout = process.env.MERRY_DIAGNOSIS_ROLLOUT;
  const originalInternalTeams = process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS;

  beforeEach(() => {
    process.env.MERRY_DIAGNOSIS_ROLLOUT = originalRollout;
    process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS = originalInternalTeams;
  });

  afterEach(() => {
    if (originalRollout === undefined) delete process.env.MERRY_DIAGNOSIS_ROLLOUT;
    else process.env.MERRY_DIAGNOSIS_ROLLOUT = originalRollout;

    if (originalInternalTeams === undefined) delete process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS;
    else process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS = originalInternalTeams;
  });

  it("defines only review and diagnosis as top-level products", () => {
    expect(PRODUCTS.map((product) => product.slug)).toEqual(["review", "diagnosis"]);
    expect(PRODUCTS.map((product) => product.href)).toEqual(["/review", "/diagnosis"]);
  });

  it("routes authenticated users to the product chooser", () => {
    expect(DEFAULT_AFTER_LOGIN_PATH).toBe("/products");
  });

  it("returns Korean labels for the chooser cards", () => {
    expect(productNavLabel("review")).toBe("투자심사");
    expect(productNavLabel("diagnosis")).toBe("현황진단");
  });

  it("throws on unknown product slugs", () => {
    expect(() => getProductBySlug("analysis")).toThrow(/Unknown product/);
  });

  it("keeps diagnosis visible for all teams by default", () => {
    delete process.env.MERRY_DIAGNOSIS_ROLLOUT;
    delete process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS;

    expect(getVisibleProducts({ teamId: "team-all", memberName: "kim" }).map((product) => product.slug)).toEqual([
      "review",
      "diagnosis",
    ]);
  });

  it("limits diagnosis to internal teams when rollout is internal", () => {
    process.env.MERRY_DIAGNOSIS_ROLLOUT = "internal";
    process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS = "team-alpha, team-beta";

    expect(getVisibleProducts({ teamId: "team-alpha", memberName: "lee" }).map((product) => product.slug)).toEqual([
      "review",
      "diagnosis",
    ]);
    expect(getVisibleProducts({ teamId: "team-gamma", memberName: "park" }).map((product) => product.slug)).toEqual([
      "review",
    ]);
  });

  it("can disable diagnosis entirely", () => {
    process.env.MERRY_DIAGNOSIS_ROLLOUT = "off";
    delete process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS;

    expect(getVisibleProducts({ teamId: "team-off", memberName: "choi" }).map((product) => product.slug)).toEqual([
      "review",
    ]);
  });
});
