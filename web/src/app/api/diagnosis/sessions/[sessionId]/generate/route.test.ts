import { beforeEach, describe, expect, it, vi } from "vitest";

const { requireWorkspaceFromCookiesMock, generateDiagnosisReportMock } = vi.hoisted(() => ({
  requireWorkspaceFromCookiesMock: vi.fn(),
  generateDiagnosisReportMock: vi.fn(),
}));

vi.mock("@/lib/workspaceServer", () => ({
  requireWorkspaceFromCookies: requireWorkspaceFromCookiesMock,
}));

vi.mock("@/lib/diagnosisWorkflows", () => ({
  generateDiagnosisReport: generateDiagnosisReportMock,
}));

import { POST } from "./route";

describe("diagnosis generate route", () => {
  beforeEach(() => {
    requireWorkspaceFromCookiesMock.mockReset();
    generateDiagnosisReportMock.mockReset();

    requireWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-1", memberName: "kim" });
    generateDiagnosisReportMock.mockResolvedValue({
      assistantMessage: {
        messageId: "diag_msg_3",
        content: "분석보고서를 생성했습니다.",
      },
      artifact: {
        artifactId: "artifact-1",
        label: "diagnosis-report.xlsx",
      },
    });
  });

  it("generates the consultant report artifact for the diagnosis session", async () => {
    const response = await POST(
      new Request("http://localhost/api/diagnosis/sessions/diag_1/generate", {
        method: "POST",
      }),
      { params: Promise.resolve({ sessionId: "diag_1" }) },
    );
    const body = await response.json();

    expect(generateDiagnosisReportMock).toHaveBeenCalledWith({
      teamId: "team-1",
      memberName: "kim",
      sessionId: "diag_1",
    });
    expect(body.artifact.label).toBe("diagnosis-report.xlsx");
  });
});
