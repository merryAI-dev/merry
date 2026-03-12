import { randomUUID } from "crypto";
import { writeFile, unlink } from "fs/promises";
import { tmpdir } from "os";
import { join } from "path";
import { GetObjectCommand } from "@aws-sdk/client-s3";
import { getS3Client } from "@/lib/aws/s3";

export const MAX_PDF_BYTES = 50 * 1024 * 1024;
export const PARSE_TIMEOUT_MS = 45_000;

export type ParserErrorCode =
  | "PARSE_TIMEOUT"
  | "PARSE_STDOUT_LIMIT"
  | "PARSE_STDERR_LIMIT"
  | "PARSE_EMPTY_OUTPUT"
  | "PARSE_OUTPUT_INVALID"
  | "PARSER_EXITED"
  | "PARSER_SPAWN_FAILED";

export type ParserRunner = (
  pdfPath: string,
  forcePro: boolean,
) => Promise<Record<string, unknown>>;

type ParserError = Error & { detail?: string };

type HandleParseDeps = {
  requireWorkspace: () => Promise<unknown>;
  runParser: ParserRunner;
  createTempPath?: () => string;
  writePdfFile?: (path: string, bytes: Buffer) => Promise<void>;
  removePdfFile?: (path: string) => Promise<void>;
};

export function parserError(code: ParserErrorCode, detail?: string) {
  const err = new Error(code) as ParserError;
  err.detail = detail;
  return err;
}

function isUnauthorizedError(message: string) {
  return message === "UNAUTHORIZED" || message.startsWith("UNAUTHORIZED:");
}

function pushCappedChunk(
  chunks: Buffer[],
  chunk: Buffer,
  currentBytes: number,
  maxBytes: number,
): { bytes: number; overflow: boolean } {
  if (currentBytes >= maxBytes) {
    return { bytes: currentBytes, overflow: true };
  }

  const remaining = maxBytes - currentBytes;
  if (chunk.length <= remaining) {
    chunks.push(chunk);
    return { bytes: currentBytes + chunk.length, overflow: false };
  }

  if (remaining > 0) {
    chunks.push(chunk.subarray(0, remaining));
  }
  return { bytes: maxBytes, overflow: true };
}

export function parseParserOutput(stdout: string): Record<string, unknown> {
  const trimmed = stdout.trim();
  if (!trimmed) {
    throw parserError("PARSE_EMPTY_OUTPUT");
  }

  const candidates = [
    trimmed,
    ...trimmed
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.startsWith("{") && line.endsWith("}"))
      .reverse(),
  ];

  const blockMatch = trimmed.match(/\{[\s\S]*\}$/);
  if (blockMatch) {
    candidates.push(blockMatch[0]);
  }

  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate) as Record<string, unknown>;
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return parsed;
      }
    } catch {
      // Try next candidate.
    }
  }

  throw parserError("PARSE_OUTPUT_INVALID", trimmed.slice(0, 200));
}

export async function runParser(
  pdfPath: string,
  forcePro = false,
): Promise<Record<string, unknown>> {
  const parserUrl = process.env.PARSER_INTERNAL_URL;
  if (!parserUrl) {
    throw parserError("PARSER_SPAWN_FAILED", "Missing env PARSER_INTERNAL_URL");
  }

  const apiKey = process.env.PARSER_API_KEY ?? "";
  const pdfBytes = await import("fs/promises").then((fs) => fs.readFile(pdfPath));

  const url = `${parserUrl}/parse${forcePro ? "?force_pro=true" : ""}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), PARSE_TIMEOUT_MS);

  let resp: Response;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/pdf",
        "Content-Length": String(pdfBytes.length),
        ...(apiKey ? { "x-api-key": apiKey } : {}),
      },
      body: pdfBytes,
      signal: controller.signal,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    throw parserError(
      msg.includes("abort") ? "PARSE_TIMEOUT" : "PARSER_SPAWN_FAILED",
      msg,
    );
  } finally {
    clearTimeout(timeoutId);
  }

  const text = await resp.text();
  if (!resp.ok) {
    throw parserError("PARSER_EXITED", `HTTP ${resp.status}: ${text.slice(0, 300)}`);
  }
  return parseParserOutput(text);
}

function defaultTempPath() {
  return join(tmpdir(), `ralph_pg_${randomUUID()}.pdf`);
}

function defaultWritePdfFile(path: string, bytes: Buffer) {
  return writeFile(path, bytes);
}

function defaultRemovePdfFile(path: string) {
  return unlink(path).catch(() => {});
}

export async function handleParseFormData(
  formData: FormData,
  deps: HandleParseDeps,
): Promise<{ status: number; body: Record<string, unknown> }> {
  let pdfPath: string | null = null;
  const createTempPath = deps.createTempPath ?? defaultTempPath;
  const writePdfFile = deps.writePdfFile ?? defaultWritePdfFile;
  const removePdfFile = deps.removePdfFile ?? defaultRemovePdfFile;

  try {
    await deps.requireWorkspace();
    const fileValue = formData.get("file");
    const file = fileValue instanceof File ? fileValue : null;

    if (!file) {
      return { status: 400, body: { ok: false, error: "FILE_REQUIRED" } };
    }
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      return { status: 400, body: { ok: false, error: "PDF_ONLY" } };
    }
    if (file.size > MAX_PDF_BYTES) {
      return { status: 413, body: { ok: false, error: "FILE_TOO_LARGE" } };
    }

    pdfPath = createTempPath();
    await writePdfFile(pdfPath, Buffer.from(await file.arrayBuffer()));
    const forcePro = formData.get("force_pro") === "true";
    const result = await deps.runParser(pdfPath, forcePro);
    return { status: 200, body: result };
  } catch (err) {
    const message = err instanceof Error ? err.message : "PARSE_FAILED";
    const status =
      isUnauthorizedError(message)
        ? 401
        : message === "FILE_TOO_LARGE"
          ? 413
          : message === "PARSE_TIMEOUT"
            ? 504
            : message === "PARSE_STDOUT_LIMIT" ||
                message === "PARSE_STDERR_LIMIT" ||
                message === "PARSE_EMPTY_OUTPUT" ||
                message === "PARSE_OUTPUT_INVALID"
              ? 502
              : 500;
    return { status, body: { ok: false, error: message } };
  } finally {
    if (pdfPath) {
      await removePdfFile(pdfPath);
    }
  }
}

/* ── S3 key-based parse (bypasses Vercel 4.5MB body limit) ── */

type S3ParseBody = {
  s3Key?: string;
  s3Bucket?: string;
  filename?: string;
  force_pro?: boolean;
};

type HandleParseS3Deps = {
  requireWorkspace: () => Promise<unknown>;
  runParser: ParserRunner;
};

export async function handleParseFromS3(
  body: S3ParseBody,
  deps: HandleParseS3Deps,
): Promise<{ status: number; body: Record<string, unknown> }> {
  let pdfPath: string | null = null;

  try {
    await deps.requireWorkspace();

    const { s3Key, s3Bucket, force_pro } = body;
    if (!s3Key || !s3Bucket) {
      return { status: 400, body: { ok: false, error: "S3_KEY_REQUIRED" } };
    }

    // Download from S3 to temp file
    const s3 = getS3Client();
    const obj = await s3.send(new GetObjectCommand({ Bucket: s3Bucket, Key: s3Key }));
    if (!obj.Body) {
      return { status: 404, body: { ok: false, error: "S3_OBJECT_NOT_FOUND" } };
    }

    const chunks: Buffer[] = [];
    // @ts-expect-error — Body is a Readable stream in Node.js runtime
    for await (const chunk of obj.Body) {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    }
    const pdfBytes = Buffer.concat(chunks);

    if (pdfBytes.length > MAX_PDF_BYTES) {
      return { status: 413, body: { ok: false, error: "FILE_TOO_LARGE" } };
    }

    pdfPath = join(tmpdir(), `ralph_s3_${randomUUID()}.pdf`);
    await writeFile(pdfPath, pdfBytes);

    const result = await deps.runParser(pdfPath, !!force_pro);
    return { status: 200, body: result };
  } catch (err) {
    const message = err instanceof Error ? err.message : "PARSE_FAILED";
    const isUnauth = message === "UNAUTHORIZED" || message.startsWith("UNAUTHORIZED:");
    const status = isUnauth
      ? 401
      : message === "FILE_TOO_LARGE"
        ? 413
        : message === "PARSE_TIMEOUT"
          ? 504
          : 500;
    return { status, body: { ok: false, error: message } };
  } finally {
    if (pdfPath) {
      await unlink(pdfPath).catch(() => {});
    }
  }
}
