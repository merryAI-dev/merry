/**
 * POST /api/ralph/check
 *
 * multipart/form-data:
 *   text       — 추출된 문서 텍스트
 *   conditions — 조건 문자열 (여러 개 가능)
 *
 * Nova Pro 텍스트 기반 조건 충족 여부 검사
 */
import { NextResponse } from "next/server";
import { spawn } from "child_process";
import { writeFile, unlink } from "fs/promises";
import { join } from "path";
import { tmpdir } from "os";
import { randomUUID } from "crypto";

import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";
export const maxDuration = 60;

const PROJECT_ROOT = join(process.cwd(), "..");
const MAX_TEXT_CHARS = 120_000;
const CHECK_TIMEOUT_MS = 45_000;
const MAX_STDOUT_BYTES = 128 * 1024;
const MAX_STDERR_BYTES = 64 * 1024;
const KILL_GRACE_MS = 1_000;

type CheckerErrorCode =
  | "CHECK_TIMEOUT"
  | "CHECK_STDOUT_LIMIT"
  | "CHECK_STDERR_LIMIT"
  | "CHECK_EMPTY_OUTPUT"
  | "CHECK_OUTPUT_INVALID"
  | "CHECKER_EXITED"
  | "CHECKER_SPAWN_FAILED";

function checkerError(code: CheckerErrorCode, detail?: string) {
  const err = new Error(code) as Error & { detail?: string };
  err.detail = detail;
  return err;
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

function parseCheckerOutput(stdout: string): Record<string, unknown> {
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

async function runChecker(
  textPath: string,
  conditions: string[],
): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
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

export async function POST(req: Request) {
  let textPath: string | null = null;

  try {
    await requireWorkspaceFromCookies();
    const formData = await req.formData();
    const textValue = formData.get("text");
    const text = typeof textValue === "string" ? textValue.trim() : "";
    const conditions = formData
      .getAll("conditions")
      .map((value) => (typeof value === "string" ? value.trim() : ""))
      .filter(Boolean)
      .slice(0, 10);

    if (!text) {
      return NextResponse.json({ ok: false, error: "TEXT_REQUIRED" }, { status: 400 });
    }
    if (!conditions.length) {
      return NextResponse.json({ ok: false, error: "CONDITIONS_REQUIRED" }, { status: 400 });
    }
    if (text.length > MAX_TEXT_CHARS) {
      return NextResponse.json({ ok: false, error: "TEXT_TOO_LARGE" }, { status: 413 });
    }

    const uid = randomUUID();
    textPath = join(tmpdir(), `ralph_check_${uid}.txt`);
    await writeFile(textPath, text, "utf-8");

    const result = await runChecker(textPath, conditions);
    return NextResponse.json(result);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "CHECK_FAILED";
    const status =
      msg === "UNAUTHORIZED"
        ? 401
        : msg === "TEXT_TOO_LARGE"
          ? 413
          : msg === "CHECK_TIMEOUT"
            ? 504
            : msg === "CHECK_STDOUT_LIMIT" || msg === "CHECK_STDERR_LIMIT" || msg === "CHECK_EMPTY_OUTPUT" || msg === "CHECK_OUTPUT_INVALID"
              ? 502
              : 500;
    if (status >= 500 && msg !== "UNAUTHORIZED") {
      console.error("[RALPH] check route failed", {
        error: msg,
        detail: err instanceof Error && "detail" in err ? (err as Error & { detail?: string }).detail : undefined,
      });
    }
    return NextResponse.json({ ok: false, error: msg }, { status });
  } finally {
    if (textPath) await unlink(textPath).catch(() => {});
  }
}
