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
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));

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
        contextDocuments: [
          {
            documentId: "doc-1",
            originalName: "deck.pdf",
            sourceFormat: "pdf",
            role: "context",
            previewText: "시장 개요",
          },
        ],
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

  it("renders attached context documents", async () => {
    render(React.createElement(DiagnosisSessionDetailPage, { sessionId: "diag_1" }));

    expect(await screen.findByText("deck.pdf")).not.toBeNull();
    expect(screen.getByText("시장 개요")).not.toBeNull();
  });

  it("uploads a support document and posts it to the diagnosis context route", async () => {
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
            latestRunId: "run-1",
            legacyJobId: "job-1",
            latestArtifactCount: 1,
            uploads: [],
            runs: [],
            events: [],
            contextDocuments: [],
            legacyJob: null,
          },
        };
      }
      if (url === "/api/uploads/presign") {
        return {
          file: { fileId: "file-ctx-1" },
          upload: { url: "https://example.com/upload", headers: { "content-type": "application/pdf" } },
        };
      }
      if (url === "/api/uploads/complete") {
        return { ok: true };
      }
      if (url === "/api/diagnosis/context-docs") {
        return { ok: true, document: { documentId: "doc-2" } };
      }
      throw new Error(`unexpected url ${url}`);
    });

    render(React.createElement(DiagnosisSessionDetailPage, { sessionId: "diag_1" }));
    await screen.findByText("비비비당 진단");

    const fileInput = screen.getByLabelText("보조 문서 업로드") as HTMLInputElement;
    fireEvent.change(fileInput, {
      target: {
        files: [new File(["%PDF-1.4"], "deck.pdf", { type: "application/pdf" })],
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "보조 문서 추가" }));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/diagnosis/context-docs", expect.objectContaining({
        method: "POST",
      }));
    });
  });
});
