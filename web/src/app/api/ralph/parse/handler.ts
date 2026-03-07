import { randomUUID } from "crypto";
import { spawn } from "child_process";
import { writeFile, unlink } from "fs/promises";
import { tmpdir } from "os";
import { join } from "path";

const PROJECT_ROOT = join(process.cwd(), "..");
export const MAX_PDF_BYTES = 50 * 1024 * 1024;
export const PARSE_TIMEOUT_MS = 45_000;
const MAX_STDOUT_BYTES = 256 * 1024;
const MAX_STDERR_BYTES = 64 * 1024;
const KILL_GRACE_MS = 1_000;

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
  return await new Promise((resolve, reject) => {
    const scriptPath = join(PROJECT_ROOT, "ralph", "playground_parser.py");
    const proc = spawn("python3", [scriptPath, pdfPath], {
      cwd: PROJECT_ROOT,
      env: {
        ...process.env,
        PYTHONPATH: PROJECT_ROOT,
        ...(forcePro ? { RALPH_FORCE_PRO: "true" } : {}),
      },
    });

    let settled = false;
    const stdoutChunks: Buffer[] = [];
    const stderrChunks: Buffer[] = [];
    let stdoutBytes = 0;
    let stderrBytes = 0;

    const settleResolve = (value: Record<string, unknown>) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeoutId);
      resolve(value);
    };

    const settleReject = (err: Error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeoutId);
      reject(err);
    };

    const terminate = (err: Error) => {
      if (settled) return;
      proc.kill("SIGTERM");
      const killId = setTimeout(() => {
        proc.kill("SIGKILL");
      }, KILL_GRACE_MS);
      killId.unref();
      settleReject(err);
    };

    const timeoutId = setTimeout(() => {
      terminate(parserError("PARSE_TIMEOUT"));
    }, PARSE_TIMEOUT_MS);
    timeoutId.unref();

    proc.stdout.on("data", (chunk: Buffer) => {
      const next = pushCappedChunk(stdoutChunks, chunk, stdoutBytes, MAX_STDOUT_BYTES);
      stdoutBytes = next.bytes;
      if (next.overflow) {
        terminate(parserError("PARSE_STDOUT_LIMIT"));
      }
    });

    proc.stderr.on("data", (chunk: Buffer) => {
      const next = pushCappedChunk(stderrChunks, chunk, stderrBytes, MAX_STDERR_BYTES);
      stderrBytes = next.bytes;
      if (next.overflow) {
        terminate(parserError("PARSE_STDERR_LIMIT"));
      }
    });

    proc.on("close", (code, signal) => {
      if (settled) return;
      const stdout = Buffer.concat(stdoutChunks).toString("utf8");
      const stderr = Buffer.concat(stderrChunks).toString("utf8");
      if (code !== 0) {
        settleReject(parserError("PARSER_EXITED", `${code ?? signal ?? "unknown"}:${stderr.slice(0, 300)}`));
        return;
      }
      try {
        settleResolve(parseParserOutput(stdout));
      } catch (err) {
        settleReject(err instanceof Error ? err : parserError("PARSE_OUTPUT_INVALID"));
      }
    });

    proc.on("error", (err) => {
      settleReject(parserError("PARSER_SPAWN_FAILED", err.message));
    });
  });
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
