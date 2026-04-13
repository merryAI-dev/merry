/** @vitest-environment jsdom */
import * as React from "react";

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetchMock } = vi.hoisted(() => ({
  apiFetchMock: vi.fn(),
}));

vi.mock("@/lib/apiClient", () => ({
  apiFetch: apiFetchMock,
}));

import AnalysisPage from "./page";

describe("AnalysisPage", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiFetchMock.mockImplementation(async (input: string) => {
      if (input === "/api/jobs") {
        return { jobs: [] };
      }
      if (typeof input === "string" && input.startsWith("/api/cost/estimate")) {
        return { ok: true, samples: 200, avgUsd: 0.1, estimateUsd: 20 };
      }
      throw new Error(`unexpected apiFetch call: ${String(input)}`);
    });
  });

  it("cuts over diagnosis to the dedicated product instead of showing a diagnosis job type", async () => {
    render(React.createElement(AnalysisPage));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/jobs");
    });

    expect(screen.queryByRole("option", { name: "기업진단 분석(엑셀)" })).toBeNull();
    expect(screen.getByRole("link", { name: "현황진단 스튜디오로 이동" })).not.toBeNull();
  });
});
