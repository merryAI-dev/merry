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

import DiagnosisSessionsPage from "./page";

describe("DiagnosisSessionsPage", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiFetchMock.mockResolvedValue({
      ok: true,
      sessions: [
        {
          sessionId: "diag_1",
          title: "비비비당 진단",
          status: "processing",
          createdAt: "2026-04-09T00:00:00.000Z",
          updatedAt: "2026-04-09T00:10:00.000Z",
          createdBy: "kim",
          originalFileName: "bbb.xlsx",
          latestRunId: "run-1",
          legacyJobId: "job-1",
          latestArtifactCount: 0,
        },
      ],
    });
  });

  it("loads diagnosis sessions from the dedicated diagnosis API", async () => {
    render(React.createElement(DiagnosisSessionsPage));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/diagnosis/sessions?limit=20");
    });

    expect(await screen.findByText("비비비당 진단")).not.toBeNull();
    expect(screen.getByText("처리 중")).not.toBeNull();
    expect(screen.getByRole("link", { name: "세션 열기" })).not.toBeNull();
  });
});
