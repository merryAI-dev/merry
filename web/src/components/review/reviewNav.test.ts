import { describe, expect, it } from "vitest";

import { REVIEW_NAV_ITEMS } from "./nav";

describe("REVIEW_NAV_ITEMS", () => {
  it("matches the staged review product routes", () => {
    expect(REVIEW_NAV_ITEMS.map(({ href, label }) => ({ href, label }))).toEqual([
      { href: "/review", label: "세션" },
      { href: "/documents", label: "문서 추출" },
      { href: "/review/new", label: "새 보고서" },
      { href: "/review/queue", label: "검토 큐" },
      { href: "/history", label: "히스토리" },
    ]);
  });

  it("uses matchers that keep report slugs under the session tab", () => {
    const [sessions, documents, newReport, queue, history] = REVIEW_NAV_ITEMS;

    expect(sessions.match("/review")).toBe(true);
    expect(sessions.match("/review/acme-series-a")).toBe(true);
    expect(sessions.match("/review/newco")).toBe(true);
    expect(sessions.match("/review/new")).toBe(false);
    expect(sessions.match("/review/queue")).toBe(false);

    expect(documents.match("/documents")).toBe(true);
    expect(documents.match("/documents/batch")).toBe(true);
    expect(documents.match("/review")).toBe(false);

    expect(newReport.match("/review/new")).toBe(true);
    expect(newReport.match("/review/new/step-2")).toBe(true);
    expect(newReport.match("/review/newco")).toBe(false);

    expect(queue.match("/review/queue")).toBe(true);
    expect(queue.match("/review/queue/open")).toBe(true);
    expect(queue.match("/review")).toBe(false);

    expect(history.match("/history")).toBe(true);
    expect(history.match("/history/jobs/1")).toBe(true);
    expect(history.match("/review")).toBe(false);
  });
});
