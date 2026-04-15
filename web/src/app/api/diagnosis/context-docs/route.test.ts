import { beforeEach, describe, expect, it, vi } from "vitest";

const { requireWorkspaceFromCookiesMock, attachDiagnosisContextDocumentFromUploadedFileMock } = vi.hoisted(() => ({
  requireWorkspaceFromCookiesMock: vi.fn(),
  attachDiagnosisContextDocumentFromUploadedFileMock: vi.fn(),
}));

vi.mock("@/lib/workspaceServer", () => ({
  requireWorkspaceFromCookies: requireWorkspaceFromCookiesMock,
}));

vi.mock("@/lib/diagnosisWorkflows", () => ({
  attachDiagnosisContextDocumentFromUploadedFile: attachDiagnosisContextDocumentFromUploadedFileMock,
}));

import { POST } from "./route";

describe("diagnosis context docs route", () => {
  beforeEach(() => {
    requireWorkspaceFromCookiesMock.mockReset();
    attachDiagnosisContextDocumentFromUploadedFileMock.mockReset();

    requireWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-1", memberName: "kim" });
    attachDiagnosisContextDocumentFromUploadedFileMock.mockResolvedValue({
      document: {
        documentId: "doc-1",
        sessionId: "diag_1",
        originalName: "deck.pdf",
        role: "context",
        sourceFormat: "pdf",
        previewText: "시장 개요",
      },
    });
  });

  it("attaches a context document to an existing diagnosis session", async () => {
    const response = await POST(
      new Request("http://localhost/api/diagnosis/context-docs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId: "diag_1", fileId: "file-1" }),
      }),
    );
    const body = await response.json();

    expect(attachDiagnosisContextDocumentFromUploadedFileMock).toHaveBeenCalledWith({
      teamId: "team-1",
      memberName: "kim",
      sessionId: "diag_1",
      fileId: "file-1",
    });
    expect(body).toMatchObject({
      ok: true,
      document: {
        documentId: "doc-1",
        sourceFormat: "pdf",
      },
    });
  });
});
