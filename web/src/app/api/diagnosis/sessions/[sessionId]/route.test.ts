import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireWorkspaceFromCookiesMock,
  getDiagnosisSessionDetailMock,
} = vi.hoisted(() => ({
  requireWorkspaceFromCookiesMock: vi.fn(),
  getDiagnosisSessionDetailMock: vi.fn(),
}));

vi.mock("@/lib/workspaceServer", () => ({
  requireWorkspaceFromCookies: requireWorkspaceFromCookiesMock,
}));

vi.mock("@/lib/diagnosisSessionStore", () => ({
  getDiagnosisSessionDetail: getDiagnosisSessionDetailMock,
}));

import { GET } from "./route";

describe("diagnosis session detail route", () => {
  beforeEach(() => {
    requireWorkspaceFromCookiesMock.mockReset();
    getDiagnosisSessionDetailMock.mockReset();

    requireWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-1", memberName: "kim" });
    getDiagnosisSessionDetailMock.mockResolvedValue({
      sessionId: "diag_1",
      title: "비비비당 진단",
      status: "ready",
      latestRunId: null,
      legacyJobId: null,
      latestArtifactCount: 1,
      createdAt: "2026-04-09T00:00:00.000Z",
      updatedAt: "2026-04-09T00:10:00.000Z",
      createdBy: "kim",
      uploads: [],
      runs: [],
      events: [{ eventId: "evt-1", description: "첫 질문을 생성했습니다.", createdAt: "2026-04-09T00:00:10.000Z", type: "conversation_started", actor: "kim", sessionId: "diag_1" }],
      messages: [
        {
          messageId: "diag_msg_1",
          role: "assistant",
          content: "초기 진단 요약과 첫 질문",
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
        sourceFile: {
          fileId: "file-1",
          originalName: "bbb.xlsx",
        },
        analysisSummary: {
          companyName: "비비비당",
          gapCount: 3,
          sheets: ["기업정보", "현황진단"],
          scoreCards: [],
          sampleGaps: [],
        },
      },
    });
  });

  it("returns diagnosis session detail for the chat-first diagnosis product", async () => {
    const response = await GET(new Request("http://localhost/api/diagnosis/sessions/diag_1"), {
      params: Promise.resolve({ sessionId: "diag_1" }),
    });
    const body = await response.json();

    expect(body.session.messages).toHaveLength(1);
    expect(body.session.artifacts).toHaveLength(1);
    expect(body.session.conversationState?.status).toBe("awaiting_user");
  });
});
