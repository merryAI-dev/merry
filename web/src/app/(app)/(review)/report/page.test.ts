/** @vitest-environment jsdom */
import * as React from "react";

import { fireEvent, render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetchMock } = vi.hoisted(() => ({
  apiFetchMock: vi.fn(),
}));

vi.mock("@/lib/apiClient", () => ({
  apiFetch: apiFetchMock,
}));

import ReportSessionsPage from "./page";

describe("ReportSessionsPage", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiFetchMock.mockResolvedValue({ sessions: [], total: 0, offset: 0, hasMore: false });
  });

  it("loads the first page of review sessions with explicit offset pagination", async () => {
    render(React.createElement(ReportSessionsPage));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/review/sessions?limit=30&offset=0&q=");
    });
  });

  it("requests the next offset when the user asks for more sessions", async () => {
    apiFetchMock
      .mockResolvedValueOnce({
        sessions: Array.from({ length: 30 }, (_, i) => ({
          sessionId: `report_${i + 1}`,
          slug: `slug-${i + 1}`,
          title: `Session ${i + 1}`,
        })),
        total: 40,
        offset: 0,
        hasMore: true,
      })
      .mockResolvedValueOnce({
        sessions: [{ sessionId: "report_2", slug: "slug-2", title: "Session 2" }],
        total: 40,
        offset: 30,
        hasMore: false,
      });

    const { getByRole } = render(React.createElement(ReportSessionsPage));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/review/sessions?limit=30&offset=0&q=");
    });

    fireEvent.click(getByRole("button", { name: "더 보기" }));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/review/sessions?limit=30&offset=30&q=");
    });
  });

  it("resets pagination and sends q when the user searches", async () => {
    const { getByPlaceholderText } = render(React.createElement(ReportSessionsPage));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/review/sessions?limit=30&offset=0&q=");
    });

    fireEvent.change(getByPlaceholderText("세션 검색"), { target: { value: "needle" } });

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/review/sessions?limit=30&offset=0&q=needle");
    });
  });

  it("offers a direct documents entry point from the review home", async () => {
    const { container } = render(React.createElement(ReportSessionsPage));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/review/sessions?limit=30&offset=0&q=");
    });

    expect(container.querySelector('a[href="/documents"]')).not.toBeNull();
  });
});
