import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as React from "react";

import { PRODUCTS } from "@/lib/products";

const { getWorkspaceFromCookiesMock } = vi.hoisted(() => ({
  getWorkspaceFromCookiesMock: vi.fn(),
}));

vi.mock("@/lib/workspaceServer", () => ({
  getWorkspaceFromCookies: getWorkspaceFromCookiesMock,
}));

import ProductsPage from "./page.tsx";

function collectText(node: React.ReactNode): string {
  const parts: string[] = [];
  const visit = (value: React.ReactNode): void => {
    if (value == null || typeof value === "boolean") return;
    if (typeof value === "string" || typeof value === "number") {
      parts.push(String(value));
      return;
    }
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    if (React.isValidElement<{ children?: React.ReactNode }>(value)) {
      visit(value.props.children);
    }
  };
  visit(node);
  return parts.join(" ");
}

function collectLinks(node: React.ReactNode): Array<{ href: string; text: string }> {
  const links: Array<{ href: string; text: string }> = [];
  const visit = (value: React.ReactNode): void => {
    if (value == null || typeof value === "boolean") return;
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    if (React.isValidElement<{ children?: React.ReactNode; href?: unknown }>(value)) {
      const href = typeof value.props.href === "string" ? value.props.href : "";
      if (href) {
        links.push({ href, text: collectText(value.props.children) });
      }
      visit(value.props.children);
    }
  };
  visit(node);
  return links;
}

describe("ProductsPage", () => {
  const originalRollout = process.env.MERRY_DIAGNOSIS_ROLLOUT;
  const originalInternalTeams = process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS;

  beforeEach(() => {
    getWorkspaceFromCookiesMock.mockReset();
  });

  afterEach(() => {
    if (originalRollout === undefined) delete process.env.MERRY_DIAGNOSIS_ROLLOUT;
    else process.env.MERRY_DIAGNOSIS_ROLLOUT = originalRollout;

    if (originalInternalTeams === undefined) delete process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS;
    else process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS = originalInternalTeams;
  });

  it("renders both product links and chooser copy when diagnosis rollout is enabled", async () => {
    getWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-all", memberName: "kim" });

    delete process.env.MERRY_DIAGNOSIS_ROLLOUT;
    delete process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS;

    const tree = await ProductsPage();
    const links = collectLinks(tree);
    const text = collectText(tree);

    expect(links.length).toBeGreaterThanOrEqual(2);
    expect(links).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ href: "/review" }),
        expect.objectContaining({ href: "/diagnosis" }),
      ]),
    );
    expect(links.some((link) => link.href === "/review" && link.text.includes("투자심사"))).toBe(true);
    expect(links.some((link) => link.href === "/diagnosis" && link.text.includes("현황진단"))).toBe(true);
    expect(text).toContain("로그인과 팀은 공유하지만, 실제 작업 공간은 제품별로 분리됩니다.");
    expect(PRODUCTS.map((product) => product.href)).toEqual(["/review", "/diagnosis"]);
  });

  it("hides diagnosis when rollout is internal and the workspace is not allowlisted", async () => {
    getWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-gamma", memberName: "park" });
    process.env.MERRY_DIAGNOSIS_ROLLOUT = "internal";
    process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS = "team-alpha,team-beta";

    const tree = await ProductsPage();
    const links = collectLinks(tree);

    expect(links).toEqual(
      expect.arrayContaining([expect.objectContaining({ href: "/review" })]),
    );
    expect(links.some((link) => link.href === "/diagnosis")).toBe(false);
  });
});
