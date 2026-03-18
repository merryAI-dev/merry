import { describe, it, expect } from "vitest";
import { truncateExtractedText, buildFileContextBlock, extractFileContexts, MAX_COMBINED_FILE_CHARS } from "./reportChat";
import type { ChatMessageRow } from "./chatStore";

describe("truncateExtractedText", () => {
  it("returns text unchanged if under limit", () => {
    const { text, truncated } = truncateExtractedText("hello world", 100);
    expect(text).toBe("hello world");
    expect(truncated).toBe(false);
  });

  it("truncates text exceeding limit with marker", () => {
    const long = "A".repeat(1000);
    const { text, truncated } = truncateExtractedText(long, 100);
    expect(truncated).toBe(true);
    expect(text.length).toBeLessThanOrEqual(100);
    expect(text).toContain("[... 중략 ...]");
  });

  it("preserves head and tail portions", () => {
    const input = "HEAD" + "x".repeat(1000) + "TAIL";
    const { text } = truncateExtractedText(input, 200);
    expect(text.startsWith("HEAD")).toBe(true);
    expect(text.endsWith("TAIL")).toBe(true);
  });

  it("uses default 80K limit", () => {
    const short = "a".repeat(80_000);
    const { truncated } = truncateExtractedText(short);
    expect(truncated).toBe(false);

    const long = "a".repeat(80_001);
    const { truncated: t2 } = truncateExtractedText(long);
    expect(t2).toBe(true);
  });
});

describe("extractFileContexts", () => {
  it("returns empty array for no file context messages", () => {
    const messages: ChatMessageRow[] = [
      { session_id: "s1", user_id: "t1", role: "user", content: "hello", metadata: {} },
      { session_id: "s1", user_id: "t1", role: "assistant", content: "hi", metadata: {} },
    ];
    expect(extractFileContexts(messages)).toEqual([]);
  });

  it("extracts file contexts from report_file_context messages", () => {
    const messages: ChatMessageRow[] = [
      {
        session_id: "s1",
        user_id: "t1",
        role: "report_file_context",
        content: "첨부 문서: test.pdf",
        metadata: {
          fileId: "f1",
          originalName: "test.pdf",
          extractedText: "extracted content here",
          charCount: 22,
          extractedAt: "2026-01-01T00:00:00Z",
          warnings: [],
        },
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    const contexts = extractFileContexts(messages);
    expect(contexts).toHaveLength(1);
    expect(contexts[0].fileId).toBe("f1");
    expect(contexts[0].originalName).toBe("test.pdf");
    expect(contexts[0].extractedText).toBe("extracted content here");
  });

  it("skips file contexts with empty fileId or text", () => {
    const messages: ChatMessageRow[] = [
      {
        session_id: "s1",
        user_id: "t1",
        role: "report_file_context",
        content: "",
        metadata: { fileId: "", originalName: "bad.pdf", extractedText: "", charCount: 0 },
      },
    ];
    expect(extractFileContexts(messages)).toEqual([]);
  });
});

describe("buildFileContextBlock", () => {
  it("returns empty string for no contexts", () => {
    expect(buildFileContextBlock([])).toBe("");
  });

  it("builds formatted block for single file", () => {
    const block = buildFileContextBlock([
      {
        fileId: "f1",
        originalName: "report.pdf",
        extractedText: "some content",
        charCount: 12,
        extractedAt: "2026-01-01",
        warnings: [],
      },
    ]);
    expect(block).toContain("[첨부 문서]");
    expect(block).toContain("--- 파일: report.pdf ---");
    expect(block).toContain("some content");
    expect(block).toContain("--- 끝 ---");
  });

  it("respects combined character budget", () => {
    const largeText = "x".repeat(MAX_COMBINED_FILE_CHARS + 10000);
    const block = buildFileContextBlock([
      {
        fileId: "f1",
        originalName: "huge.pdf",
        extractedText: largeText,
        charCount: largeText.length,
        extractedAt: "2026-01-01",
        warnings: [],
      },
    ]);
    // Block should not exceed budget + formatting overhead
    expect(block.length).toBeLessThan(MAX_COMBINED_FILE_CHARS + 500);
  });
});
