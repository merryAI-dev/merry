import { beforeEach, describe, expect, it, vi } from "vitest";

const { requireWorkspaceFromCookiesMock, replyInDiagnosisSessionMock } = vi.hoisted(() => ({
  requireWorkspaceFromCookiesMock: vi.fn(),
  replyInDiagnosisSessionMock: vi.fn(),
}));

vi.mock("@/lib/workspaceServer", () => ({
  requireWorkspaceFromCookies: requireWorkspaceFromCookiesMock,
}));

vi.mock("@/lib/diagnosisWorkflows", () => ({
  replyInDiagnosisSession: replyInDiagnosisSessionMock,
}));

import { POST } from "./route";

describe("diagnosis message route", () => {
  beforeEach(() => {
    requireWorkspaceFromCookiesMock.mockReset();
    replyInDiagnosisSessionMock.mockReset();

    requireWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-1", memberName: "kim" });
    replyInDiagnosisSessionMock.mockResolvedValue({
      assistantMessage: {
        messageId: "diag_msg_2",
        content: "좋습니다. 다음으로 CAC 추이를 알려주세요.",
      },
    });
  });

  it("routes a user reply into the diagnosis conversation workflow", async () => {
    const response = await POST(
      new Request("http://localhost/api/diagnosis/sessions/diag_1/messages", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ content: "현재는 리퍼럴 중심이고 CAC는 아직 추적하지 못했습니다." }),
      }),
      { params: Promise.resolve({ sessionId: "diag_1" }) },
    );
    const body = await response.json();

    expect(replyInDiagnosisSessionMock).toHaveBeenCalledWith({
      teamId: "team-1",
      memberName: "kim",
      sessionId: "diag_1",
      content: "현재는 리퍼럴 중심이고 CAC는 아직 추적하지 못했습니다.",
    });
    expect(body.assistantMessage.content).toContain("CAC");
  });
});
