import * as React from "react";
import { describe, expect, it } from "vitest";

import DiagnosisHistoryPage from "./history/page.tsx";
import DiagnosisPage from "./page.tsx";
import DiagnosisSessionsPage from "./sessions/page.tsx";
import DiagnosisUploadPage from "./upload/page.tsx";

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

describe("diagnosis placeholder routes", () => {
  it("renders the staged diagnosis shell pages", () => {
    expect(collectText(DiagnosisPage())).toContain("기업 현황을 진단하고 다음 작업을 준비합니다");
    expect(collectText(DiagnosisUploadPage())).toContain("업로드 준비 중");
    expect(collectText(DiagnosisSessionsPage())).toContain("진단 세션 준비 중");
    expect(collectText(DiagnosisHistoryPage())).toContain("진단 히스토리 준비 중");
  });
});
