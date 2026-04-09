import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

function read(relativePath: string): string {
  return readFileSync(path.join(process.cwd(), relativePath), "utf8");
}

describe("review slug error alias", () => {
  it("keeps the alias route marked as a client component", () => {
    const source = read("src/app/(app)/(review)/review/[slug]/error.tsx");

    expect(source).toContain('"use client";');
    expect(source).toContain('export { default } from "../../report/[slug]/error";');
  });
});
