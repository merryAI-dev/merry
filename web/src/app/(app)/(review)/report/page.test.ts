/** @vitest-environment jsdom */
import * as React from "react";

import { render, waitFor } from "@testing-library/react";
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
    apiFetchMock.mockResolvedValue({ sessions: [] });
  });

  it("requests an expanded review session corpus for the primary /review surface", async () => {
    render(React.createElement(ReportSessionsPage));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/review/sessions?limit=200");
    });
  });
});
