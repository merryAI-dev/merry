import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { sendMock } = vi.hoisted(() => ({
  sendMock: vi.fn(),
}));

vi.mock("@/lib/aws/ddb", () => ({
  getDdbDocClient: () => ({ send: sendMock }),
}));

import { getReviewQueueRecord, listReviewQueueRecords } from "./reviewQueue";

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

describe("reviewQueue review table routing", () => {
  it("uses MERRY_REVIEW_DDB_TABLE for queue record reads", async () => {
    await getReviewQueueRecord("team-1", "queue-1");

    expect(sendMock).toHaveBeenCalledTimes(1);
    expect(sendMock.mock.calls[0][0].input.TableName).toBe("merry-review");
    expect(sendMock.mock.calls[0][0].input.TableName).not.toBe("merry-main");
  });

  it("keeps scanning older index pages until it finds enough filtered matches", async () => {
    sendMock
      .mockResolvedValueOnce({
        Items: [
          { queue_id: "queue-ignore-1", status: "resolved_correct", queue_reason: "alias_correction" },
          { queue_id: "queue-ignore-2", status: "suppressed", queue_reason: "task_error" },
        ],
        LastEvaluatedKey: { pk: "TEAM#team-1#REVIEW_QUEUE", sk: "cursor-1" },
      })
      .mockResolvedValueOnce({
        Items: [
          { queue_id: "queue-1", status: "queued", queue_reason: "parse_warning" },
          { queue_id: "queue-2", status: "queued", queue_reason: "parse_warning" },
        ],
      })
      .mockResolvedValueOnce({
        Item: {
          queue_id: "queue-1",
          job_id: "job-1",
          task_id: "task-1",
          file_id: "file-1",
          filename: "one.pdf",
          company_group_key: "acme",
          company_group_name: "Acme",
          job_title: "조건 검사",
          policy_id: "policy-1",
          policy_text: "정책",
          queue_reason: "parse_warning",
          severity: "medium",
          status: "queued",
          evidence: "근거",
          parse_warning: "warn",
          error: "",
          alias_from: "",
          created_at: "2026-04-01T00:00:00.000Z",
          updated_at: "2026-04-01T00:00:00.000Z",
        },
      })
      .mockResolvedValueOnce({
        Item: {
          queue_id: "queue-2",
          job_id: "job-2",
          task_id: "task-2",
          file_id: "file-2",
          filename: "two.pdf",
          company_group_key: "beta",
          company_group_name: "Beta",
          job_title: "조건 검사",
          policy_id: "policy-2",
          policy_text: "정책",
          queue_reason: "parse_warning",
          severity: "high",
          status: "queued",
          evidence: "근거",
          parse_warning: "warn",
          error: "",
          alias_from: "",
          created_at: "2026-04-02T00:00:00.000Z",
          updated_at: "2026-04-02T00:00:00.000Z",
        },
      });

    const result = await listReviewQueueRecords("team-1", {
      status: "queued",
      reason: "parse_warning",
      limit: 2,
    });

    expect(result.items.map((item) => item.queueId)).toEqual(["queue-1", "queue-2"]);
    expect(result.hasMore).toBe(false);
    expect(result.nextCursor).toBeNull();
    expect(sendMock.mock.calls[0][0].input.TableName).toBe("merry-review");
    expect(sendMock.mock.calls[1][0].input.ExclusiveStartKey).toEqual({ pk: "TEAM#team-1#REVIEW_QUEUE", sk: "cursor-1" });
  });

  it("preserves overflow matches in nextCursor so older matching rows remain reachable", async () => {
    sendMock
      .mockResolvedValueOnce({
        Items: [
          { queue_id: "queue-1", status: "queued", queue_reason: "parse_warning" },
          { queue_id: "queue-2", status: "queued", queue_reason: "parse_warning" },
          { queue_id: "queue-3", status: "queued", queue_reason: "parse_warning" },
        ],
        LastEvaluatedKey: { pk: "TEAM#team-1#REVIEW_QUEUE", sk: "cursor-1" },
      })
      .mockResolvedValueOnce({
        Item: {
          queue_id: "queue-1",
          job_id: "job-1",
          task_id: "task-1",
          file_id: "file-1",
          filename: "one.pdf",
          company_group_key: "acme",
          company_group_name: "Acme",
          job_title: "조건 검사",
          policy_id: "policy-1",
          policy_text: "정책",
          queue_reason: "parse_warning",
          severity: "medium",
          status: "queued",
          evidence: "근거",
          parse_warning: "warn",
          error: "",
          alias_from: "",
          created_at: "2026-04-01T00:00:00.000Z",
          updated_at: "2026-04-01T00:00:00.000Z",
        },
      })
      .mockResolvedValueOnce({
        Item: {
          queue_id: "queue-2",
          job_id: "job-2",
          task_id: "task-2",
          file_id: "file-2",
          filename: "two.pdf",
          company_group_key: "beta",
          company_group_name: "Beta",
          job_title: "조건 검사",
          policy_id: "policy-2",
          policy_text: "정책",
          queue_reason: "parse_warning",
          severity: "high",
          status: "queued",
          evidence: "근거",
          parse_warning: "warn",
          error: "",
          alias_from: "",
          created_at: "2026-04-02T00:00:00.000Z",
          updated_at: "2026-04-02T00:00:00.000Z",
        },
      })
      .mockResolvedValueOnce({
        Item: {
          queue_id: "queue-3",
          job_id: "job-3",
          task_id: "task-3",
          file_id: "file-3",
          filename: "three.pdf",
          company_group_key: "gamma",
          company_group_name: "Gamma",
          job_title: "조건 검사",
          policy_id: "policy-3",
          policy_text: "정책",
          queue_reason: "parse_warning",
          severity: "low",
          status: "queued",
          evidence: "근거",
          parse_warning: "warn",
          error: "",
          alias_from: "",
          created_at: "2026-04-03T00:00:00.000Z",
          updated_at: "2026-04-03T00:00:00.000Z",
        },
      });

    const firstPage = await listReviewQueueRecords("team-1", {
      status: "queued",
      reason: "parse_warning",
      limit: 2,
    });

    const secondPage = await listReviewQueueRecords("team-1", {
      status: "queued",
      reason: "parse_warning",
      limit: 1,
      cursor: firstPage.nextCursor ?? undefined,
    });

    expect(firstPage.items.map((item) => item.queueId)).toEqual(["queue-1", "queue-2"]);
    expect(firstPage.hasMore).toBe(true);
    expect(firstPage.nextCursor).toEqual(expect.any(String));
    expect(secondPage.items.map((item) => item.queueId)).toEqual(["queue-3"]);
  });
});
