/** @vitest-environment jsdom */
import * as React from "react";

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetchMock } = vi.hoisted(() => ({
  apiFetchMock: vi.fn(),
}));

vi.mock("@/lib/apiClient", () => ({
  apiFetch: apiFetchMock,
}));

import ReviewQueuePage from "./page";

const queueResponse = {
  ok: true,
  items: [
    {
      queueId: "queue-1",
      jobId: "job-1",
      taskId: "task-1",
      filename: "deal.pdf",
      companyGroupName: "Acme",
      companyGroupKey: "acme",
      jobTitle: "조건 검사",
      policyText: "정책",
      queueReason: "parse_warning" as const,
      severity: "medium" as const,
      status: "queued" as const,
      evidence: "근거",
      parseWarning: "경고",
      error: "",
      aliasFrom: "",
      createdAt: "2026-04-09T00:00:00.000Z",
      updatedAt: "2026-04-09T00:00:00.000Z",
    },
  ],
  summary: { total: 8, queued: 5, in_review: 1, alias_correction: 3, parse_warning: 4 },
  syncedCandidates: 0,
  hasMore: false,
  nextCursor: null,
};

describe("ReviewQueuePage", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiFetchMock.mockImplementation(async (input: string) => {
      if (typeof input === "string" && input.startsWith("/api/review/queue?")) {
        return queueResponse;
      }
      if (typeof input === "string" && input.startsWith("/api/review/queue/")) {
        return { ok: true };
      }
      throw new Error(`unexpected apiFetch call: ${String(input)}`);
    });
  });

  it("loads and mutates queue items through the /api/review/queue namespace", async () => {
    render(React.createElement(ReviewQueuePage));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        expect.stringMatching(/^\/api\/review\/queue\?/),
      );
    });

    fireEvent.click(await screen.findByRole("button", { name: "Claim" }));
    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/review/queue/queue-1/claim", { method: "POST" });
    });

    fireEvent.click(await screen.findByRole("button", { name: "정답 확인" }));
    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        "/api/review/queue/queue-1/resolve",
        expect.objectContaining({ method: "POST" }),
      );
    });

    fireEvent.click(await screen.findByRole("button", { name: "보류" }));
    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        "/api/review/queue/queue-1/suppress",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("renders top-line metrics from queue-wide summary payload rather than filtered item count", async () => {
    render(React.createElement(ReviewQueuePage));

    expect(await screen.findByText("8개 중")).not.toBeNull();
    expect(screen.getByText("6")).not.toBeNull();
    expect(screen.getByText("3")).not.toBeNull();
    expect(screen.getByText("4")).not.toBeNull();
  });

  it("requests the next cursor when the user loads more queue items", async () => {
    apiFetchMock.mockReset();
    apiFetchMock
      .mockResolvedValueOnce({
        ...queueResponse,
        items: [queueResponse.items[0]],
        hasMore: true,
        nextCursor: "cursor-1",
      })
      .mockResolvedValueOnce({
        ...queueResponse,
        items: [
          {
            ...queueResponse.items[0],
            queueId: "queue-2",
            filename: "deal-2.pdf",
            taskId: "task-2",
            jobId: "job-2",
          },
        ],
        hasMore: false,
        nextCursor: null,
      });

    render(React.createElement(ReviewQueuePage));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/review/queue?status=open&reason=all&limit=50");
    });

    fireEvent.click(await screen.findByRole("button", { name: "더 보기" }));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/review/queue?status=open&reason=all&limit=50&cursor=cursor-1");
    });
  });
});
