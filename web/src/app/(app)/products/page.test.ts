import { describe, expect, it } from "vitest";
import * as React from "react";

import { PRODUCTS } from "@/lib/products";

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
  it("renders both product links and chooser copy", () => {
    const tree = ProductsPage();
    const links = collectLinks(tree);
    const text = collectText(tree);

    expect(links.length).toBeGreaterThanOrEqual(2);
    expect(links).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ href: "/report" }),
        expect.objectContaining({ href: "/diagnosis" }),
      ]),
    );
    expect(links.some((link) => link.href === "/report" && link.text.includes("투자심사"))).toBe(true);
    expect(links.some((link) => link.href === "/diagnosis" && link.text.includes("현황진단"))).toBe(true);
    expect(text).toContain("로그인과 팀은 공유하지만, 실제 작업 공간은 제품별로 분리됩니다.");
    expect(PRODUCTS.map((product) => product.href)).toEqual(["/report", "/diagnosis"]);
  });
});
