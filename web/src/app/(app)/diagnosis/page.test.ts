import { describe, expect, it } from "vitest";
import * as React from "react";

import DiagnosisPage from "./page.tsx";

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
    if (React.isValidElement(value)) {
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
    if (React.isValidElement(value)) {
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

describe("DiagnosisPage", () => {
  it("keeps the temporary fallback link on the chooser path", () => {
    const tree = DiagnosisPage();
    const links = collectLinks(tree);
    const text = collectText(tree);

    expect(links.some((link) => link.href === "/products" && link.text.includes("제품 선택으로 돌아가기"))).toBe(true);
    expect(text).toContain("현황진단 준비 중");
    expect(text).toContain("지금은 제품 선택 화면에서 다시 이동할 수 있습니다.");
  });
});
