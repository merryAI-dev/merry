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
    if (React.isValidElement<{ children?: React.ReactNode }>(value)) {
      visit(value.props.children);
    }
  };
  visit(node);
  return parts.join(" ");
}

describe("DiagnosisPage", () => {
  it("introduces the diagnosis studio workflow", () => {
    const tree = DiagnosisPage();
    const text = collectText(tree);

    expect(text).toContain("기업 현황을 진단하고 다음 작업을 준비합니다");
    expect(text).toContain("자동 분석과 첫 질문");
    expect(text).toContain("대화형 진단 세션");
    expect(text).toContain("후속 작업을 추적합니다");
  });
});
