import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    include: ["src/**/*.test.ts"],
    exclude: [
      // Legacy tests using node:test (not vitest-compatible)
      "src/app/(app)/playground/errorFormat.test.ts",
      "src/app/api/ralph/parse/handler.test.ts",
      "src/app/api/ralph/check/handler.test.ts",
      "src/lib/reviewQueueCandidates.test.ts",
    ],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
