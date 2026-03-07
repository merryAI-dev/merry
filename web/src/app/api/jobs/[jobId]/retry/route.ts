import { SendMessageBatchCommand } from "@aws-sdk/client-sqs";
import { NextResponse } from "next/server";

import { getSqsClient } from "@/lib/aws/sqs";
import { getSqsQueueUrl } from "@/lib/aws/env";
import { getJob, listTasksByJob, retryTask } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

type SqsBatchEntry = {
  Id: string;
  MessageBody: string;
};

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

/**
 * POST /api/jobs/[jobId]/retry
 *
 * Retry all failed tasks for a fan-out job in bulk.
 * Accepts optional body: { mode: "failed" | "all" }
 * - "failed" (default): retry only failed tasks
 * - "all": retry all tasks (full re-run)
 */
export async function POST(
  req: Request,
  { params }: { params: Promise<{ jobId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { jobId } = await params;

    // Parse optional body.
    let mode: "failed" | "all" = "failed";
    try {
      const body = await req.json();
      if (body?.mode === "all") mode = "all";
    } catch {
      // No body or invalid JSON — use default.
    }

    // Verify job exists and is in a retryable state.
    const job = await getJob(ws.teamId, jobId);
    if (!job) {
      return NextResponse.json({ ok: false, error: "NOT_FOUND" }, { status: 404 });
    }
    if (!job.fanout) {
      return NextResponse.json({ ok: false, error: "NOT_FANOUT_JOB" }, { status: 400 });
    }
    if (job.status !== "succeeded" && job.status !== "failed") {
      return NextResponse.json({ ok: false, error: "JOB_NOT_TERMINAL" }, { status: 409 });
    }

    // Get all tasks for this job.
    const tasks = await listTasksByJob(ws.teamId, jobId);
    const tasksToRetry = mode === "all"
      ? tasks
      : tasks.filter((t) => t.status === "failed");

    if (tasksToRetry.length === 0) {
      return NextResponse.json({ ok: true, retriedCount: 0 });
    }

    // Reset each task to pending and decrement counters.
    for (const task of tasksToRetry) {
      if (task.status === "failed") {
        await retryTask(ws.teamId, jobId, task.taskId);
      } else if (mode === "all" && task.status === "succeeded") {
        await retryTask(ws.teamId, jobId, task.taskId, "succeeded");
      }
    }

    // Re-enqueue SQS messages in batches of 10.
    const sqs = getSqsClient();
    const sqsUrl = getSqsQueueUrl();

    for (let i = 0; i < tasksToRetry.length; i += 10) {
      const batch = tasksToRetry.slice(i, i + 10);
      await sendBatchWithRetry(
        sqs,
        sqsUrl,
        batch.map((task, idx) => ({
          Id: `${idx}`,
          MessageBody: JSON.stringify({
            version: 2,
            teamId: ws.teamId,
            jobId,
            taskId: task.taskId,
            fileId: task.fileId,
          }),
        })),
      );
    }

    return NextResponse.json({ ok: true, retriedCount: tasksToRetry.length });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}
