import { BatchWriteCommand, GetCommand, PutCommand, QueryCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";

import { getDdbDocClient } from "@/lib/aws/ddb";
import { getDdbTableName } from "@/lib/aws/env";

export type FileStatus = "presigned" | "uploaded" | "deleted";

export type UploadFileRecord = {
  fileId: string;
  teamId: string;
  status: FileStatus;
  originalName: string;
  contentType: string;
  sizeBytes?: number;
  s3Bucket: string;
  s3Key: string;
  createdBy: string;
  createdAt: string;
  uploadedAt?: string;
  deletedAt?: string;
  etag?: string;
};

export type JobType =
  | "exit_projection"
  | "diagnosis_analysis"
  | "pdf_evidence"
  | "pdf_parse"
  | "contract_review"
  | "document_extraction"
  | "condition_check"
  | "financial_extraction";

export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export type JobArtifact = {
  artifactId: string;
  label: string;
  contentType: string;
  s3Bucket: string;
  s3Key: string;
  sizeBytes?: number;
};

export type FanoutStatus = "splitting" | "running" | "assembling" | "succeeded" | "failed";

export type JobRecord = {
  jobId: string;
  teamId: string;
  type: JobType;
  status: JobStatus;
  title: string;
  createdBy: string;
  createdAt: string;
  updatedAt?: string;
  inputFileIds: string[];
  params?: Record<string, unknown>;
  error?: string;
  artifacts?: JobArtifact[];
  metrics?: Record<string, unknown>;
  usage?: Record<string, unknown>;
  /* Fan-out fields (present when fanout === true) */
  fanout?: boolean;
  totalTasks?: number;
  processedCount?: number;
  failedCount?: number;
  fanoutStatus?: FanoutStatus;
};

export type TaskStatus = "pending" | "processing" | "succeeded" | "failed";

export type TaskRecord = {
  taskId: string;
  jobId: string;
  teamId: string;
  taskIndex: number;
  status: TaskStatus;
  fileId: string;
  createdAt: string;
  updatedAt?: string;
  startedAt?: string;
  endedAt?: string;
  result?: Record<string, unknown>;
  error?: string;
  workerId?: string;
};

function pkTeam(teamId: string) {
  return `TEAM#${teamId}`;
}

function pkTeamJobs(teamId: string) {
  return `TEAM#${teamId}#JOBS`;
}

function pkTeamFiles(teamId: string) {
  return `TEAM#${teamId}#FILES`;
}

function skFile(fileId: string) {
  return `FILE#${fileId}`;
}

function skJob(jobId: string) {
  return `JOB#${jobId}`;
}

function skCreated(createdAt: string, type: "FILE" | "JOB", id: string) {
  return `CREATED#${createdAt}#${type}#${id}`;
}

async function getJobCreatedAt(teamId: string, jobId: string): Promise<string | null> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  const res = await ddb.send(
    new GetCommand({
      TableName,
      Key: { pk: pkTeam(teamId), sk: skJob(jobId) },
      ProjectionExpression: "created_at",
    }),
  );
  const createdAt = res.Item?.created_at;
  return typeof createdAt === "string" && createdAt ? createdAt : null;
}

async function updateJobIndexState(
  teamId: string,
  jobId: string,
  updates: {
    status?: JobStatus;
    fanout?: boolean;
    fanoutStatus?: FanoutStatus;
  },
): Promise<void> {
  if (updates.status == null && updates.fanout == null && updates.fanoutStatus == null) {
    return;
  }

  const createdAt = await getJobCreatedAt(teamId, jobId);
  if (!createdAt) return;

  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  const exprs = ["updated_at = :updated_at"];
  const names: Record<string, string> = {};
  const values: Record<string, unknown> = {
    ":updated_at": new Date().toISOString(),
  };

  if (updates.status != null) {
    names["#status"] = "status";
    values[":status"] = updates.status;
    exprs.push("#status = :status");
  }
  if (updates.fanout != null) {
    names["#fanout"] = "fanout";
    values[":fanout"] = updates.fanout;
    exprs.push("#fanout = :fanout");
  }
  if (updates.fanoutStatus != null) {
    names["#fanout_status"] = "fanout_status";
    values[":fanout_status"] = updates.fanoutStatus;
    exprs.push("#fanout_status = :fanout_status");
  }

  await ddb.send(
    new UpdateCommand({
      TableName,
      Key: { pk: pkTeamJobs(teamId), sk: skCreated(createdAt, "JOB", jobId) },
      UpdateExpression: `SET ${exprs.join(", ")}`,
      ...(Object.keys(names).length > 0 ? { ExpressionAttributeNames: names } : {}),
      ExpressionAttributeValues: values,
      ConditionExpression: "attribute_exists(pk) AND attribute_exists(sk)",
    }),
  );
}

function skTask(jobId: string, taskId: string) {
  return `TASK#${jobId}#${taskId}`;
}

function pkTeamTasks(teamId: string, jobId: string) {
  return `TEAM#${teamId}#TASKS#${jobId}`;
}

export function padTaskIndex(index: number): string {
  return String(index).padStart(3, "0");
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function asBoolean(value: unknown): boolean {
  return value === true;
}

/** Unix epoch seconds for DynamoDB TTL. Default 30 days from now. */
function ttlEpoch(days = 30): number {
  return Math.floor(Date.now() / 1000) + days * 86400;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function asOptionalString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function asOptionalNumber(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}

export async function putUploadFile(record: UploadFileRecord) {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();

  const fileTtl = ttlEpoch(90);

  const item = {
    pk: pkTeam(record.teamId),
    sk: skFile(record.fileId),
    entity: "file",
    file_id: record.fileId,
    team_id: record.teamId,
    status: record.status,
    original_name: record.originalName,
    content_type: record.contentType,
    size_bytes: record.sizeBytes,
    s3_bucket: record.s3Bucket,
    s3_key: record.s3Key,
    created_by: record.createdBy,
    created_at: record.createdAt,
    uploaded_at: record.uploadedAt,
    deleted_at: record.deletedAt,
    etag: record.etag,
    ttl: fileTtl,
  };

  await ddb.send(new PutCommand({ TableName, Item: item }));

  // Listing index.
  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkTeamFiles(record.teamId),
        sk: skCreated(record.createdAt, "FILE", record.fileId),
        entity: "file_index",
        file_id: record.fileId,
        team_id: record.teamId,
        status: record.status,
        created_at: record.createdAt,
        created_by: record.createdBy,
        s3_key: record.s3Key,
        original_name: record.originalName,
        ttl: fileTtl,
      },
    }),
  );
}

export async function getUploadFile(teamId: string, fileId: string): Promise<UploadFileRecord | null> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  const res = await ddb.send(
    new GetCommand({
      TableName,
      Key: { pk: pkTeam(teamId), sk: skFile(fileId) },
    }),
  );
  const row = (res.Item ?? null) as Record<string, unknown> | null;
  if (!row) return null;
  const statusRaw = row["status"];
  const status: FileStatus = statusRaw === "uploaded" || statusRaw === "deleted" ? statusRaw : "presigned";
  return {
    fileId: asString(row["file_id"]),
    teamId: teamId,
    status,
    originalName: asString(row["original_name"]),
    contentType: asString(row["content_type"]),
    sizeBytes: asOptionalNumber(row["size_bytes"]),
    s3Bucket: asString(row["s3_bucket"]),
    s3Key: asString(row["s3_key"]),
    createdBy: asString(row["created_by"]),
    createdAt: asString(row["created_at"]),
    uploadedAt: asOptionalString(row["uploaded_at"]),
    deletedAt: asOptionalString(row["deleted_at"]),
    etag: asOptionalString(row["etag"]),
  };
}

export async function markUploadFileUploaded(args: {
  teamId: string;
  fileId: string;
  uploadedAt: string;
  etag?: string;
  sizeBytes?: number;
}) {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  await ddb.send(
    new UpdateCommand({
      TableName,
      Key: { pk: pkTeam(args.teamId), sk: skFile(args.fileId) },
      UpdateExpression:
        "SET #status = :uploaded, uploaded_at = :uploaded_at, etag = :etag, size_bytes = if_not_exists(size_bytes, :size_bytes)",
      ExpressionAttributeNames: { "#status": "status" },
      ExpressionAttributeValues: {
        ":uploaded": "uploaded",
        ":uploaded_at": args.uploadedAt,
        ":etag": args.etag ?? "",
        ":size_bytes": args.sizeBytes ?? 0,
      },
    }),
  );
}

export async function createJob(record: JobRecord) {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();

  const item: Record<string, unknown> = {
    pk: pkTeam(record.teamId),
    sk: skJob(record.jobId),
    entity: "job",
    job_id: record.jobId,
    team_id: record.teamId,
    type: record.type,
    status: record.status,
    title: record.title,
    created_by: record.createdBy,
    created_at: record.createdAt,
    updated_at: record.updatedAt ?? record.createdAt,
    input_file_ids: record.inputFileIds,
    params: record.params ?? {},
    error: record.error ?? "",
    artifacts: record.artifacts ?? [],
    metrics: record.metrics ?? {},
    usage: record.usage ?? {},
    ttl: ttlEpoch(90),
  };

  // Fan-out fields (only written when present)
  if (record.fanout) {
    item.fanout = true;
    item.total_tasks = record.totalTasks ?? 0;
    item.processed_count = record.processedCount ?? 0;
    item.failed_count = record.failedCount ?? 0;
    item.fanout_status = record.fanoutStatus ?? "splitting";
  }

  await ddb.send(
    new PutCommand({
      TableName,
      Item: item,
      ConditionExpression: "attribute_not_exists(pk)",
    }),
  );
  await ddb.send(
    new PutCommand({
      TableName,
      Item: (() => {
        const jobIndexItem: Record<string, unknown> = {
        pk: pkTeamJobs(record.teamId),
        sk: skCreated(record.createdAt, "JOB", record.jobId),
        entity: "job_index",
        job_id: record.jobId,
        team_id: record.teamId,
        type: record.type,
        status: record.status,
        fanout: Boolean(record.fanout),
        title: record.title,
        created_at: record.createdAt,
        updated_at: record.updatedAt ?? record.createdAt,
        created_by: record.createdBy,
        ttl: ttlEpoch(90),
        };
        if (record.fanout) {
          jobIndexItem.fanout_status = record.fanoutStatus ?? "splitting";
        }
        return jobIndexItem;
      })(),
    }),
  );
}

export async function getJob(teamId: string, jobId: string): Promise<JobRecord | null> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  const res = await ddb.send(
    new GetCommand({
      TableName,
      Key: { pk: pkTeam(teamId), sk: skJob(jobId) },
    }),
  );
  const row = (res.Item ?? null) as Record<string, unknown> | null;
  if (!row) return null;
  const typeRaw = row["type"];
  const type: JobType =
    typeRaw === "diagnosis_analysis" ||
    typeRaw === "pdf_evidence" ||
    typeRaw === "pdf_parse" ||
    typeRaw === "contract_review" ||
    typeRaw === "exit_projection" ||
    typeRaw === "document_extraction" ||
    typeRaw === "condition_check" ||
    typeRaw === "financial_extraction"
      ? typeRaw
      : "pdf_evidence";
  const statusRaw = row["status"];
  const status: JobStatus =
    statusRaw === "running" || statusRaw === "succeeded" || statusRaw === "failed" ? statusRaw : "queued";
  const artifacts = Array.isArray(row["artifacts"]) ? (row["artifacts"] as JobArtifact[]) : [];

  const result: JobRecord = {
    jobId: asString(row["job_id"]),
    teamId,
    type,
    status,
    title: asString(row["title"]) || `${type}`,
    createdBy: asString(row["created_by"]),
    createdAt: asString(row["created_at"]),
    updatedAt: asOptionalString(row["updated_at"]),
    inputFileIds: Array.isArray(row["input_file_ids"]) ? (row["input_file_ids"] as string[]) : [],
    params: (row["params"] && typeof row["params"] === "object" ? (row["params"] as Record<string, unknown>) : {}) as Record<
      string,
      unknown
    >,
    error: asOptionalString(row["error"]),
    artifacts,
    metrics: (row["metrics"] && typeof row["metrics"] === "object" ? (row["metrics"] as Record<string, unknown>) : {}) as Record<
      string,
      unknown
    >,
    usage: (row["usage"] && typeof row["usage"] === "object" ? (row["usage"] as Record<string, unknown>) : {}) as Record<
      string,
      unknown
    >,
  };

  // Fan-out fields
  if (asBoolean(row["fanout"])) {
    result.fanout = true;
    result.totalTasks = asOptionalNumber(row["total_tasks"]);
    result.processedCount = asOptionalNumber(row["processed_count"]);
    result.failedCount = asOptionalNumber(row["failed_count"]);
    const fs = asOptionalString(row["fanout_status"]);
    if (fs === "splitting" || fs === "running" || fs === "assembling" || fs === "succeeded" || fs === "failed") {
      result.fanoutStatus = fs;
    }
  }

  return result;
}

/* ──────────────────────────────────────────────────────────
   Fan-out: TASK CRUD & helpers
   ────────────────────────────────────────────────────────── */

/** Batch-create TASK records (entity + index). Uses BatchWriteItem (25 items per call). */
export async function batchCreateTasks(tasks: TaskRecord[]): Promise<void> {
  if (tasks.length === 0) return;
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();

  // Each task generates 2 items: entity + index
  const allItems: Record<string, unknown>[] = [];
  for (const t of tasks) {
    const taskTtl = ttlEpoch(90);
    allItems.push({
      pk: pkTeam(t.teamId),
      sk: skTask(t.jobId, t.taskId),
      entity: "task",
      team_id: t.teamId,
      job_id: t.jobId,
      task_id: t.taskId,
      task_index: t.taskIndex,
      status: t.status,
      file_id: t.fileId,
      created_at: t.createdAt,
      updated_at: t.createdAt,
      ttl: taskTtl,
    });
    allItems.push({
      pk: pkTeamTasks(t.teamId, t.jobId),
      sk: `TASK#${t.taskId}`,
      entity: "task_index",
      task_id: t.taskId,
      file_id: t.fileId,
      status: t.status,
      created_at: t.createdAt,
      ttl: taskTtl,
    });
  }

  // BatchWriteItem max 25 items per call
  for (let i = 0; i < allItems.length; i += 25) {
    let pending: Array<{ PutRequest: { Item: Record<string, unknown> } }> = allItems
      .slice(i, i + 25)
      .map((item) => ({ PutRequest: { Item: item } }));

    for (let attempt = 0; pending.length > 0; attempt++) {
      const res = await ddb.send(
        new BatchWriteCommand({
          RequestItems: {
            [TableName]: pending,
          },
        }),
      );
      pending = (res.UnprocessedItems?.[TableName] ?? []) as Array<{ PutRequest: { Item: Record<string, unknown> } }>;
      if (pending.length === 0) break;
      if (attempt >= 4) {
        throw new Error(`TASK_BATCH_WRITE_FAILED:${pending.length}`);
      }
      await sleep(50 * 2 ** attempt);
    }
  }
}

/** Get a single TASK record. */
export async function getTask(teamId: string, jobId: string, taskId: string): Promise<TaskRecord | null> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  const res = await ddb.send(
    new GetCommand({ TableName, Key: { pk: pkTeam(teamId), sk: skTask(jobId, taskId) } }),
  );
  const row = (res.Item ?? null) as Record<string, unknown> | null;
  if (!row) return null;
  return deserializeTask(row, teamId);
}

/** List all TASK records for a given job, ordered by task_index. */
export async function listTasksByJob(teamId: string, jobId: string): Promise<TaskRecord[]> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();

  const tasks: TaskRecord[] = [];
  let lastKey: Record<string, unknown> | undefined;

  do {
    const res = await ddb.send(
      new QueryCommand({
        TableName,
        KeyConditionExpression: "pk = :pk AND begins_with(sk, :prefix)",
        ExpressionAttributeValues: { ":pk": pkTeam(teamId), ":prefix": `TASK#${jobId}#` },
        ...(lastKey ? { ExclusiveStartKey: lastKey } : {}),
      }),
    );
    for (const item of res.Items ?? []) {
      const row = item as Record<string, unknown>;
      if (row["entity"] === "task") {
        tasks.push(deserializeTask(row, teamId));
      }
    }
    lastKey = res.LastEvaluatedKey as Record<string, unknown> | undefined;
  } while (lastKey);

  tasks.sort((a, b) => a.taskIndex - b.taskIndex);
  return tasks;
}

/** Update JOB fanout_status (and optionally status). */
export async function updateJobFanoutStatus(
  teamId: string,
  jobId: string,
  fanoutStatus: FanoutStatus,
  jobStatus?: JobStatus,
): Promise<void> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();

  let expr = "SET fanout_status = :fs, updated_at = :now";
  const names: Record<string, string> = {};
  const values: Record<string, unknown> = {
    ":fs": fanoutStatus,
    ":now": new Date().toISOString(),
  };

  if (jobStatus) {
    expr += ", #status = :st";
    names["#status"] = "status";
    values[":st"] = jobStatus;
  }

  await ddb.send(
    new UpdateCommand({
      TableName,
      Key: { pk: pkTeam(teamId), sk: skJob(jobId) },
      UpdateExpression: expr,
      ...(Object.keys(names).length > 0 ? { ExpressionAttributeNames: names } : {}),
      ExpressionAttributeValues: values,
    }),
  );

  await updateJobIndexState(teamId, jobId, {
    status: jobStatus,
    fanout: true,
    fanoutStatus,
  });
}

function deserializeTask(row: Record<string, unknown>, teamId: string): TaskRecord {
  const statusRaw = row["status"];
  const status: TaskStatus =
    statusRaw === "processing" || statusRaw === "succeeded" || statusRaw === "failed"
      ? statusRaw
      : "pending";
  const rawResult = row["result"];
  let result: Record<string, unknown> | undefined;
  if (rawResult && typeof rawResult === "object") {
    result = rawResult as Record<string, unknown>;
  } else if (typeof rawResult === "string" && rawResult) {
    try {
      const parsed = JSON.parse(rawResult) as unknown;
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        result = parsed as Record<string, unknown>;
      }
    } catch {
      result = undefined;
    }
  }
  return {
    taskId: asString(row["task_id"]),
    jobId: asString(row["job_id"]),
    teamId,
    taskIndex: typeof row["task_index"] === "number" ? row["task_index"] : 0,
    status,
    fileId: asString(row["file_id"]),
    createdAt: asString(row["created_at"]),
    updatedAt: asOptionalString(row["updated_at"]),
    startedAt: asOptionalString(row["started_at"]),
    endedAt: asOptionalString(row["ended_at"]),
    result,
    error: asOptionalString(row["error"]),
    workerId: asOptionalString(row["worker_id"]),
  };
}

/* ──────────────────────────────────────────────────────────
   Job listing
   ────────────────────────────────────────────────────────── */

export async function retryTask(
  teamId: string,
  jobId: string,
  taskId: string,
  fromStatus: "failed" | "succeeded" = "failed",
): Promise<void> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  const now = new Date().toISOString();

  // Reset task status to pending (only if currently failed).
  await ddb.send(
    new UpdateCommand({
      TableName,
      Key: { pk: pkTeam(teamId), sk: skTask(jobId, taskId) },
      UpdateExpression:
        "SET #status = :pending, #updated_at = :now, #error = :empty, #ended_at = :empty, #started_at = :empty, #worker_id = :empty",
      ConditionExpression: "#status = :from_status",
      ExpressionAttributeNames: {
        "#status": "status",
        "#updated_at": "updated_at",
        "#error": "error",
        "#ended_at": "ended_at",
        "#started_at": "started_at",
        "#worker_id": "worker_id",
      },
      ExpressionAttributeValues: {
        ":pending": "pending",
        ":from_status": fromStatus,
        ":now": now,
        ":empty": "",
      },
    }),
  );

  // Also update the task index record.
  await ddb.send(
    new UpdateCommand({
      TableName,
      Key: { pk: pkTeamTasks(teamId, jobId), sk: `TASK#${taskId}` },
      UpdateExpression: "SET #status = :pending, #updated_at = :now",
      ExpressionAttributeNames: { "#status": "status", "#updated_at": "updated_at" },
      ExpressionAttributeValues: { ":pending": "pending", ":now": now },
    }),
  );

  // Decrement job counters (processed_count and failed_count).
  const updateExpression =
    fromStatus === "failed"
      ? "SET #pc = #pc - :one, #fc = #fc - :one, #updated_at = :now, fanout_status = :running, #status = :running"
      : "SET #pc = #pc - :one, #updated_at = :now, fanout_status = :running, #status = :running";
  await ddb.send(
    new UpdateCommand({
      TableName,
      Key: { pk: pkTeam(teamId), sk: skJob(jobId) },
      UpdateExpression: updateExpression,
      ExpressionAttributeNames: {
        "#pc": "processed_count",
        "#updated_at": "updated_at",
        "#status": "status",
        ...(fromStatus === "failed" ? { "#fc": "failed_count" } : {}),
      },
      ExpressionAttributeValues: {
        ":one": 1,
        ":now": now,
        ":running": "running",
      },
    }),
  );
}

export async function restoreRetriedTask(
  teamId: string,
  jobId: string,
  task: TaskRecord,
): Promise<void> {
  if (task.status !== "failed" && task.status !== "succeeded") {
    throw new Error(`INVALID_RESTORE_STATUS:${task.status}`);
  }

  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  const now = new Date().toISOString();
  const terminalStatus = task.status;

  await ddb.send(
    new UpdateCommand({
      TableName,
      Key: { pk: pkTeam(teamId), sk: skTask(jobId, task.taskId) },
      UpdateExpression:
        "SET #status = :terminal, #updated_at = :now, #error = :error, #started_at = :started_at, #ended_at = :ended_at, #worker_id = :worker_id",
      ConditionExpression: "#status = :pending",
      ExpressionAttributeNames: {
        "#status": "status",
        "#updated_at": "updated_at",
        "#error": "error",
        "#started_at": "started_at",
        "#ended_at": "ended_at",
        "#worker_id": "worker_id",
      },
      ExpressionAttributeValues: {
        ":terminal": terminalStatus,
        ":pending": "pending",
        ":now": now,
        ":error": task.error ?? "",
        ":started_at": task.startedAt ?? "",
        ":ended_at": task.endedAt ?? "",
        ":worker_id": task.workerId ?? "",
      },
    }),
  );

  await ddb.send(
    new UpdateCommand({
      TableName,
      Key: { pk: pkTeamTasks(teamId, jobId), sk: `TASK#${task.taskId}` },
      UpdateExpression: "SET #status = :terminal, #updated_at = :now",
      ExpressionAttributeNames: { "#status": "status", "#updated_at": "updated_at" },
      ExpressionAttributeValues: { ":terminal": terminalStatus, ":now": now },
    }),
  );

  const updateExpression =
    terminalStatus === "failed"
      ? "SET #pc = #pc + :one, #fc = #fc + :one, #updated_at = :now"
      : "SET #pc = #pc + :one, #updated_at = :now";
  await ddb.send(
    new UpdateCommand({
      TableName,
      Key: { pk: pkTeam(teamId), sk: skJob(jobId) },
      UpdateExpression: updateExpression,
      ExpressionAttributeNames: {
        "#pc": "processed_count",
        "#updated_at": "updated_at",
        ...(terminalStatus === "failed" ? { "#fc": "failed_count" } : {}),
      },
      ExpressionAttributeValues: {
        ":one": 1,
        ":now": now,
      },
    }),
  );
}

export async function restoreJobTerminalState(
  teamId: string,
  jobId: string,
  jobStatus: "failed" | "succeeded",
  fanoutStatus: "failed" | "succeeded",
): Promise<void> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  await ddb.send(
    new UpdateCommand({
      TableName,
      Key: { pk: pkTeam(teamId), sk: skJob(jobId) },
      UpdateExpression: "SET #status = :status, #fanout_status = :fanout_status, #updated_at = :now",
      ExpressionAttributeNames: {
        "#status": "status",
        "#fanout_status": "fanout_status",
        "#updated_at": "updated_at",
      },
      ExpressionAttributeValues: {
        ":status": jobStatus,
        ":fanout_status": fanoutStatus,
        ":now": new Date().toISOString(),
      },
    }),
  );
}

export async function cancelJob(
  teamId: string,
  jobId: string,
  reason = "사용자에 의해 취소됨",
): Promise<boolean> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  const now = new Date().toISOString();

  // Conditional write: only cancel if fanout_status is still "running".
  try {
    await ddb.send(
      new UpdateCommand({
        TableName,
        Key: { pk: pkTeam(teamId), sk: skJob(jobId) },
        UpdateExpression:
          "SET #status = :failed, #fs = :failed, #error = :reason, #updated_at = :now",
        ConditionExpression: "#fs = :running",
        ExpressionAttributeNames: {
          "#status": "status",
          "#fs": "fanout_status",
          "#error": "error",
          "#updated_at": "updated_at",
        },
        ExpressionAttributeValues: {
          ":failed": "failed",
          ":running": "running",
          ":reason": reason,
          ":now": now,
        },
      }),
    );
    await updateJobIndexState(teamId, jobId, {
      status: "failed",
      fanout: true,
      fanoutStatus: "failed",
    });
    return true;
  } catch {
    // ConditionalCheckFailedException or other — job not in running state.
    return false;
  }
}

/**
 * Count currently running fan-out jobs for a team.
 * Used for rate limiting — query the job index directly to avoid N+1 JOB reads.
 */
export async function countRunningFanoutJobs(teamId: string): Promise<number> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  let running = 0;
  let lastKey: Record<string, unknown> | undefined;

  do {
    const res = await ddb.send(
      new QueryCommand({
        TableName,
        KeyConditionExpression: "pk = :pk",
        FilterExpression: "#fanout = :fanout AND (#status = :queued OR #status = :running)",
        ExpressionAttributeNames: {
          "#fanout": "fanout",
          "#status": "status",
        },
        ExpressionAttributeValues: {
          ":pk": pkTeamJobs(teamId),
          ":fanout": true,
          ":queued": "queued",
          ":running": "running",
        },
        Select: "COUNT",
        ...(lastKey ? { ExclusiveStartKey: lastKey } : {}),
      }),
    );
    running += res.Count ?? 0;
    lastKey = res.LastEvaluatedKey as Record<string, unknown> | undefined;
  } while (lastKey);

  return running;
}

export type JobListResult = {
  jobs: JobRecord[];
  nextCursor: string | null;
};

/** Encode DDB LastEvaluatedKey as an opaque base64 cursor. */
function encodeCursor(key: Record<string, unknown>): string {
  return Buffer.from(JSON.stringify(key)).toString("base64url");
}

/** Decode an opaque cursor back to DDB ExclusiveStartKey. */
function decodeCursor(cursor: string): Record<string, unknown> | undefined {
  try {
    return JSON.parse(Buffer.from(cursor, "base64url").toString("utf-8"));
  } catch {
    return undefined;
  }
}

export async function listRecentJobs(
  teamId: string,
  limit = 30,
  cursor?: string,
): Promise<JobListResult> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();

  const exclusiveStartKey = cursor ? decodeCursor(cursor) : undefined;

  const res = await ddb.send(
    new QueryCommand({
      TableName,
      KeyConditionExpression: "pk = :pk",
      ExpressionAttributeValues: { ":pk": pkTeamJobs(teamId) },
      Limit: limit,
      ScanIndexForward: false,
      ...(exclusiveStartKey ? { ExclusiveStartKey: exclusiveStartKey } : {}),
    }),
  );
  const ids = (res.Items ?? [])
    .map((it) => (it ?? {}) as Record<string, unknown>)
    .map((it) => (typeof it["job_id"] === "string" ? it["job_id"] : ""))
    .filter(Boolean);

  const jobs: JobRecord[] = [];
  for (const id of ids) {
    const job = await getJob(teamId, id);
    if (job) jobs.push(job);
  }
  jobs.sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""));

  const nextCursor = res.LastEvaluatedKey
    ? encodeCursor(res.LastEvaluatedKey as Record<string, unknown>)
    : null;

  return { jobs, nextCursor };
}
