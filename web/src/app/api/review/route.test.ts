import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

function read(relativePath: string): string {
  return readFileSync(path.join(process.cwd(), relativePath), "utf8");
}

describe("review API aliases", () => {
  it("defines the feedback alias under /api/review/feedback", () => {
    expect(read("src/app/api/review/feedback/route.ts")).toContain(
      'export * from "@/app/api/report/feedback/route";',
    );
  });

  it("defines the primary review aliases used by Task 4 routes", () => {
    expect(read("src/app/api/review/sessions/route.ts")).toContain(
      'export * from "@/app/api/report/sessions/route";',
    );
    expect(read("src/app/api/review/[sessionId]/meta/route.ts")).toContain(
      'export * from "@/app/api/report/[sessionId]/meta/route";',
    );
    expect(read("src/app/api/review/[sessionId]/messages/route.ts")).toContain(
      'export * from "@/app/api/report/[sessionId]/messages/route";',
    );
    expect(read("src/app/api/review/chat/route.ts")).toContain(
      'export * from "@/app/api/report/chat/route";',
    );
  });
});
