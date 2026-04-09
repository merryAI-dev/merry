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

  it("uses matchers that keep report slugs under the session tab", () => {
    const [sessions, newReport, queue, history] = REVIEW_NAV_ITEMS;

    expect(sessions.match("/report")).toBe(true);
    expect(sessions.match("/report/acme-series-a")).toBe(true);
    expect(sessions.match("/report/newco")).toBe(true);
    expect(sessions.match("/report/new")).toBe(false);

    expect(newReport.match("/report/new")).toBe(true);
    expect(newReport.match("/report/new/step-2")).toBe(true);
    expect(newReport.match("/report/newco")).toBe(false);

    expect(queue.match("/review")).toBe(true);
    expect(queue.match("/review/queue-1")).toBe(true);
    expect(queue.match("/report")).toBe(false);

    expect(history.match("/history")).toBe(true);
    expect(history.match("/history/jobs/1")).toBe(true);
    expect(history.match("/review")).toBe(false);
  });
});
