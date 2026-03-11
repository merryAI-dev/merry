/**
 * Input validation utilities for API routes and client-side forms.
 *
 * Guards against path traversal, injection patterns, and malformed input.
 */

/* ── Filename validation ── */

/** Characters that are never allowed in filenames (path traversal, control chars). */
const FILENAME_DENY_PATTERN = /[<>:"|?*\x00-\x1f\\]/;
const PATH_TRAVERSAL_PATTERN = /\.\.\//;
const MAX_FILENAME_LENGTH = 255;

export function validateFilename(filename: string): { ok: true } | { ok: false; reason: string } {
  if (!filename || typeof filename !== "string") {
    return { ok: false, reason: "EMPTY_FILENAME" };
  }
  const trimmed = filename.trim();
  if (trimmed.length === 0) {
    return { ok: false, reason: "EMPTY_FILENAME" };
  }
  if (trimmed.length > MAX_FILENAME_LENGTH) {
    return { ok: false, reason: "FILENAME_TOO_LONG" };
  }
  if (FILENAME_DENY_PATTERN.test(trimmed)) {
    return { ok: false, reason: "INVALID_CHARACTERS" };
  }
  if (PATH_TRAVERSAL_PATTERN.test(trimmed)) {
    return { ok: false, reason: "PATH_TRAVERSAL" };
  }
  // Reject hidden files (Unix dotfiles).
  if (trimmed.startsWith(".")) {
    return { ok: false, reason: "HIDDEN_FILE" };
  }
  return { ok: true };
}

/* ── MIME type validation ── */

const ALLOWED_MIMES: ReadonlySet<string> = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  // xlsx
  "application/vnd.ms-excel",  // xls
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  // docx
  "application/octet-stream",  // fallback
]);

const EXT_TO_MIME: Record<string, string> = {
  ".pdf": "application/pdf",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".xls": "application/vnd.ms-excel",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};

export function validateMimeType(
  contentType: string,
  filename?: string,
): { ok: true } | { ok: false; reason: string } {
  if (!ALLOWED_MIMES.has(contentType)) {
    return { ok: false, reason: "UNSUPPORTED_MIME_TYPE" };
  }
  // Cross-check: if filename has a known extension, MIME should match.
  if (filename) {
    const dot = filename.lastIndexOf(".");
    if (dot !== -1) {
      const ext = filename.slice(dot).toLowerCase();
      const expectedMime = EXT_TO_MIME[ext];
      if (
        expectedMime &&
        contentType !== expectedMime &&
        contentType !== "application/octet-stream"
      ) {
        return { ok: false, reason: "MIME_EXTENSION_MISMATCH" };
      }
    }
  }
  return { ok: true };
}

/* ── Search query sanitization ── */

const MAX_SEARCH_LENGTH = 200;

/** Strip characters that could cause issues in downstream queries. */
export function sanitizeSearchQuery(raw: string): string {
  return raw
    .replace(/[<>"'`;]/g, "")  // Strip injection-prone chars
    .trim()
    .slice(0, MAX_SEARCH_LENGTH);
}

/* ── Text field size limits (DynamoDB 400KB item safety) ── */

/** Max chars for user-editable content fields (drafts, stash, report messages). */
export const MAX_CONTENT_LENGTH = 50_000;
/** Max chars for short text fields (titles, names, labels). */
export const MAX_TITLE_LENGTH = 500;
/** Max chars for comment text. */
export const MAX_COMMENT_LENGTH = 5_000;
/** Max chars for ID-like fields (UUIDs, job IDs, etc.). */
export const MAX_ID_LENGTH = 128;

/* ── Generic string bounds ── */

export function validateStringLength(
  value: string,
  { min = 0, max = 1000 }: { min?: number; max?: number } = {},
): { ok: true } | { ok: false; reason: string } {
  if (value.length < min) return { ok: false, reason: "TOO_SHORT" };
  if (value.length > max) return { ok: false, reason: "TOO_LONG" };
  return { ok: true };
}
