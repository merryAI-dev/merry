import { describe, it, expect } from "vitest";
import { validateFilename, validateMimeType } from "./validation";

describe("validateFilename", () => {
  it("accepts valid filenames", () => {
    expect(validateFilename("report.pdf").ok).toBe(true);
    expect(validateFilename("my file (1).xlsx").ok).toBe(true);
    expect(validateFilename("한글파일.docx").ok).toBe(true);
  });

  it("rejects empty filenames", () => {
    expect(validateFilename("").ok).toBe(false);
    expect(validateFilename("   ").ok).toBe(false);
  });

  it("rejects path traversal", () => {
    const result = validateFilename("../../../etc/passwd");
    expect(result.ok).toBe(false);
  });

  it("rejects control characters", () => {
    expect(validateFilename("file\x00name.pdf").ok).toBe(false);
    expect(validateFilename("file|name.pdf").ok).toBe(false);
  });

  it("rejects hidden files", () => {
    expect(validateFilename(".env").ok).toBe(false);
    expect(validateFilename(".gitignore").ok).toBe(false);
  });

  it("rejects very long filenames", () => {
    const long = "a".repeat(256) + ".pdf";
    expect(validateFilename(long).ok).toBe(false);
  });
});

describe("validateMimeType", () => {
  it("accepts allowed MIME types", () => {
    expect(validateMimeType("application/pdf").ok).toBe(true);
    expect(validateMimeType("image/png").ok).toBe(true);
    expect(validateMimeType("text/plain").ok).toBe(true);
    expect(validateMimeType("application/json").ok).toBe(true);
  });

  it("rejects unknown MIME types", () => {
    expect(validateMimeType("application/x-shellscript").ok).toBe(false);
    expect(validateMimeType("video/mp4").ok).toBe(false);
  });

  it("cross-checks extension against MIME type", () => {
    // Mismatched: .pdf file claiming to be image/png
    const result = validateMimeType("image/png", "file.pdf");
    expect(result.ok).toBe(false);
  });

  it("allows octet-stream fallback for any extension", () => {
    expect(validateMimeType("application/octet-stream", "file.pdf").ok).toBe(true);
    expect(validateMimeType("application/octet-stream", "file.xlsx").ok).toBe(true);
  });
});
