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
});
