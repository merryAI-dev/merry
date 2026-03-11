import { SendMessageBatchCommand, SendMessageCommand } from "@aws-sdk/client-sqs";
import { NextResponse } from "next/server";
import { z } from "zod";

import { handleApiError } from "@/lib/apiError";
import { getSqsClient } from "@/lib/aws/sqs";
import { getSqsQueueUrl } from "@/lib/aws/env";
import { withCache } from "@/lib/cache";
import { paginate } from "@/lib/pagination";
import { sanitizeSearchQuery } from "@/lib/validation";
import {
  batchCreateTasks,
  countRunningFanoutJobs,
  createJob,
  getUploadFile,
  listRecentJobs,
  padTaskIndex,
  updateJobFanoutStatus,
  type JobType,
  type TaskRecord,
} from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

/* ── Fan-out registry: job types that fan out to per-file tasks ── */
const FANOUT_JOB_TYPES: ReadonlySet<string> = new Set(["condition_check", "document_extraction", "financial_extraction"]);

/* ── Max file count per fan-out job ── */
const FANOUT_MAX_FILES = 200;

/* ── Max concurrent fan-out jobs per team ── */
const MAX_CONCURRENT_FANOUT = Number(process.env.MERRY_MAX_CONCURRENT_FANOUT ?? 3);

type SqsBatchEntry = {
  Id: string;
  MessageBody: string;
};

const CreateSchema = z.object({
  jobType: z.enum(["exit_projection", "diagnosis_analysis", "pdf_evidence", "pdf_parse", "contract_review", "document_extraction", "condition_check", "financial_extraction"]),
  title: z.string().optional(),
  fileIds: z.array(z.string().min(6)).min(1).max(FANOUT_MAX_FILES),
  params: z.record(z.string(), z.unknown()).optional(),
});

export async function GET(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const url = new URL(req.url);

    const { jobs: allJobs } = await listRecentJobs(ws.teamId, 100);

    // Apply filters.
    let filtered = allJobs;

    const statusFilter = url.searchParams.get("status");
    if (statusFilter && statusFilter !== "all") {
      filtered = filtered.filter((j) => j.status === statusFilter);
    }

    const typeFilter = url.searchParams.get("type");
    if (typeFilter && typeFilter !== "all") {
      filtered = filtered.filter((j) => j.type === typeFilter);
    }

    const q = sanitizeSearchQuery(url.searchParams.get("q") || "").toLowerCase();
    if (q) {
      filtered = filtered.filter(
        (j) =>
          (j.title || "").toLowerCase().includes(q) ||
          j.jobId.toLowerCase().includes(q) ||
          (j.type || "").toLowerCase().includes(q),
      );
    }

    const { items, total, offset, hasMore } = paginate(filtered, url, 20);

    return withCache(
      NextResponse.json({ ok: true, jobs: items, total, offset, hasMore }),
      5, 10,
    );
  } catch (err) {
    return handleApiError(err, "GET /api/jobs");
  }
}

/** Split array into chunks of `size`. */
function chunkArray<T>(arr: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < arr.length; i += size) {
    chunks.push(arr.slice(i, i + size));
  }
  return chunks;
}

async function sleep(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function sendBatchWithRetry(
  sqs: ReturnType<typeof getSqsClient>,
  sqsUrl: string,
  entries: SqsBatchEntry[],
) {
  let pending = entries;
  for (let attempt = 0; pending.length > 0; attempt++) {
    const res = await sqs.send(
      new SendMessageBatchCommand({
        QueueUrl: sqsUrl,
        Entries: pending,
      }),
    );

    const failedIds = new Set((res.Failed ?? []).map((item) => item.Id).filter(Boolean));
    if (failedIds.size === 0) return;
    if (attempt >= 4) {
      throw new Error(`SQS_BATCH_SEND_FAILED:${Array.from(failedIds).join(",")}`);
    }
    pending = pending.filter((entry) => failedIds.has(entry.Id));
    await sleep(100 * 2 ** attempt);
  }
}

export async function POST(req: Request) {
  let jobId = "";
  let teamId = "";
  let jobCreated = false;
  try {
    const ws = await requireWorkspaceFromCookies();
    teamId = ws.teamId;
    const body = CreateSchema.parse(await req.json());

    // Enforce job-type specific arity to keep worker behavior predictable.
    if (FANOUT_JOB_TYPES.has(body.jobType)) {
      if (body.fileIds.length > FANOUT_MAX_FILES) {
        return NextResponse.json({ ok: false, error: "TOO_MANY_FILES" }, { status: 400 });
      }
    } else if (body.jobType === "contract_review") {
      if (body.fileIds.length > 2) {
        return NextResponse.json({ ok: false, error: "TOO_MANY_FILES" }, { status: 400 });
      }
    } else {
      if (body.fileIds.length !== 1) {
        return NextResponse.json({ ok: false, error: "INVALID_FILE_COUNT" }, { status: 400 });
      }
    }

    // Rate limit: max concurrent fan-out jobs per team.
    if (FANOUT_JOB_TYPES.has(body.jobType)) {
      const running = await countRunningFanoutJobs(ws.teamId);
      if (running >= MAX_CONCURRENT_FANOUT) {
        return NextResponse.json(
          { ok: false, error: "TOO_MANY_CONCURRENT_JOBS", running, limit: MAX_CONCURRENT_FANOUT },
          { status: 429 },
        );
      }
    }

    // Validate input file existence and upload completion.
    for (const fileId of body.fileIds) {
      const file = await getUploadFile(ws.teamId, fileId);
      if (!file) return NextResponse.json({ ok: false, error: "FILE_NOT_FOUND" }, { status: 404 });
      if (file.status !== "uploaded") {
        return NextResponse.json({ ok: false, error: "FILE_NOT_UPLOADED" }, { status: 400 });
      }
    }

    jobId = crypto.randomUUID().replaceAll("-", "").slice(0, 16);
    const correlationId = `${jobId}-${Date.now().toString(36)}`;
    const createdAt = new Date().toISOString();
    const type = body.jobType as JobType;
    const title = (body.title ?? "").trim() || ({
      exit_projection: "Exit 프로젝션",
      diagnosis_analysis: "기업진단 분석",
      pdf_evidence: "PDF 근거 추출",
      pdf_parse: "PDF 파싱",
      contract_review: "계약서 검토",
      document_extraction: "문서 일괄 추출",
      condition_check: "조건 검사",
      financial_extraction: "재무 데이터 추출",
    }[type]);

    const sqs = getSqsClient();
    const sqsUrl = getSqsQueueUrl();

    if (FANOUT_JOB_TYPES.has(body.jobType)) {
      /* ═══════════════════════════════════════════
         FAN-OUT PATH: 1 message per file
         ═══════════════════════════════════════════ */

      // 1. Create JOB record with fan-out metadata
      await createJob({
        jobId,
        teamId: ws.teamId,
        type,
        status: "queued",
        title,
        createdBy: ws.memberName,
        createdAt,
        inputFileIds: body.fileIds,
        params: body.params ?? {},
        fanout: true,
        totalTasks: body.fileIds.length,
        processedCount: 0,
        failedCount: 0,
        fanoutStatus: "splitting",
      });
      jobCreated = true;

      // 2. Create TASK records (BatchWriteItem, 25 items per call)
      const tasks: TaskRecord[] = body.fileIds.map((fileId, i) => ({
        taskId: padTaskIndex(i),
        jobId,
        teamId: ws.teamId,
        taskIndex: i,
        status: "pending" as const,
        fileId,
        createdAt,
      }));
      await batchCreateTasks(tasks);

      // 3. Send SQS messages (SendMessageBatch, 10 per call)
      const chunks = chunkArray(tasks, 10);
      for (const chunk of chunks) {
        await sendBatchWithRetry(
          sqs,
          sqsUrl,
          chunk.map((task) => ({
            Id: `${jobId}-${task.taskId}`,
            MessageBody: JSON.stringify({
              version: 2,
              teamId: ws.teamId,
              jobId,
              taskId: task.taskId,
              fileId: task.fileId,
              correlationId,
            }),
          })),
        );
      }

      // 4. Mark job as running
      await updateJobFanoutStatus(ws.teamId, jobId, "running", "running");

      const fanoutRes = NextResponse.json({ ok: true, jobId });
      fanoutRes.headers.set("x-correlation-id", correlationId);
      return fanoutRes;
    }

    /* ═══════════════════════════════════════════
       LEGACY PATH: 1 message for entire job
       ═══════════════════════════════════════════ */

    await createJob({
      jobId,
      teamId: ws.teamId,
      type,
      status: "queued",
      title,
      createdBy: ws.memberName,
      createdAt,
      inputFileIds: body.fileIds,
      params: body.params ?? {},
    });

    await sqs.send(
      new SendMessageCommand({
        QueueUrl: sqsUrl,
        MessageBody: JSON.stringify({ teamId: ws.teamId, jobId, correlationId }),
      }),
    );

    const legacyRes = NextResponse.json({ ok: true, jobId });
    legacyRes.headers.set("x-correlation-id", correlationId);
    return legacyRes;
  } catch (err) {
    if (jobCreated && teamId && jobId) {
      await updateJobFanoutStatus(teamId, jobId, "failed", "failed").catch(() => {});
    }
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    const code =
      err instanceof Error && err.message.startsWith("Missing env ")
        ? "MISSING_AWS_CONFIG"
        : "BAD_REQUEST";
    return NextResponse.json({ ok: false, error: code }, { status });
  }
}
