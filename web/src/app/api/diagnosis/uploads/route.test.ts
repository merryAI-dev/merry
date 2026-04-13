import { beforeEach, describe, expect, it, vi } from "vitest";

const { requireWorkspaceFromCookiesMock, startDiagnosisFromUploadedFileMock } = vi.hoisted(() => ({
  requireWorkspaceFromCookiesMock: vi.fn(),
  startDiagnosisFromUploadedFileMock: vi.fn(),
}));

vi.mock("@/lib/workspaceServer", () => ({
  requireWorkspaceFromCookies: requireWorkspaceFromCookiesMock,
}));

vi.mock("@/lib/diagnosisWorkflows", () => ({
  startDiagnosisFromUploadedFile: startDiagnosisFromUploadedFileMock,
}));

import { POST } from "./route";

describe("diagnosis uploads route", () => {
  beforeEach(() => {
    requireWorkspaceFromCookiesMock.mockReset();
    startDiagnosisFromUploadedFileMock.mockReset();

    requireWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-1", memberName: "kim" });
    startDiagnosisFromUploadedFileMock.mockResolvedValue({
      session: { sessionId: "diag_1" },
      run: { runId: "run-1" },
      legacyJobId: "job-1",
    });
  });

  it("starts a diagnosis workflow from an uploaded file", async () => {
    const response = await POST(
      new Request("http://localhost/api/diagnosis/uploads", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ fileId: "file-1", title: "비비비당 진단" }),
      }),
    );
    const body = await response.json();

    expect(startDiagnosisFromUploadedFileMock).toHaveBeenCalledWith({
      teamId: "team-1",
      memberName: "kim",
      fileId: "file-1",
      title: "비비비당 진단",
    });
    expect(body).toMatchObject({
      ok: true,
      sessionId: "diag_1",
      runId: "run-1",
      legacyJobId: "job-1",
      href: "/diagnosis/sessions/diag_1",
    });
  });
});
