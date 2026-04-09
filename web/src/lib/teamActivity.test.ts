import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { sendMock } = vi.hoisted(() => ({
  sendMock: vi.fn(),
}));

vi.mock("@/lib/aws/ddb", () => ({
  getDdbDocClient: () => ({ send: sendMock }),
}));

import { getRecentActivity } from "./teamActivity";

const ENV_KEYS = ["MERRY_DDB_TABLE", "MERRY_REVIEW_DDB_TABLE"] as const;

let originalEnv: Partial<Record<(typeof ENV_KEYS)[number], string | undefined>> = {};

beforeEach(() => {
  originalEnv = {};
  for (const key of ENV_KEYS) {
    originalEnv[key] = process.env[key];
  }

  process.env.MERRY_DDB_TABLE = "merry-main";
  process.env.MERRY_REVIEW_DDB_TABLE = "merry-review";
  sendMock.mockReset();
  sendMock.mockResolvedValue({ Items: [] });
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

describe("teamActivity review table routing", () => {
  it("uses MERRY_REVIEW_DDB_TABLE for activity queries", async () => {
    await getRecentActivity("team-1");

    expect(sendMock).toHaveBeenCalledTimes(1);
    expect(sendMock.mock.calls[0][0].input.TableName).toBe("merry-review");
    expect(sendMock.mock.calls[0][0].input.TableName).not.toBe("merry-main");
  });
});
