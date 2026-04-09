import { beforeEach, describe, expect, it, vi } from "vitest";

const { requireWorkspaceFromCookiesMock, listReportSessionsMock } = vi.hoisted(() => ({
  requireWorkspaceFromCookiesMock: vi.fn(),
  listReportSessionsMock: vi.fn(),
}));

vi.mock("@/lib/workspaceServer", () => ({
  requireWorkspaceFromCookies: requireWorkspaceFromCookiesMock,
}));

vi.mock("@/lib/reportChat", async () => {
  const actual = await vi.importActual<typeof import("@/lib/reportChat")>("@/lib/reportChat");
  return {
    ...actual,
    listReportSessions: listReportSessionsMock,
    createReportSession: vi.fn(),
    addReportMessage: vi.fn(),
  };
});

import { GET } from "./route";

describe("report sessions route", () => {
  beforeEach(() => {
    requireWorkspaceFromCookiesMock.mockReset();
    listReportSessionsMock.mockReset();

    requireWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-1", memberName: "lee" });
    listReportSessionsMock.mockResolvedValue(
      Array.from({ length: 150 }, (_, i) => ({
        sessionId: `report_${i}`,
        slug: `slug-${i}`,
        title: `Session ${i}`,
        createdAt: `2026-04-${String((i % 28) + 1).padStart(2, "0")}T00:00:00.000Z`,
      })),
    );
  });

  it("paginates against the full corpus instead of a 100-session slice", async () => {
    const response = await GET(new Request("http://localhost/api/report/sessions?limit=30&offset=120"));
    const body = await response.json();

    expect(listReportSessionsMock).toHaveBeenCalledWith("team-1");
    expect(body.total).toBe(150);
    expect(body.offset).toBe(120);
    expect(body.hasMore).toBe(false);
    expect(body.sessions).toHaveLength(30);
    expect(body.sessions[0]?.slug).toBe("slug-120");
  });

  it("filters against the full corpus before slicing", async () => {
    listReportSessionsMock.mockResolvedValue([
      ...Array.from({ length: 149 }, (_, i) => ({
        sessionId: `report_${i}`,
        slug: `slug-${i}`,
        title: `Session ${i}`,
        companyName: "Acme",
        createdAt: `2026-04-${String((i % 28) + 1).padStart(2, "0")}T00:00:00.000Z`,
      })),
      {
        sessionId: "report_target",
        slug: "slug-target",
        title: "Session target",
        companyName: "Needle Labs",
        createdAt: "2026-04-30T00:00:00.000Z",
      },
    ]);

    const response = await GET(new Request("http://localhost/api/report/sessions?limit=30&offset=0&q=needle"));
    const body = await response.json();

    expect(body.total).toBe(1);
    expect(body.offset).toBe(0);
    expect(body.hasMore).toBe(false);
    expect(body.sessions).toHaveLength(1);
    expect(body.sessions[0]?.slug).toBe("slug-target");
  });
});
