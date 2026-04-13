import { beforeEach, describe, expect, it, vi } from "vitest";

const { requireWorkspaceFromCookiesMock, listDiagnosisHistoryMock } = vi.hoisted(() => ({
  requireWorkspaceFromCookiesMock: vi.fn(),
  listDiagnosisHistoryMock: vi.fn(),
}));

vi.mock("@/lib/workspaceServer", () => ({
  requireWorkspaceFromCookies: requireWorkspaceFromCookiesMock,
}));

vi.mock("@/lib/diagnosisSessionStore", () => ({
  listDiagnosisHistory: listDiagnosisHistoryMock,
}));

import { GET } from "./route";

describe("diagnosis history route", () => {
  beforeEach(() => {
    requireWorkspaceFromCookiesMock.mockReset();
    listDiagnosisHistoryMock.mockReset();

    requireWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-1", memberName: "kim" });
    listDiagnosisHistoryMock.mockResolvedValue([
      {
        eventId: "event-1",
        sessionId: "diag_1",
        sessionTitle: "비비비당 진단",
        type: "run_succeeded",
        actor: "kim",
        createdAt: "2026-04-09T00:10:00.000Z",
        description: "진단 실행이 완료되었습니다.",
      },
    ]);
  });

  it("returns recent diagnosis history events", async () => {
    const response = await GET(new Request("http://localhost/api/diagnosis/history?limit=10"));
    const body = await response.json();

    expect(listDiagnosisHistoryMock).toHaveBeenCalledWith("team-1", 10);
    expect(body.events[0]?.sessionId).toBe("diag_1");
  });
});
