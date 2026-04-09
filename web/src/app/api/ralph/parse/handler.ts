import { randomUUID } from "crypto";
import { writeFile, unlink } from "fs/promises";
import { tmpdir } from "os";
import { join } from "path";

import { InvokeCommand } from "@aws-sdk/client-lambda";

import { getLambdaClient } from "@/lib/aws/lambda";
import { parseExcelBuffer, parseExcelFromS3Detailed } from "@/lib/aws/s3Excel";

export const MAX_PDF_BYTES = 50 * 1024 * 1024;
export const PARSE_TIMEOUT_MS = 90_000;
const EXCEL_EXTS = new Set([".xlsx", ".xls"]);

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

function getExt(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot).toLowerCase() : "";
}

function buildExcelParseResponse(text: string, sheetCount: number): Record<string, unknown> {
  return {
    ok: true,
    text,
    pages: sheetCount,
    method: "xlsx",
    text_quality: 1,
    is_poor: false,
    is_fragmented: false,
    text_structure: "document",
    doc_type: "spreadsheet",
    confidence: 1,
    detection_method: "sheetjs",
    description: "Excel spreadsheet parsed as text",
    visual_description: null,
  };
}

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

/**
 * S3 키를 Lambda SDK로 직접 전달. API Gateway 29s 타임아웃 및 10MB 제한을 모두 우회.
 * Lambda가 S3에서 직접 다운로드 후 파싱 결과를 반환.
 */
export async function runParserS3(
  s3Key: string,
  s3Bucket: string,
  forcePro = false,
): Promise<Record<string, unknown>> {
  const functionName = (process.env.PARSER_LAMBDA_FUNCTION ?? "merry-parser").trim();
  const client = getLambdaClient();

  const payload = JSON.stringify({
    s3_key: s3Key,
    s3_bucket: s3Bucket,
    force_pro: forcePro,
  });

  const command = new InvokeCommand({
    FunctionName: functionName,
    InvocationType: "RequestResponse",
    Payload: new TextEncoder().encode(payload),
  });

  let responsePayload: Uint8Array | undefined;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), PARSE_TIMEOUT_MS);

  try {
    const response = await client.send(command, { abortSignal: controller.signal });
    if (response.FunctionError) {
      const errText = response.Payload
        ? new TextDecoder().decode(response.Payload).slice(0, 300)
        : response.FunctionError;
      throw parserError("PARSER_EXITED", errText);
    }
    responsePayload = response.Payload;
  } catch (err) {
    if (err instanceof Error && (err.name === "AbortError" || err.message.includes("abort"))) {
      throw parserError("PARSE_TIMEOUT");
    }
    if (err && typeof err === "object" && "code" in err) {
      throw parserError("PARSER_SPAWN_FAILED", String(err));
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }

  if (!responsePayload || responsePayload.length === 0) {
    throw parserError("PARSE_EMPTY_OUTPUT");
  }

  const resultText = new TextDecoder().decode(responsePayload);
  // Lambda direct invocation returns result directly (no statusCode wrapper)
  let result: Record<string, unknown>;
  try {
    result = JSON.parse(resultText) as Record<string, unknown>;
  } catch {
    throw parserError("PARSE_OUTPUT_INVALID", resultText.slice(0, 200));
  }

  if (!result || typeof result !== "object" || Array.isArray(result)) {
    throw parserError("PARSE_OUTPUT_INVALID", resultText.slice(0, 200));
  }

  // Lambda handler may return {ok: false, error: ...} for errors
  if (result.ok === false && typeof result.error === "string") {
    throw parserError("PARSER_EXITED", result.error as string);
  }

  return result;
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
    const ext = getExt(file.name);
    if (EXCEL_EXTS.has(ext)) {
      const parsed = parseExcelBuffer(Buffer.from(await file.arrayBuffer()));
      return { status: 200, body: buildExcelParseResponse(parsed.text, parsed.sheetCount) };
    }
    if (ext !== ".pdf") {
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

/* ── S3 key-based parse (bypasses Vercel 4.5MB + API Gateway 10MB limits) ── */

type S3ParseBody = {
  s3Key?: string;
  s3Bucket?: string;
  filename?: string;
  force_pro?: boolean;
};

type HandleParseS3Deps = {
  requireWorkspace: () => Promise<unknown>;
  runParserS3: typeof runParserS3;
  parseExcelFromS3?: typeof parseExcelFromS3Detailed;
};

export async function handleParseFromS3(
  body: S3ParseBody,
  deps: HandleParseS3Deps,
): Promise<{ status: number; body: Record<string, unknown> }> {
  try {
    await deps.requireWorkspace();

    const { s3Key, s3Bucket, force_pro } = body;
    if (!s3Key || !s3Bucket) {
      return { status: 400, body: { ok: false, error: "S3_KEY_REQUIRED" } };
    }

    const filename = typeof body.filename === "string" && body.filename.trim()
      ? body.filename
      : s3Key;
    const ext = getExt(filename);

    if (EXCEL_EXTS.has(ext)) {
      const parseExcel = deps.parseExcelFromS3 ?? parseExcelFromS3Detailed;
      const parsed = await parseExcel(s3Key, s3Bucket);
      return { status: 200, body: buildExcelParseResponse(parsed.text, parsed.sheetCount) };
    }

    // Lambda가 S3에서 직접 다운로드 (Vercel ↔ S3 ↔ API Gateway 이중 전송 제거)
    const result = await deps.runParserS3(s3Key, s3Bucket, !!force_pro);
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
  }
}
