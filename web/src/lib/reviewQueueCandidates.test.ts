import assert from "node:assert/strict";
import test from "node:test";

import { deriveReviewQueueCandidates } from "./reviewQueueCandidates.ts";

test("deriveReviewQueueCandidates emits parse warning, alias correction, and missing evidence", () => {
  const candidates = deriveReviewQueueCandidates(
    { jobId: "job1", title: "조건 검사" } as const,
    [
      {
        taskId: "000",
        jobId: "job1",
        teamId: "team1",
        taskIndex: 0,
        status: "succeeded",
        fileId: "file1",
        createdAt: "2026-03-10T00:00:00.000Z",
        result: {
          filename: "alpha.pdf",
          company_group_name: "스트레스솔루션",
          company_group_key: "stress",
          company_group_alias_from: "스트레",
          parse_warning: "JSON 응답 일부를 복구했습니다.",
          conditions: [
            { condition: "업력 3년 미만", result: true, evidence: "짧음" },
          ],
        },
      },
    ],
  );

  assert.equal(candidates.length, 3);
  assert.ok(candidates.some((item) => item.queueReason === "parse_warning"));
  assert.ok(candidates.some((item) => item.queueReason === "alias_correction"));
  assert.ok(candidates.some((item) => item.queueReason === "evidence_missing"));
});

test("deriveReviewQueueCandidates emits company_unrecognized and task_error", () => {
  const candidates = deriveReviewQueueCandidates(
    { jobId: "job2", title: "조건 검사" } as const,
    [
      {
        taskId: "001",
        jobId: "job2",
        teamId: "team1",
        taskIndex: 1,
        status: "failed",
        fileId: "file2",
        createdAt: "2026-03-10T00:00:00.000Z",
        error: "PARSE_FAILED",
        result: {
          filename: "beta.pdf",
          conditions: [],
        },
      },
    ],
  );

  assert.ok(candidates.some((item) => item.queueReason === "task_error"));
  assert.ok(candidates.some((item) => item.queueReason === "company_unrecognized"));
});
