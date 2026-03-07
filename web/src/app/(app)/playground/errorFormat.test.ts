import assert from "node:assert/strict";
import test from "node:test";

import { formatCheckError, formatParseError } from "./errorFormat.ts";

test("formatParseError maps detailed auth failures to a friendly login message", () => {
  assert.equal(
    formatParseError("UNAUTHORIZED:NO_SESSION"),
    "Ralph Playground를 사용하려면 로그인 상태가 필요합니다.",
  );
});

test("formatCheckError maps detailed auth failures to a friendly login message", () => {
  assert.equal(
    formatCheckError("UNAUTHORIZED:DOMAIN_MISMATCH"),
    "Ralph Playground를 사용하려면 로그인 상태가 필요합니다.",
  );
});

test("formatParseError preserves parse timeout guidance", () => {
  assert.equal(
    formatParseError("PARSE_TIMEOUT"),
    "문서 파싱 시간이 초과되었습니다. 페이지 수를 줄이거나 문서를 나눠서 다시 시도하세요.",
  );
});
