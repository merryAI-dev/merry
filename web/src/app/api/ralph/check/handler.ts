import { spawn } from "child_process";
import { writeFile, unlink } from "fs/promises";
import { join } from "path";
import { tmpdir } from "os";
import { randomUUID } from "crypto";

const PROJECT_ROOT = join(process.cwd(), "..");
export const MAX_TEXT_CHARS = 120_000;
export const CHECK_TIMEOUT_MS = 45_000;
const MAX_STDOUT_BYTES = 128 * 1024;
const MAX_STDERR_BYTES = 64 * 1024;
const KILL_GRACE_MS = 1_000;

export type CheckerErrorCode =
  | "CHECK_TIMEOUT"
  | "CHECK_STDOUT_LIMIT"
  | "CHECK_STDERR_LIMIT"
  | "CHECK_EMPTY_OUTPUT"
  | "CHECK_OUTPUT_INVALID"
  | "CHECKER_EXITED"
  | "CHECKER_SPAWN_FAILED";

export type CheckerRunner = (
  textPath: string,
  conditions: string[],
) => Promise<Record<string, unknown>>;

type CheckerError = Error & { detail?: string };

type HandleCheckDeps = {
  requireWorkspace: () => Promise<unknown>;
  runChecker: CheckerRunner;
  createTempPath?: () => string;
  writeTextFile?: (path: string, text: string) => Promise<void>;
  removeTextFile?: (path: string) => Promise<void>;
};

export function checkerError(code: CheckerErrorCode, detail?: string) {
  const err = new Error(code) as CheckerError;
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

export function parseCheckerOutput(stdout: string): Record<string, unknown> {
  const trimmed = stdout.trim();
  if (!trimmed) {
    throw checkerError("CHECK_EMPTY_OUTPUT");
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

  throw checkerError("CHECK_OUTPUT_INVALID", trimmed.slice(0, 200));
}

export async function runChecker(
  textPath: string,
  conditions: string[],
): Promise<Record<string, unknown>> {
  return await new Promise((resolve, reject) => {
    const scriptPath = join(PROJECT_ROOT, "ralph", "condition_checker.py");

    const proc = spawn("python3", [scriptPath, textPath], {
      cwd: PROJECT_ROOT,
      env: {
        ...process.env,
        PYTHONPATH: PROJECT_ROOT,
        RALPH_CONDITIONS: JSON.stringify(conditions),
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
      terminate(checkerError("CHECK_TIMEOUT"));
    }, CHECK_TIMEOUT_MS);
    timeoutId.unref();

    proc.stdout.on("data", (chunk: Buffer) => {
      const next = pushCappedChunk(stdoutChunks, chunk, stdoutBytes, MAX_STDOUT_BYTES);
      stdoutBytes = next.bytes;
      if (next.overflow) {
        terminate(checkerError("CHECK_STDOUT_LIMIT"));
      }
    });

    proc.stderr.on("data", (chunk: Buffer) => {
      const next = pushCappedChunk(stderrChunks, chunk, stderrBytes, MAX_STDERR_BYTES);
      stderrBytes = next.bytes;
      if (next.overflow) {
        terminate(checkerError("CHECK_STDERR_LIMIT"));
      }
    });

    proc.on("close", (code, signal) => {
      if (settled) return;
      const stdout = Buffer.concat(stdoutChunks).toString("utf8");
      const stderr = Buffer.concat(stderrChunks).toString("utf8");
      if (code !== 0) {
        settleReject(checkerError("CHECKER_EXITED", `${code ?? signal ?? "unknown"}:${stderr.slice(0, 300)}`));
        return;
      }
      try {
        settleResolve(parseCheckerOutput(stdout));
      } catch (err) {
        settleReject(err instanceof Error ? err : checkerError("CHECK_OUTPUT_INVALID"));
      }
    });

    proc.on("error", (err) => {
      settleReject(checkerError("CHECKER_SPAWN_FAILED", err.message));
    });
  });
}

function defaultTempPath() {
  return join(tmpdir(), `ralph_check_${randomUUID()}.txt`);
}

function defaultWriteTextFile(path: string, text: string) {
  return writeFile(path, text, "utf-8");
}

function defaultRemoveTextFile(path: string) {
  return unlink(path).catch(() => {});
}

export async function handleCheckFormData(
  formData: FormData,
  deps: HandleCheckDeps,
): Promise<{ status: number; body: Record<string, unknown> }> {
  let textPath: string | null = null;
  const createTempPath = deps.createTempPath ?? defaultTempPath;
  const writeTextFile = deps.writeTextFile ?? defaultWriteTextFile;
  const removeTextFile = deps.removeTextFile ?? defaultRemoveTextFile;

  try {
    await deps.requireWorkspace();
    const textValue = formData.get("text");
    const text = typeof textValue === "string" ? textValue.trim() : "";
    const conditions = formData
      .getAll("conditions")
      .map((value) => (typeof value === "string" ? value.trim() : ""))
      .filter(Boolean)
      .slice(0, 10);

    if (!text) {
      return { status: 400, body: { ok: false, error: "TEXT_REQUIRED" } };
    }
    if (!conditions.length) {
      return { status: 400, body: { ok: false, error: "CONDITIONS_REQUIRED" } };
    }
    if (text.length > MAX_TEXT_CHARS) {
      return { status: 413, body: { ok: false, error: "TEXT_TOO_LARGE" } };
    }

    textPath = createTempPath();
    await writeTextFile(textPath, text);
    const result = await deps.runChecker(textPath, conditions);
    return { status: 200, body: result };
  } catch (err) {
    const msg = err instanceof Error ? err.message : "CHECK_FAILED";
    const status =
      isUnauthorizedError(msg)
        ? 401
        : msg === "TEXT_TOO_LARGE"
          ? 413
          : msg === "CHECK_TIMEOUT"
            ? 504
            : msg === "CHECK_STDOUT_LIMIT" || msg === "CHECK_STDERR_LIMIT" || msg === "CHECK_EMPTY_OUTPUT" || msg === "CHECK_OUTPUT_INVALID"
              ? 502
              : 500;
    return { status, body: { ok: false, error: msg } };
  } finally {
    if (textPath) {
      await removeTextFile(textPath);
    }
  }
}
