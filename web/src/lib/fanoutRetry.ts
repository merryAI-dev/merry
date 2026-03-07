import { SendMessageBatchCommand } from "@aws-sdk/client-sqs";

import { getSqsClient } from "@/lib/aws/sqs";
import { getSqsQueueUrl } from "@/lib/aws/env";
import {
  getJob,
  getTask,
  listTasksByJob,
  restoreJobTerminalState,
  restoreRetriedTask,
  retryTask,
  type TaskRecord,
} from "@/lib/jobStore";

export type RetryMode = "failed" | "all";

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function sendTasksWithRetry(teamId: string, jobId: string, tasks: TaskRecord[]) {
  if (tasks.length === 0) return [];

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
    if (failedIds.size === 0) return [];
    if (attempt >= 4) return pending.map((entry) => entry.Id);
    pending = pending.filter((entry) => failedIds.has(entry.Id));
    await sleep(100 * 2 ** attempt);
  }

  return [];
}

async function restorePreparedTasks(
  teamId: string,
  jobId: string,
  tasks: TaskRecord[],
  restoreTerminalState?: { jobStatus: "failed" | "succeeded"; fanoutStatus: "failed" | "succeeded" },
) {
  const failedRestores: string[] = [];
  for (const task of tasks) {
    try {
      await restoreRetriedTask(teamId, jobId, task);
    } catch {
      failedRestores.push(task.taskId);
    }
  }

  if (restoreTerminalState && failedRestores.length === 0) {
    await restoreJobTerminalState(teamId, jobId, restoreTerminalState.jobStatus, restoreTerminalState.fanoutStatus);
  }

  if (failedRestores.length > 0) {
    throw new Error(`RETRY_COMPENSATION_FAILED:${failedRestores.join(",")}`);
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

  const originalJobStatus = job.status;
  const originalFanoutStatus = job.fanoutStatus === "succeeded" || job.fanoutStatus === "failed"
    ? job.fanoutStatus
    : (job.status === "succeeded" ? "succeeded" : "failed");
  let dispatchedCount = 0;

  for (let i = 0; i < tasksToRetry.length; i += 10) {
    const batch = tasksToRetry.slice(i, i + 10);
    const preparedTasks: TaskRecord[] = [];

    try {
      for (const task of batch) {
        await retryTask(teamId, jobId, task.taskId, task.status === "succeeded" ? "succeeded" : "failed");
        preparedTasks.push(task);
      }
    } catch (err) {
      if (preparedTasks.length > 0) {
        try {
          await restorePreparedTasks(
            teamId,
            jobId,
            preparedTasks,
            dispatchedCount === 0
              ? { jobStatus: originalJobStatus, fanoutStatus: originalFanoutStatus }
              : undefined,
          );
        } catch (restoreErr) {
          throw new Error(
            `${err instanceof Error ? err.message : "RETRY_PREPARE_FAILED"}:${restoreErr instanceof Error ? restoreErr.message : "RETRY_COMPENSATION_FAILED"}`,
          );
        }
      }
      throw err;
    }

    const unsentTaskIds = await sendTasksWithRetry(teamId, jobId, batch);
    if (unsentTaskIds.length > 0) {
      const unsentTaskSet = new Set(unsentTaskIds);
      const unsentTasks = batch.filter((task) => unsentTaskSet.has(task.taskId));
      const sentCount = batch.length - unsentTasks.length;
      dispatchedCount += sentCount;
      try {
        await restorePreparedTasks(
          teamId,
          jobId,
          unsentTasks,
          dispatchedCount === 0
            ? { jobStatus: originalJobStatus, fanoutStatus: originalFanoutStatus }
            : undefined,
        );
      } catch (restoreErr) {
        throw new Error(`SQS_BATCH_SEND_FAILED:${unsentTaskIds.join(",")}:${restoreErr instanceof Error ? restoreErr.message : "RETRY_COMPENSATION_FAILED"}`);
      }
      throw new Error(`SQS_BATCH_SEND_FAILED:${unsentTaskIds.join(",")}`);
    }

    dispatchedCount += batch.length;
  }

  return { retriedCount: tasksToRetry.length };
}

export async function retryFailedTask(teamId: string, jobId: string, taskId: string) {
  const task = await getTask(teamId, jobId, taskId);
  if (!task) throw new Error("TASK_NOT_FOUND");
  if (task.status !== "failed") throw new Error("TASK_NOT_FAILED");

  await retryTask(teamId, jobId, taskId);
  const unsentTaskIds = await sendTasksWithRetry(teamId, jobId, [task]);
  if (unsentTaskIds.length > 0) {
    try {
      await restorePreparedTasks(teamId, jobId, [task], { jobStatus: "failed", fanoutStatus: "failed" });
    } catch (restoreErr) {
      throw new Error(`SQS_BATCH_SEND_FAILED:${unsentTaskIds.join(",")}:${restoreErr instanceof Error ? restoreErr.message : "RETRY_COMPENSATION_FAILED"}`);
    }
    throw new Error(`SQS_BATCH_SEND_FAILED:${unsentTaskIds.join(",")}`);
  }

  return { retriedCount: 1 };
}
