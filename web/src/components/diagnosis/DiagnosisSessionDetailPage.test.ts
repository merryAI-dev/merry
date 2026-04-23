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

    apiFetchMock.mockImplementation(async (url: string) => {
      if (url === "/api/diagnosis/sessions/diag_1") {
        return {
          ok: true,
          session: {
            sessionId: "diag_1",
            title: "비비비당 진단",
            status: "ready",
            createdAt: "2026-04-09T00:00:00.000Z",
            updatedAt: "2026-04-09T00:10:00.000Z",
            createdBy: "kim",
            originalFileName: "bbb.xlsx",
            latestRunId: null,
            legacyJobId: null,
            latestArtifactCount: 1,
            uploads: [],
            runs: [],
            events: [],
            messages: [
              {
                messageId: "diag_msg_1",
                role: "assistant",
                content: "초기 진단 요약입니다.",
                createdAt: "2026-04-09T00:00:10.000Z",
              },
            ],
            artifacts: [
              {
                artifactId: "artifact-1",
                label: "diagnosis-report.xlsx",
                createdAt: "2026-04-09T00:20:00.000Z",
                contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
              },
            ],
            conversationState: {
              status: "awaiting_user",
              canGenerateReport: true,
              sourceFile: { fileId: "file-1", originalName: "bbb.xlsx" },
              analysisSummary: {
                companyName: "비비비당",
                gapCount: 3,
                sheets: ["기업정보", "현황진단"],
                scoreCards: [],
                sampleGaps: [],
              },
            },
          },
        };
      }
      if (url === "/api/diagnosis/sessions/diag_1/generate") {
        return {
          ok: true,
          artifact: { artifactId: "artifact-1" },
        };
      }
      if (url === "/api/diagnosis/sessions/diag_1/artifacts/artifact-1") {
        return {
          ok: true,
          url: "https://download.example.com/artifact-1",
        };
      }
      throw new Error(`unexpected apiFetch call: ${url}`);
    });
  });

  it("loads diagnosis chat detail and downloads attached artifacts through the diagnosis artifact route", async () => {
    render(React.createElement(DiagnosisSessionDetailPage, { sessionId: "diag_1" }));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/diagnosis/sessions/diag_1");
    });

    expect(await screen.findByText("비비비당 진단")).not.toBeNull();
    expect(screen.getByText("초기 진단 요약입니다.")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "diagnosis-report.xlsx 다운로드" }));
    await waitFor(() => {
      expect(windowOpenMock).toHaveBeenCalledWith(
        "https://download.example.com/artifact-1",
        "_blank",
        "noopener,noreferrer",
      );
    });
  });
});
