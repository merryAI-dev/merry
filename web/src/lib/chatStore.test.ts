import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { sendMock } = vi.hoisted(() => ({
  sendMock: vi.fn(),
}));

vi.mock("@/lib/aws/ddb", () => ({
  getDdbDocClient: () => ({ send: sendMock }),
}));

import { getSession } from "./chatStore";

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
  sendMock.mockResolvedValue({ Item: undefined });
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

describe("chatStore review table routing", () => {
  it("uses MERRY_REVIEW_DDB_TABLE for session reads", async () => {
    await getSession("team-1", "session-1");

    expect(sendMock).toHaveBeenCalledTimes(1);
    expect(sendMock.mock.calls[0][0].input.TableName).toBe("merry-review");
    expect(sendMock.mock.calls[0][0].input.TableName).not.toBe("merry-main");
  });

  it("falls back to MERRY_DDB_TABLE when the dedicated review table env is missing", async () => {
    delete process.env.MERRY_REVIEW_DDB_TABLE;

    await getSession("team-1", "session-1");

    expect(sendMock).toHaveBeenCalledTimes(1);
    expect(sendMock.mock.calls[0][0].input.TableName).toBe("merry-main");
  });
});
