import { describe, expect, it } from "vitest";

import { DIAGNOSIS_NAV_ITEMS } from "./nav";

describe("DIAGNOSIS_NAV_ITEMS", () => {
  it("matches the staged diagnosis product routes", () => {
    expect(DIAGNOSIS_NAV_ITEMS.map(({ href, label }) => ({ href, label }))).toEqual([
      { href: "/diagnosis", label: "진단 시작" },
      { href: "/diagnosis/upload", label: "업로드" },
      { href: "/diagnosis/sessions", label: "진단 세션" },
      { href: "/diagnosis/history", label: "히스토리" },
    ]);
  });

  it("uses matchers that keep diagnosis sections isolated", () => {
    const [start, upload, sessions, history] = DIAGNOSIS_NAV_ITEMS;

    expect(start.match("/diagnosis")).toBe(true);
    expect(start.match("/diagnosis/upload")).toBe(false);

    expect(upload.match("/diagnosis/upload")).toBe(true);
    expect(upload.match("/diagnosis/upload/batch-1")).toBe(true);
    expect(upload.match("/diagnosis")).toBe(false);

    expect(sessions.match("/diagnosis/sessions")).toBe(true);
    expect(sessions.match("/diagnosis/sessions/abc")).toBe(true);
    expect(sessions.match("/diagnosis/history")).toBe(false);

    expect(history.match("/diagnosis/history")).toBe(true);
    expect(history.match("/diagnosis/history/2026-04-09")).toBe(true);
    expect(history.match("/diagnosis/sessions")).toBe(false);
  });
});
