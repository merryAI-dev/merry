import { spawn } from "child_process";
import { mkdir, writeFile } from "fs/promises";
import { join, resolve } from "path";

import type { DiagnosisAnalysisSummary, DiagnosisMessageRole } from "@/lib/diagnosisTypes";
import type { UploadFileRecord } from "@/lib/jobStore";
import { readBytesFromS3 } from "@/lib/aws/s3Utils";

const PROJECT_ROOT = resolve(process.cwd(), "..");
const SCRIPT_PATH = join(PROJECT_ROOT, "scripts", "diagnosis_chat_bridge.py");
const MAX_STDOUT_BYTES = 256 * 1024;
const MAX_STDERR_BYTES = 64 * 1024;
const TIMEOUT_MS = 120_000;

function sanitizePathPart(value: string) {
  return value.replace(/[^a-zA-Z0-9._-]+/g, "_").replace(/^_+|_+$/g, "") || "diagnosis";
}

function pushChunk(
  chunks: Buffer[],
  chunk: Buffer,
  currentBytes: number,
  maxBytes: number,
): { bytes: number; overflow: boolean } {
  if (currentBytes >= maxBytes) return { bytes: currentBytes, overflow: true };
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

function parseBridgeOutput(stdout: string): DiagnosisAgentTurnResult {
  const parsed = JSON.parse(stdout.trim()) as Record<string, unknown>;
  if (parsed["ok"] !== true) {
    throw new Error(typeof parsed["error"] === "string" ? parsed["error"] : "DIAGNOSIS_AGENT_FAILED");
  }
  return {
    assistantText: typeof parsed["assistant_text"] === "string" ? parsed["assistant_text"] : "",
    analysisSummary: (parsed["analysis_summary"] as DiagnosisAnalysisSummary | null | undefined) ?? null,
    latestGeneratedFile:
      typeof parsed["latest_generated_file"] === "string" && parsed["latest_generated_file"]
        ? parsed["latest_generated_file"]
        : null,
  };
}

export type DiagnosisVisibleMessage = {
  role: DiagnosisMessageRole;
  content: string;
};

export type DiagnosisAgentTurnMode = "start" | "reply" | "generate";

export type DiagnosisAgentTurnInput = {
  mode: DiagnosisAgentTurnMode;
  prompt: string;
  history: DiagnosisVisibleMessage[];
  sessionId: string;
  teamId: string;
  memberName: string;
  model?: string;
  sourceFilePath?: string;
};

export type DiagnosisAgentTurnResult = {
  assistantText: string;
  analysisSummary: DiagnosisAnalysisSummary | null;
  latestGeneratedFile: string | null;
};

export type MaterializedDiagnosisSourceFile = {
  fileId: string;
  originalName: string;
  contentType: string;
  localPath: string;
};

export async function materializeDiagnosisSourceFile(args: {
  teamId: string;
  sessionId: string;
  file: UploadFileRecord;
}): Promise<MaterializedDiagnosisSourceFile> {
  const safeDir = sanitizePathPart(`diagnosis_${args.teamId}_${args.sessionId}`);
  const safeFile = sanitizePathPart(args.file.originalName);
  const dirPath = join(PROJECT_ROOT, "temp", safeDir);
  const localPath = join(dirPath, `${args.file.fileId}_${safeFile}`);
  await mkdir(dirPath, { recursive: true });
  const bytes = await readBytesFromS3(args.file.s3Key, args.file.s3Bucket);
  await writeFile(localPath, bytes);
  return {
    fileId: args.file.fileId,
    originalName: args.file.originalName,
    contentType: args.file.contentType,
    localPath,
  };
}

export async function runDiagnosisAgentTurn(input: DiagnosisAgentTurnInput): Promise<DiagnosisAgentTurnResult> {
  return await new Promise((resolvePromise, rejectPromise) => {
    const proc = spawn("python3", [SCRIPT_PATH], {
      cwd: PROJECT_ROOT,
      env: {
        ...process.env,
        PYTHONPATH: PROJECT_ROOT,
      },
    });

    const stdoutChunks: Buffer[] = [];
    const stderrChunks: Buffer[] = [];
    let stdoutBytes = 0;
    let stderrBytes = 0;
    let settled = false;

    const finish = (err?: Error, result?: DiagnosisAgentTurnResult) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeoutId);
      if (err) rejectPromise(err);
      else if (result) resolvePromise(result);
    };

    const timeoutId = setTimeout(() => {
      proc.kill("SIGTERM");
      finish(new Error("DIAGNOSIS_AGENT_TIMEOUT"));
    }, TIMEOUT_MS);
    timeoutId.unref();

    proc.stdout.on("data", (chunk: Buffer) => {
      const next = pushChunk(stdoutChunks, chunk, stdoutBytes, MAX_STDOUT_BYTES);
      stdoutBytes = next.bytes;
      if (next.overflow) {
        proc.kill("SIGTERM");
        finish(new Error("DIAGNOSIS_AGENT_STDOUT_LIMIT"));
      }
    });

    proc.stderr.on("data", (chunk: Buffer) => {
      const next = pushChunk(stderrChunks, chunk, stderrBytes, MAX_STDERR_BYTES);
      stderrBytes = next.bytes;
      if (next.overflow) {
        proc.kill("SIGTERM");
        finish(new Error("DIAGNOSIS_AGENT_STDERR_LIMIT"));
      }
    });

    proc.on("error", (err) => {
      finish(new Error(`DIAGNOSIS_AGENT_SPAWN_FAILED:${err.message}`));
    });

    proc.on("close", (code) => {
      if (settled) return;
      const stdout = Buffer.concat(stdoutChunks).toString("utf-8");
      const stderr = Buffer.concat(stderrChunks).toString("utf-8");
      if (code !== 0) {
        finish(new Error(`DIAGNOSIS_AGENT_EXITED:${stderr.slice(0, 400)}`));
        return;
      }
      try {
        finish(undefined, parseBridgeOutput(stdout));
      } catch (err) {
        finish(err instanceof Error ? err : new Error("DIAGNOSIS_AGENT_OUTPUT_INVALID"));
      }
    });

    proc.stdin.end(
      JSON.stringify({
        ...input,
        userId: sanitizePathPart(`diagnosis_${input.teamId}_${input.sessionId}`),
      }),
    );
  });
}

export function buildDiagnosisStartPrompt(sourceFilePath: string) {
  return [
    `${sourceFilePath} 파일을 분석해줘.`,
    "기업 상황을 4~6문장으로 요약하고, 현재 확인된 강점과 핵심 공백을 짚어줘.",
    "마지막에는 대표자가 바로 답할 수 있는 다음 질문 1개만 한국어로 물어봐.",
  ].join(" ");
}

export function buildDiagnosisReplyPrompt(sourceFilePath: string, userReply: string) {
  return [
    `참고 파일 경로: ${sourceFilePath}`,
    "위 파일과 지금까지의 대화를 바탕으로 현황진단 대화를 이어가.",
    "사용자 답변을 반영해 현재 판단을 짧게 업데이트하고, 다음 질문은 1개만 제시해.",
    `사용자 답변: ${userReply}`,
  ].join("\n");
}

export function buildDiagnosisGeneratePrompt(sourceFilePath: string) {
  return [
    `참고 파일 경로: ${sourceFilePath}`,
    "지금까지의 대화와 위 진단시트를 바탕으로 '(컨설턴트용) 분석보고서'를 실제 엑셀에 반영해 저장해줘.",
    "저장이 끝나면 핵심 요약과 생성 완료 사실만 간단히 한국어로 알려줘.",
  ].join("\n");
}
