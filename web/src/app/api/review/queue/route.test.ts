import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

function read(relativePath: string): string {
  return readFileSync(path.join(process.cwd(), relativePath), "utf8");
}

describe("review queue API aliases", () => {
  it("defines a queue list alias under /api/review/queue", () => {
    expect(read("src/app/api/review/queue/route.ts")).toContain(
      'export * from "@/app/api/review-queue/route";',
    );
  });

  it("defines queue mutation aliases under /api/review/queue/[queueId]", () => {
    expect(read("src/app/api/review/queue/[queueId]/claim/route.ts")).toContain(
      'export * from "@/app/api/review-queue/[queueId]/claim/route";',
    );
    expect(read("src/app/api/review/queue/[queueId]/resolve/route.ts")).toContain(
      'export * from "@/app/api/review-queue/[queueId]/resolve/route";',
    );
    expect(read("src/app/api/review/queue/[queueId]/suppress/route.ts")).toContain(
      'export * from "@/app/api/review-queue/[queueId]/suppress/route";',
    );
  });
});
