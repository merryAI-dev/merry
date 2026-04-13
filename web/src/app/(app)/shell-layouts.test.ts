import * as React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

const {
  redirectMock,
  getWorkspaceFromCookiesMock,
  ReviewSidebarMock,
  ReviewMobileNavMock,
  DiagnosisSidebarMock,
  DiagnosisMobileNavMock,
} = vi.hoisted(() => ({
  redirectMock: vi.fn(),
  getWorkspaceFromCookiesMock: vi.fn(),
  ReviewSidebarMock: vi.fn(() => React.createElement("div", null, "review-sidebar")),
  ReviewMobileNavMock: vi.fn(() => React.createElement("div", null, "review-mobile-nav")),
  DiagnosisSidebarMock: vi.fn(() => React.createElement("div", null, "diagnosis-sidebar")),
  DiagnosisMobileNavMock: vi.fn(() => React.createElement("div", null, "diagnosis-mobile-nav")),
}));

vi.mock("next/navigation", () => ({
  redirect: redirectMock,
}));

vi.mock("@/lib/workspaceServer", () => ({
  getWorkspaceFromCookies: getWorkspaceFromCookiesMock,
}));

vi.mock("@/components/review/ReviewSidebar", () => ({
  ReviewSidebar: ReviewSidebarMock,
}));

vi.mock("@/components/review/ReviewMobileNav", () => ({
  ReviewMobileNav: ReviewMobileNavMock,
}));

vi.mock("@/components/diagnosis/DiagnosisSidebar", () => ({
  DiagnosisSidebar: DiagnosisSidebarMock,
}));

vi.mock("@/components/diagnosis/DiagnosisMobileNav", () => ({
  DiagnosisMobileNav: DiagnosisMobileNavMock,
}));

const { default: AppLayout } = await import("./layout.tsx");
const { default: ReviewLayout } = await import("./(review)/layout.tsx");
const { default: DiagnosisLayout } = await import("./(diagnosis)/layout.tsx");

function findElementByType(node: React.ReactNode, type: unknown): React.ReactElement | null {
  if (node == null || typeof node === "boolean") return null;
  if (Array.isArray(node)) {
    for (const child of node) {
      const found = findElementByType(child, type);
      if (found) return found;
    }
    return null;
  }
  if (!React.isValidElement<{ children?: React.ReactNode }>(node)) return null;
  if (node.type === type) return node;
  return findElementByType(node.props.children, type);
}

describe("product shell layouts", () => {
  const originalRollout = process.env.MERRY_DIAGNOSIS_ROLLOUT;
  const originalInternalTeams = process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS;

  afterEach(() => {
    if (originalRollout === undefined) delete process.env.MERRY_DIAGNOSIS_ROLLOUT;
    else process.env.MERRY_DIAGNOSIS_ROLLOUT = originalRollout;

    if (originalInternalTeams === undefined) delete process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS;
    else process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS = originalInternalTeams;
  });

  it("keeps the base app layout free of product shell chrome", async () => {
    getWorkspaceFromCookiesMock.mockReset();
    redirectMock.mockReset();
    getWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team", memberName: "kim" });

    const tree = await AppLayout({
      children: React.createElement("div", null, "plain-child"),
    });

    expect(findElementByType(tree, ReviewSidebarMock)).toBeNull();
    expect(findElementByType(tree, ReviewMobileNavMock)).toBeNull();
    expect(findElementByType(tree, DiagnosisSidebarMock)).toBeNull();
    expect(findElementByType(tree, DiagnosisMobileNavMock)).toBeNull();
  });

  it("injects review shell chrome only in the review layout", async () => {
    getWorkspaceFromCookiesMock.mockReset();
    getWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team", memberName: "kim" });

    const tree = await ReviewLayout({
      children: React.createElement("div", null, "review-child"),
    });

    expect(findElementByType(tree, ReviewSidebarMock)).not.toBeNull();
    expect(findElementByType(tree, ReviewMobileNavMock)).not.toBeNull();
    expect(findElementByType(tree, DiagnosisSidebarMock)).toBeNull();
    expect(findElementByType(tree, DiagnosisMobileNavMock)).toBeNull();
  });

  it("injects diagnosis shell chrome only in the diagnosis layout", async () => {
    getWorkspaceFromCookiesMock.mockReset();
    redirectMock.mockReset();
    delete process.env.MERRY_DIAGNOSIS_ROLLOUT;
    delete process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS;
    getWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team", memberName: "kim" });

    const tree = await DiagnosisLayout({
      children: React.createElement("div", null, "diagnosis-child"),
    });

    expect(findElementByType(tree, ReviewSidebarMock)).toBeNull();
    expect(findElementByType(tree, ReviewMobileNavMock)).toBeNull();
    expect(findElementByType(tree, DiagnosisSidebarMock)).not.toBeNull();
    expect(findElementByType(tree, DiagnosisMobileNavMock)).not.toBeNull();
  });

  it("redirects out of the diagnosis shell when rollout is disabled for the workspace", async () => {
    getWorkspaceFromCookiesMock.mockReset();
    redirectMock.mockReset();
    process.env.MERRY_DIAGNOSIS_ROLLOUT = "off";
    delete process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS;
    getWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team", memberName: "kim" });

    await DiagnosisLayout({
      children: React.createElement("div", null, "diagnosis-child"),
    });

    expect(redirectMock).toHaveBeenCalledWith("/products");
  });
});
