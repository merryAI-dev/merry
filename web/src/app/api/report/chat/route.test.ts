import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireWorkspaceFromCookiesMock,
  assertExistingReportSessionMock,
} = vi.hoisted(() => ({
  requireWorkspaceFromCookiesMock: vi.fn(),
  assertExistingReportSessionMock: vi.fn(),
}));

vi.mock("@/lib/workspaceServer", () => ({
  requireWorkspaceFromCookies: requireWorkspaceFromCookiesMock,
}));

vi.mock("@/lib/reportChat", () => ({
  assertExistingReportSession: assertExistingReportSessionMock,
  addReportMessage: vi.fn(),
  extractFileContexts: vi.fn(() => []),
  buildFileContextBlock: vi.fn(() => ""),
  extractMarketIntelBlock: vi.fn(() => ""),
}));

vi.mock("@/lib/failurePatterns", () => ({
  extractFailurePatterns: vi.fn(() => []),
  buildFailurePatternBlock: vi.fn(() => ""),
}));

vi.mock("@/lib/adaptiveScaffold", () => ({
  extractOutcomes: vi.fn(() => []),
  shouldInjectScaffold: vi.fn(() => false),
  calculateFailureRate: vi.fn(() => 0),
  buildScaffoldBlock: vi.fn(() => ""),
}));

vi.mock("@/lib/postVerifier", () => ({
  buildTrustedPool: vi.fn(() => []),
  annotateUnverifiedClaims: vi.fn((text: string) => ({ annotated: text, claimCount: 0 })),
}));

vi.mock("@/lib/chatStore", () => ({
  getMessages: vi.fn(() => []),
}));

vi.mock("@/lib/llm", () => ({
  getLlmProvider: vi.fn(() => "anthropic"),
}));

vi.mock("@/lib/aws/bedrock", () => ({
  getBedrockRuntimeClient: vi.fn(),
}));

vi.mock("@/lib/merryPersona", () => ({
  buildMerryPersona: vi.fn(() => ""),
  buildSynthesisPrompt: vi.fn(() => ""),
}));

vi.mock("@/lib/jobStore", () => ({
  getJob: vi.fn(),
}));

vi.mock("@/lib/reportAssumptionsStore", () => ({
  getAssumptionPackById: vi.fn(),
  getLatestComputeSnapshot: vi.fn(),
  getLatestLockedAssumptionPack: vi.fn(),
}));

import { POST } from "./route";

describe("report chat route", () => {
  beforeEach(() => {
    requireWorkspaceFromCookiesMock.mockReset();
    assertExistingReportSessionMock.mockReset();

    requireWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-1", memberName: "lee" });
  });

  it("rejects chat writes for nonexistent report sessions", async () => {
    assertExistingReportSessionMock.mockRejectedValue(new Error("NOT_FOUND"));

    const response = await POST(
      new Request("http://localhost/api/report/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId: "report_missing", message: "hello" }),
      }),
    );

    const body = await response.json();
    expect(response.status).toBe(404);
    expect(body).toEqual({ ok: false, error: "NOT_FOUND" });
  });
});
