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

import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";
export const maxDuration = 60;

const PROJECT_ROOT = join(process.cwd(), "..");

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

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (d: Buffer) => { stdout += d.toString(); });
    proc.stderr.on("data", (d: Buffer) => { stderr += d.toString(); });

    proc.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`checker exited ${code}: ${stderr.slice(0, 300)}`));
        return;
      }
      try {
        const lines = stdout.trim().split("\n");
        const jsonLine = lines.findLast((l) => l.trim().startsWith("{")) ?? "";
        resolve(JSON.parse(jsonLine));
      } catch {
        reject(new Error(`JSON parse failed. stdout=${stdout.slice(0, 200)}`));
      }
    });

    proc.on("error", reject);
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

    const uid = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    textPath = join(tmpdir(), `ralph_check_${uid}.txt`);
    await writeFile(textPath, text, "utf-8");

    const result = await runChecker(textPath, conditions);
    return NextResponse.json(result);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "CHECK_FAILED";
    const status = msg === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: msg }, { status });
  } finally {
    if (textPath) await unlink(textPath).catch(() => {});
  }
}
