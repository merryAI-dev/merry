/** @vitest-environment jsdom */
import * as React from "react";

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetchMock, windowOpenMock } = vi.hoisted(() => ({
  apiFetchMock: vi.fn(),
  windowOpenMock: vi.fn(),
}));

vi.mock("@/lib/apiClient", () => ({
  apiFetch: apiFetchMock,
}));

import { DiagnosisSessionDetailPage } from "./DiagnosisSessionDetailPage";

describe("DiagnosisSessionDetailPage", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    windowOpenMock.mockReset();
    vi.stubGlobal("open", windowOpenMock);

    apiFetchMock.mockResolvedValue({
      ok: true,
      session: {
        sessionId: "diag_1",
        title: "비비비당 진단",
        status: "ready",
        createdAt: "2026-04-09T00:00:00.000Z",
        updatedAt: "2026-04-09T00:10:00.000Z",
        createdBy: "kim",
        originalFileName: "bbb.xlsx",
        latestRunId: "run-1",
        legacyJobId: "job-1",
        latestArtifactCount: 1,
        uploads: [],
        runs: [],
        events: [],
        legacyJob: {
          jobId: "job-1",
          status: "succeeded",
          error: "",
          artifacts: [{ artifactId: "artifact-1", label: "diagnosis.json" }],
        },
      },
    });
  });

  it("loads diagnosis session detail and opens artifact downloads through the legacy job route", async () => {
    render(React.createElement(DiagnosisSessionDetailPage, { sessionId: "diag_1" }));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/diagnosis/sessions/diag_1");
    });

    expect(await screen.findByText("비비비당 진단")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "diagnosis.json 다운로드" }));
    expect(windowOpenMock).toHaveBeenCalledWith(
      "/api/jobs/job-1/artifact?artifactId=artifact-1",
      "_blank",
      "noopener,noreferrer",
    );
  });
});
