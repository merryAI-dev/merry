import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireWorkspaceFromCookiesMock,
  listDiagnosisSessionsMock,
  syncDiagnosisSessionFromLegacyJobMock,
} = vi.hoisted(() => ({
  requireWorkspaceFromCookiesMock: vi.fn(),
  listDiagnosisSessionsMock: vi.fn(),
  syncDiagnosisSessionFromLegacyJobMock: vi.fn(),
}));

vi.mock("@/lib/workspaceServer", () => ({
  requireWorkspaceFromCookies: requireWorkspaceFromCookiesMock,
}));

vi.mock("@/lib/diagnosisSessionStore", () => ({
  listDiagnosisSessions: listDiagnosisSessionsMock,
  syncDiagnosisSessionFromLegacyJob: syncDiagnosisSessionFromLegacyJobMock,
}));

import { GET } from "./route";

describe("diagnosis sessions route", () => {
  beforeEach(() => {
    requireWorkspaceFromCookiesMock.mockReset();
    listDiagnosisSessionsMock.mockReset();
    syncDiagnosisSessionFromLegacyJobMock.mockReset();

    requireWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-1", memberName: "kim" });
    listDiagnosisSessionsMock
      .mockResolvedValueOnce([
        { sessionId: "diag_1", status: "processing", legacyJobId: "job-1" },
      ])
      .mockResolvedValueOnce([
        { sessionId: "diag_1", status: "ready", legacyJobId: "job-1" },
      ]);
  });

  it("lists recent diagnosis sessions and syncs in-flight ones", async () => {
    const response = await GET(new Request("http://localhost/api/diagnosis/sessions?limit=20"));
    const body = await response.json();

    expect(listDiagnosisSessionsMock).toHaveBeenCalledTimes(2);
    expect(syncDiagnosisSessionFromLegacyJobMock).toHaveBeenCalledWith("team-1", "diag_1");
    expect(body.sessions[0]?.status).toBe("ready");
  });
});
