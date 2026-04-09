import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireWorkspaceFromCookiesMock,
  authMock,
  listReportPresenceMock,
  upsertReportPresenceMock,
  assertExistingReportSessionMock,
} = vi.hoisted(() => ({
  requireWorkspaceFromCookiesMock: vi.fn(),
  authMock: vi.fn(),
  listReportPresenceMock: vi.fn(),
  upsertReportPresenceMock: vi.fn(),
  assertExistingReportSessionMock: vi.fn(),
}));

vi.mock("@/lib/workspaceServer", () => ({
  requireWorkspaceFromCookies: requireWorkspaceFromCookiesMock,
}));

vi.mock("@/auth", () => ({
  auth: authMock,
}));

vi.mock("@/lib/presenceStore", () => ({
  listReportPresence: listReportPresenceMock,
  upsertReportPresence: upsertReportPresenceMock,
}));

vi.mock("@/lib/reportChat", () => ({
  assertExistingReportSession: assertExistingReportSessionMock,
}));

import { POST } from "./route";

describe("presence route", () => {
  beforeEach(() => {
    requireWorkspaceFromCookiesMock.mockReset();
    authMock.mockReset();
    listReportPresenceMock.mockReset();
    upsertReportPresenceMock.mockReset();
    assertExistingReportSessionMock.mockReset();

    requireWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-1", memberName: "lee" });
    authMock.mockResolvedValue({ user: { email: "lee@example.com", image: null } });
  });

  it("rejects presence heartbeats for nonexistent review sessions", async () => {
    assertExistingReportSessionMock.mockRejectedValue(new Error("NOT_FOUND"));

    const response = await POST(
      new Request("http://localhost/api/presence", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ scope: "review", scopeId: "report_missing" }),
      }),
    );

    const body = await response.json();
    expect(response.status).toBe(404);
    expect(body).toEqual({ ok: false, error: "NOT_FOUND" });
    expect(upsertReportPresenceMock).not.toHaveBeenCalled();
  });
});
