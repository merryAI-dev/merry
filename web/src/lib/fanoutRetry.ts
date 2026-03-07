import { SendMessageBatchCommand } from "@aws-sdk/client-sqs";

import { getSqsClient } from "@/lib/aws/sqs";
import { getSqsQueueUrl } from "@/lib/aws/env";
import { getJob, getTask, listTasksByJob, retryTask, type TaskRecord } from "@/lib/jobStore";

export type RetryMode = "failed" | "all";

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function sendTasksWithRetry(teamId: string, jobId: string, tasks: TaskRecord[]) {
  if (tasks.length === 0) return;

  const sqs = getSqsClient();
  const sqsUrl = getSqsQueueUrl();
  let pending = tasks.map((task) => ({
    Id: task.taskId,
    MessageBody: JSON.stringify({
      version: 2,
      teamId,
      jobId,
      taskId: task.taskId,
      fileId: task.fileId,
    }),
  }));

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

export async function retryFanoutJob(teamId: string, jobId: string, mode: RetryMode = "failed") {
  const job = await getJob(teamId, jobId);
  if (!job) throw new Error("NOT_FOUND");
  if (!job.fanout) throw new Error("NOT_FANOUT_JOB");
  if (job.status !== "succeeded" && job.status !== "failed") {
    throw new Error("JOB_NOT_TERMINAL");
  }

  const tasks = await listTasksByJob(teamId, jobId);
  const tasksToRetry = mode === "all"
    ? tasks.filter((task) => task.status === "failed" || task.status === "succeeded")
    : tasks.filter((task) => task.status === "failed");

  if (tasksToRetry.length === 0) {
    return { retriedCount: 0 };
  }

  for (let i = 0; i < tasksToRetry.length; i += 10) {
    const batch = tasksToRetry.slice(i, i + 10);
    for (const task of batch) {
      await retryTask(teamId, jobId, task.taskId, task.status === "succeeded" ? "succeeded" : "failed");
    }
    await sendTasksWithRetry(teamId, jobId, batch);
  }

  return { retriedCount: tasksToRetry.length };
}

export async function retryFailedTask(teamId: string, jobId: string, taskId: string) {
  const task = await getTask(teamId, jobId, taskId);
  if (!task) throw new Error("TASK_NOT_FOUND");
  if (task.status !== "failed") throw new Error("TASK_NOT_FAILED");

  await retryTask(teamId, jobId, taskId);
  await sendTasksWithRetry(teamId, jobId, [task]);

  return { retriedCount: 1 };
}
