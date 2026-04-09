import { describe, expect, it } from "vitest";

import { REVIEW_NAV_ITEMS } from "./nav";

describe("REVIEW_NAV_ITEMS", () => {
  it("matches the staged review product routes", () => {
    expect(REVIEW_NAV_ITEMS.map(({ href, label }) => ({ href, label }))).toEqual([
      { href: "/report", label: "세션" },
      { href: "/report/new", label: "새 보고서" },
      { href: "/review", label: "검토 큐" },
      { href: "/history", label: "히스토리" },
    ]);
  });
});
