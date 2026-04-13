import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireWorkspaceFromCookiesMock,
  syncDiagnosisSessionFromLegacyJobMock,
  getDiagnosisSessionDetailMock,
  getJobMock,
} = vi.hoisted(() => ({
  requireWorkspaceFromCookiesMock: vi.fn(),
  syncDiagnosisSessionFromLegacyJobMock: vi.fn(),
  getDiagnosisSessionDetailMock: vi.fn(),
  getJobMock: vi.fn(),
}));

vi.mock("@/lib/workspaceServer", () => ({
  requireWorkspaceFromCookies: requireWorkspaceFromCookiesMock,
}));

vi.mock("@/lib/diagnosisSessionStore", () => ({
  syncDiagnosisSessionFromLegacyJob: syncDiagnosisSessionFromLegacyJobMock,
  getDiagnosisSessionDetail: getDiagnosisSessionDetailMock,
}));

vi.mock("@/lib/jobStore", () => ({
  getJob: getJobMock,
}));

import { GET } from "./route";

describe("diagnosis session detail route", () => {
  beforeEach(() => {
    requireWorkspaceFromCookiesMock.mockReset();
    syncDiagnosisSessionFromLegacyJobMock.mockReset();
    getDiagnosisSessionDetailMock.mockReset();
    getJobMock.mockReset();

    requireWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-1", memberName: "kim" });
    getDiagnosisSessionDetailMock.mockResolvedValue({
      sessionId: "diag_1",
      title: "비비비당 진단",
      status: "ready",
      legacyJobId: "job-1",
      latestRunId: "run-1",
      uploads: [],
      runs: [{ runId: "run-1", legacyJobId: "job-1", status: "succeeded" }],
      events: [],
    });
    getJobMock.mockResolvedValue({
      jobId: "job-1",
      status: "succeeded",
      artifacts: [{ artifactId: "artifact-1", label: "diagnosis.json" }],
      error: "",
    });
  });

  it("returns diagnosis session detail enriched with legacy job data", async () => {
    const response = await GET(new Request("http://localhost/api/diagnosis/sessions/diag_1"), {
      params: Promise.resolve({ sessionId: "diag_1" }),
    });
    const body = await response.json();

    expect(syncDiagnosisSessionFromLegacyJobMock).toHaveBeenCalledWith("team-1", "diag_1");
    expect(getJobMock).toHaveBeenCalledWith("team-1", "job-1");
    expect(body.session.legacyJob?.status).toBe("succeeded");
    expect(body.session.legacyJob?.artifacts).toHaveLength(1);
  });
});
