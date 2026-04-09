import { beforeEach, afterEach, describe, expect, it } from "vitest";

import {
  getDdbTableName,
  getDiagnosisDdbTableName,
  getReviewDdbTableName,
} from "./env";

const ENV_KEYS = ["MERRY_DDB_TABLE", "MERRY_REVIEW_DDB_TABLE", "MERRY_DIAGNOSIS_DDB_TABLE"] as const;

let originalEnv: Partial<Record<(typeof ENV_KEYS)[number], string | undefined>> = {};

beforeEach(() => {
  originalEnv = {};
  for (const key of ENV_KEYS) {
    originalEnv[key] = process.env[key];
  }

  process.env.MERRY_DDB_TABLE = "merry-main";
  process.env.MERRY_REVIEW_DDB_TABLE = "merry-review";
  process.env.MERRY_DIAGNOSIS_DDB_TABLE = "merry-diagnosis";
});

afterEach(() => {
  for (const key of ENV_KEYS) {
    const value = originalEnv[key];
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }
});

describe("ddb table resolution", () => {
  it("keeps the shared table resolver on MERRY_DDB_TABLE", () => {
    expect(getDdbTableName()).toBe("merry-main");
  });

  it("resolves review and diagnosis tables separately", () => {
    expect(getReviewDdbTableName()).toBe("merry-review");
    expect(getDiagnosisDdbTableName()).toBe("merry-diagnosis");
  });

  it("falls back to the shared table for review when the dedicated table env is missing", () => {
    delete process.env.MERRY_REVIEW_DDB_TABLE;

    expect(getReviewDdbTableName()).toBe("merry-main");
  });

  it("throws a targeted error when a product table env is missing", () => {
    delete process.env.MERRY_DIAGNOSIS_DDB_TABLE;

    expect(() => getDiagnosisDdbTableName()).toThrow("Missing env MERRY_DIAGNOSIS_DDB_TABLE");
  });
});
