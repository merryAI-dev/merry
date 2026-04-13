/** @vitest-environment jsdom */
import * as React from "react";

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetchMock } = vi.hoisted(() => ({
  apiFetchMock: vi.fn(),
}));

vi.mock("@/lib/apiClient", () => ({
  apiFetch: apiFetchMock,
}));

import DiagnosisHistoryPage from "./page";

describe("DiagnosisHistoryPage", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiFetchMock.mockResolvedValue({
      ok: true,
      events: [
        {
          eventId: "event-1",
          sessionId: "diag_1",
          sessionTitle: "비비비당 진단",
          type: "run_succeeded",
          actor: "kim",
          createdAt: "2026-04-09T00:10:00.000Z",
          description: "진단 실행이 완료되었습니다.",
        },
      ],
    });
  });

  it("loads diagnosis history from the diagnosis API", async () => {
    render(React.createElement(DiagnosisHistoryPage));

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith("/api/diagnosis/history?limit=30");
    });

    expect(await screen.findByText("비비비당 진단")).not.toBeNull();
    expect(screen.getByText("진단 실행이 완료되었습니다.")).not.toBeNull();
  });
});
