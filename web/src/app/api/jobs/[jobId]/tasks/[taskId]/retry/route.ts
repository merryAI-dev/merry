import { SendMessageCommand } from "@aws-sdk/client-sqs";
import { NextResponse } from "next/server";

import { getSqsClient } from "@/lib/aws/sqs";
import { getSqsQueueUrl } from "@/lib/aws/env";
import { getTask, retryTask } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ jobId: string; taskId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { jobId, taskId } = await params;

    // Verify task exists and is in failed state.
    const task = await getTask(ws.teamId, jobId, taskId);
    if (!task) {
      return NextResponse.json({ ok: false, error: "TASK_NOT_FOUND" }, { status: 404 });
    }
    if (task.status !== "failed") {
      return NextResponse.json({ ok: false, error: "TASK_NOT_FAILED" }, { status: 400 });
    }

    // Reset task to pending and adjust job counters.
    await retryTask(ws.teamId, jobId, taskId);

    // Re-enqueue SQS message for this task.
    const sqs = getSqsClient();
    const sqsUrl = getSqsQueueUrl();
    await sqs.send(
      new SendMessageCommand({
        QueueUrl: sqsUrl,
        MessageBody: JSON.stringify({
          version: 2,
          teamId: ws.teamId,
          jobId,
          taskId: task.taskId,
          fileId: task.fileId,
        }),
      }),
    );

    return NextResponse.json({ ok: true });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}
