/**
 * POST /api/ralph/parse
 *
 * multipart/form-data: file (PDF)
 *
 * 응답: playground_parser.py의 JSON 결과를 그대로 전달
 * - PyMuPDF 텍스트 우선, 스캔 문서면 Nova Lite 시각 추출 추가
 */
import { NextResponse } from "next/server";
import { spawn } from "child_process";
import { writeFile, unlink } from "fs/promises";
import { join } from "path";
import { tmpdir } from "os";

export const runtime = "nodejs";
export const maxDuration = 60;

const PROJECT_ROOT = join(process.cwd(), ".."); // merry/

async function runParser(pdfPath: string): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const scriptPath = join(PROJECT_ROOT, "ralph", "playground_parser.py");

    const proc = spawn("python3", [scriptPath, pdfPath], {
      cwd: PROJECT_ROOT,
      env: { ...process.env, PYTHONPATH: PROJECT_ROOT },
    });

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (d: Buffer) => { stdout += d.toString(); });
    proc.stderr.on("data", (d: Buffer) => { stderr += d.toString(); });

    proc.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`parser exited ${code}: ${stderr.slice(0, 300)}`));
        return;
      }
      try {
        // stdout에 로그가 섞여 있을 수 있으니 마지막 JSON 라인만 파싱
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
  let tempPath: string | null = null;

  try {
    const formData = await req.formData();
    const file = formData.get("file") as File | null;

    if (!file) {
      return NextResponse.json({ ok: false, error: "FILE_REQUIRED" }, { status: 400 });
    }
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      return NextResponse.json({ ok: false, error: "PDF_ONLY" }, { status: 400 });
    }
    if (file.size > 50 * 1024 * 1024) {
      return NextResponse.json({ ok: false, error: "FILE_TOO_LARGE" }, { status: 400 });
    }

    const bytes = await file.arrayBuffer();
    const uid = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    tempPath = join(tmpdir(), `ralph_pg_${uid}.pdf`);
    await writeFile(tempPath, Buffer.from(bytes));

    const result = await runParser(tempPath);
    return NextResponse.json(result);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "PARSE_FAILED";
    return NextResponse.json({ ok: false, error: msg }, { status: 500 });
  } finally {
    if (tempPath) await unlink(tempPath).catch(() => {});
  }
}
