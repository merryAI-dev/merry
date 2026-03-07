import assert from "node:assert/strict";
import test from "node:test";

import {
  CHECK_TIMEOUT_MS,
  MAX_TEXT_CHARS,
  checkerError,
  handleCheckFormData,
} from "./handler.ts";

function buildFormData(text: string, conditions: string[]) {
  const form = new FormData();
  form.set("text", text);
  for (const condition of conditions) {
    form.append("conditions", condition);
  }
  return form;
}

test("handleCheckFormData trims, drops blanks, limits conditions, and preserves parse warnings", async () => {
  const calls: Array<{ path: string; text: string; conditions: string[] }> = [];
  let cleanedPath = "";
  const result = await handleCheckFormData(
    buildFormData("  sample text  ", [" 조건1 ", "", "  ", ...Array.from({ length: 12 }, (_, i) => ` 조건${i + 2} `)]),
    {
      requireWorkspace: async () => undefined,
      createTempPath: () => "/tmp/ralph-handler-test.txt",
      writeTextFile: async (path, text) => {
        calls.push({ path, text, conditions: [] });
      },
      removeTextFile: async (path) => {
        cleanedPath = path;
      },
      runChecker: async (path, conditions) => {
        calls.push({ path, text: "", conditions });
        return {
          company_name: "테스트 기업",
          parse_warning: "JSON_PARSE_FAILED",
          raw_response: "{bad json",
          conditions: conditions.map((condition) => ({
            condition,
            result: false,
            evidence: "문서에서 확인 불가",
          })),
        };
      },
    },
  );

  assert.equal(result.status, 200);
  assert.equal(calls[0]?.path, "/tmp/ralph-handler-test.txt");
  assert.equal(calls[0]?.text, "sample text");
  assert.deepEqual(calls[1]?.conditions, [
    "조건1",
    "조건2",
    "조건3",
    "조건4",
    "조건5",
    "조건6",
    "조건7",
    "조건8",
    "조건9",
    "조건10",
  ]);
  assert.equal(result.body.parse_warning, "JSON_PARSE_FAILED");
  assert.equal(result.body.raw_response, "{bad json");
  assert.equal(cleanedPath, "/tmp/ralph-handler-test.txt");
});

test("handleCheckFormData returns 401 when workspace auth fails", async () => {
  let called = false;
  const result = await handleCheckFormData(
    buildFormData("sample", ["조건1"]),
    {
      requireWorkspace: async () => {
        throw new Error("UNAUTHORIZED");
      },
      runChecker: async () => {
        called = true;
        return {};
      },
    },
  );

  assert.equal(result.status, 401);
  assert.deepEqual(result.body, { ok: false, error: "UNAUTHORIZED" });
  assert.equal(called, false);
});

test("handleCheckFormData rejects oversized text before running the checker", async () => {
  let called = false;
  const result = await handleCheckFormData(
    buildFormData("x".repeat(MAX_TEXT_CHARS + 1), ["조건1"]),
    {
      requireWorkspace: async () => undefined,
      runChecker: async () => {
        called = true;
        return {};
      },
    },
  );

  assert.equal(result.status, 413);
  assert.deepEqual(result.body, { ok: false, error: "TEXT_TOO_LARGE" });
  assert.equal(called, false);
});

test("handleCheckFormData maps checker timeout to 504", async () => {
  const result = await handleCheckFormData(
    buildFormData("sample", ["조건1"]),
    {
      requireWorkspace: async () => undefined,
      runChecker: async () => {
        throw checkerError("CHECK_TIMEOUT");
      },
    },
  );

  assert.equal(CHECK_TIMEOUT_MS, 45_000);
  assert.equal(result.status, 504);
  assert.deepEqual(result.body, { ok: false, error: "CHECK_TIMEOUT" });
});

test("handleCheckFormData maps invalid checker output to 502", async () => {
  const result = await handleCheckFormData(
    buildFormData("sample", ["조건1"]),
    {
      requireWorkspace: async () => undefined,
      runChecker: async () => {
        throw checkerError("CHECK_OUTPUT_INVALID", "broken");
      },
    },
  );

  assert.equal(result.status, 502);
  assert.deepEqual(result.body, { ok: false, error: "CHECK_OUTPUT_INVALID" });
});
