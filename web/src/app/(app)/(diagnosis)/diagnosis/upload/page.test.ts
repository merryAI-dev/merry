/** @vitest-environment jsdom */
import * as React from "react";

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetchMock, routerPushMock } = vi.hoisted(() => ({
  apiFetchMock: vi.fn(),
  routerPushMock: vi.fn(),
}));

vi.mock("@/lib/apiClient", () => ({
  apiFetch: apiFetchMock,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock }),
}));

import DiagnosisUploadPage from "./page";

describe("DiagnosisUploadPage", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    routerPushMock.mockReset();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
      }),
    );
    apiFetchMock.mockImplementation(async (input: string) => {
      if (input === "/api/uploads/presign") {
        return {
          file: { fileId: "file-1" },
          upload: { url: "https://upload.example.com/file-1", headers: { "content-type": "application/vnd.ms-excel" } },
        };
      }
      if (input === "/api/uploads/complete") {
        return { ok: true };
      }
      if (input === "/api/diagnosis/uploads") {
        return { ok: true, sessionId: "diag_1", href: "/diagnosis/sessions/diag_1" };
      }
      throw new Error(`unexpected apiFetch call: ${String(input)}`);
    });
  });

  it("uploads an xlsx file and starts a diagnosis session", async () => {
    render(React.createElement(DiagnosisUploadPage));

    const file = new File(["sheet"], "bbb.xlsx", {
      type: "application/vnd.ms-excel",
    });

    fireEvent.change(screen.getByLabelText("진단 시트 파일"), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "진단 시작" }));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        "/api/uploads/presign",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });
    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        "/api/uploads/complete",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });
    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        "/api/diagnosis/uploads",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });
    await waitFor(() => {
      expect(routerPushMock).toHaveBeenCalledWith("/diagnosis/sessions/diag_1");
    });
  });
});
