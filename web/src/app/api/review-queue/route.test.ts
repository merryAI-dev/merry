import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireWorkspaceFromCookiesMock,
  syncReviewQueueFromRecentConditionJobsMock,
  listReviewQueueRecordsMock,
  getReviewQueueSummaryMock,
} = vi.hoisted(() => ({
  requireWorkspaceFromCookiesMock: vi.fn(),
  syncReviewQueueFromRecentConditionJobsMock: vi.fn(),
  listReviewQueueRecordsMock: vi.fn(),
  getReviewQueueSummaryMock: vi.fn(),
}));

vi.mock("@/lib/workspaceServer", () => ({
  requireWorkspaceFromCookies: requireWorkspaceFromCookiesMock,
}));

vi.mock("@/lib/reviewQueue", () => ({
  syncReviewQueueFromRecentConditionJobs: syncReviewQueueFromRecentConditionJobsMock,
  listReviewQueueRecords: listReviewQueueRecordsMock,
  getReviewQueueSummary: getReviewQueueSummaryMock,
}));

import { GET } from "./route";

describe("review queue route", () => {
  beforeEach(() => {
    requireWorkspaceFromCookiesMock.mockReset();
    syncReviewQueueFromRecentConditionJobsMock.mockReset();
    listReviewQueueRecordsMock.mockReset();
    getReviewQueueSummaryMock.mockReset();

    requireWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-1" });
    syncReviewQueueFromRecentConditionJobsMock.mockResolvedValue(2);
    listReviewQueueRecordsMock.mockResolvedValue([
      {
        queueId: "queue-1",
        status: "queued",
        queueReason: "parse_warning",
      },
    ]);
    getReviewQueueSummaryMock.mockResolvedValue({
      total: 8,
      queued: 5,
      in_review: 1,
      alias_correction: 3,
      parse_warning: 4,
    });
  });

  it("returns queue-wide summary counts even when item filters are narrower", async () => {
    const response = await GET(new Request("http://localhost/api/review-queue?status=queued&reason=parse_warning&limit=10"));
    const body = await response.json();

    expect(syncReviewQueueFromRecentConditionJobsMock).toHaveBeenCalledWith("team-1", 20);
    expect(listReviewQueueRecordsMock).toHaveBeenCalledWith("team-1", {
      status: "queued",
      reason: "parse_warning",
      limit: 10,
    });
    expect(getReviewQueueSummaryMock).toHaveBeenCalledWith("team-1");
    expect(body.items).toHaveLength(1);
    expect(body.summary).toEqual({
      total: 8,
      queued: 5,
      in_review: 1,
      alias_correction: 3,
      parse_warning: 4,
    });
  });
});
