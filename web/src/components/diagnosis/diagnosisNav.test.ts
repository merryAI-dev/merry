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
});
