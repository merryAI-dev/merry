import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_PDF_BYTES,
  PARSE_TIMEOUT_MS,
  handleParseFormData,
  parserError,
} from "./handler.ts";

function buildFormData(file?: File, forcePro = false) {
  const form = new FormData();
  if (file) {
    form.set("file", file);
  }
  if (forcePro) {
    form.set("force_pro", "true");
  }
  return form;
}

test("handleParseFormData writes the PDF, forwards forcePro, and cleans up temp files", async () => {
  const sampleFile = new File([new Uint8Array([1, 2, 3, 4])], "sample.PDF", {
    type: "application/pdf",
  });
  const writes: Array<{ path: string; bytes: Buffer }> = [];
  let removedPath = "";

  const result = await handleParseFormData(buildFormData(sampleFile, true), {
    requireWorkspace: async () => undefined,
    createTempPath: () => "/tmp/ralph-parse-handler-test.pdf",
    writePdfFile: async (path, bytes) => {
      writes.push({ path, bytes });
    },
    removePdfFile: async (path) => {
      removedPath = path;
    },
    runParser: async (path, forcePro) => {
      assert.equal(path, "/tmp/ralph-parse-handler-test.pdf");
      assert.equal(forcePro, true);
      return {
        ok: true,
        text: "sample text",
        method: "nova_pro",
      };
    },
  });

  assert.equal(result.status, 200);
  assert.equal(writes[0]?.path, "/tmp/ralph-parse-handler-test.pdf");
  assert.deepEqual([...writes[0]?.bytes ?? []], [1, 2, 3, 4]);
  assert.equal(removedPath, "/tmp/ralph-parse-handler-test.pdf");
  assert.deepEqual(result.body, {
    ok: true,
    text: "sample text",
    method: "nova_pro",
  });
});

test("handleParseFormData returns 401 when workspace auth fails with a detailed reason", async () => {
  let called = false;
  const result = await handleParseFormData(
    buildFormData(new File([new Uint8Array([1])], "sample.pdf", { type: "application/pdf" })),
    {
      requireWorkspace: async () => {
        throw new Error("UNAUTHORIZED:NO_SESSION");
      },
      runParser: async () => {
        called = true;
        return {};
      },
    },
  );

  assert.equal(result.status, 401);
  assert.deepEqual(result.body, { ok: false, error: "UNAUTHORIZED:NO_SESSION" });
  assert.equal(called, false);
});

test("handleParseFormData rejects oversized PDFs before spawning the parser", async () => {
  let called = false;
  const largeFile = new File([new Uint8Array(MAX_PDF_BYTES + 1)], "large.pdf", {
    type: "application/pdf",
  });

  const result = await handleParseFormData(buildFormData(largeFile), {
    requireWorkspace: async () => undefined,
    runParser: async () => {
      called = true;
      return {};
    },
  });

  assert.equal(result.status, 413);
  assert.deepEqual(result.body, { ok: false, error: "FILE_TOO_LARGE" });
  assert.equal(called, false);
});

test("handleParseFormData maps parser timeout to 504", async () => {
  const result = await handleParseFormData(
    buildFormData(new File([new Uint8Array([1])], "sample.pdf", { type: "application/pdf" })),
    {
      requireWorkspace: async () => undefined,
      runParser: async () => {
        throw parserError("PARSE_TIMEOUT");
      },
    },
  );

  assert.equal(PARSE_TIMEOUT_MS, 90_000);
  assert.equal(result.status, 504);
  assert.deepEqual(result.body, { ok: false, error: "PARSE_TIMEOUT" });
});

test("handleParseFormData maps invalid parser output to 502", async () => {
  const result = await handleParseFormData(
    buildFormData(new File([new Uint8Array([1])], "sample.pdf", { type: "application/pdf" })),
    {
      requireWorkspace: async () => undefined,
      runParser: async () => {
        throw parserError("PARSE_OUTPUT_INVALID", "broken json");
      },
    },
  );

  assert.equal(result.status, 502);
  assert.deepEqual(result.body, { ok: false, error: "PARSE_OUTPUT_INVALID" });
});
