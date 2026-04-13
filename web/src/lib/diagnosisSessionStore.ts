import { GetCommand, PutCommand, QueryCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";

import { getDdbDocClient } from "@/lib/aws/ddb";
import { getDiagnosisDdbTableName } from "@/lib/aws/env";
import { getJob, type UploadFileRecord } from "@/lib/jobStore";

import type {
  DiagnosisEventType,
  DiagnosisHistoryEvent,
  DiagnosisRunRecord,
  DiagnosisRunStatus,
  DiagnosisSessionDetail,
  DiagnosisSessionStatus,
  DiagnosisSessionSummary,
  DiagnosisUploadRecord,
} from "./diagnosisTypes";

function pkTeam(teamId: string) {
  return `TEAM#${teamId}`;
}

function skSession(sessionId: string) {
  return `DIAG#SESSION#${sessionId}`;
}

function pkTeamDiagnosisSessions(teamId: string) {
  return `TEAM#${teamId}#DIAGNOSIS#SESSIONS`;
}

function pkTeamDiagnosisHistory(teamId: string) {
  return `TEAM#${teamId}#DIAGNOSIS#HISTORY`;
}

function pkDiagnosisSession(teamId: string, sessionId: string) {
  return `TEAM#${teamId}#DIAGNOSIS#SESSION#${sessionId}`;
}

function skCreated(createdAt: string, entity: "SESSION" | "EVENT", id: string) {
  return `CREATED#${createdAt}#${entity}#${id}`;
}

function skUpload(uploadId: string) {
  return `UPLOAD#${uploadId}`;
}

function skRun(runId: string) {
  return `RUN#${runId}`;
}

function skEvent(createdAt: string, eventId: string) {
  return `EVENT#${createdAt}#${eventId}`;
}

function newId(prefix: string) {
  return `${prefix}_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function asOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value ? value : undefined;
}

function asNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function asSessionStatus(value: unknown): DiagnosisSessionStatus {
  if (value === "processing" || value === "ready" || value === "failed") return value;
  return "uploaded";
}

function asRunStatus(value: unknown): DiagnosisRunStatus {
  if (value === "running" || value === "succeeded" || value === "failed") return value;
  return "queued";
}

function deserializeSession(row: Record<string, unknown>): DiagnosisSessionSummary {
  return {
    sessionId: asString(row["session_id"]),
    title: asString(row["title"]) || "현황진단",
    status: asSessionStatus(row["status"]),
    createdBy: asString(row["created_by"]),
    createdAt: asString(row["created_at"]),
    updatedAt: asString(row["updated_at"]) || asString(row["created_at"]),
    originalFileName: asOptionalString(row["original_file_name"]),
    latestRunId: asOptionalString(row["latest_run_id"]) ?? null,
    legacyJobId: asOptionalString(row["legacy_job_id"]) ?? null,
    latestArtifactCount: asNumber(row["latest_artifact_count"]),
  };
}

function deserializeUpload(row: Record<string, unknown>, sessionId: string): DiagnosisUploadRecord {
  return {
    uploadId: asString(row["upload_id"]),
    sessionId,
    fileId: asString(row["file_id"]),
    originalName: asString(row["original_name"]),
    contentType: asString(row["content_type"]),
    sizeBytes: typeof row["size_bytes"] === "number" ? row["size_bytes"] : undefined,
    s3Bucket: asString(row["s3_bucket"]),
    s3Key: asString(row["s3_key"]),
    createdAt: asString(row["created_at"]),
    uploadedAt: asOptionalString(row["uploaded_at"]),
  };
}

function deserializeRun(row: Record<string, unknown>, sessionId: string): DiagnosisRunRecord {
  return {
    runId: asString(row["run_id"]),
    sessionId,
    legacyJobId: asString(row["legacy_job_id"]),
    status: asRunStatus(row["status"]),
    createdAt: asString(row["created_at"]),
    updatedAt: asString(row["updated_at"]) || asString(row["created_at"]),
    error: asOptionalString(row["error"]),
  };
}

function deserializeEvent(row: Record<string, unknown>): DiagnosisHistoryEvent {
  const typeRaw = asString(row["type"]);
  const type: DiagnosisEventType =
    typeRaw === "upload_recorded" ||
    typeRaw === "run_started" ||
    typeRaw === "run_succeeded" ||
    typeRaw === "run_failed"
      ? typeRaw
      : "session_created";
  return {
    eventId: asString(row["event_id"]),
    sessionId: asString(row["session_id"]),
    sessionTitle: asOptionalString(row["session_title"]),
    type,
    actor: asString(row["actor"]),
    createdAt: asString(row["created_at"]),
    description: asString(row["description"]),
    legacyJobId: asOptionalString(row["legacy_job_id"]),
  };
}

async function getDiagnosisSessionSummary(teamId: string, sessionId: string): Promise<DiagnosisSessionSummary | null> {
  const ddb = getDdbDocClient();
  const TableName = getDiagnosisDdbTableName();
  const res = await ddb.send(
    new GetCommand({
      TableName,
      Key: { pk: pkTeam(teamId), sk: skSession(sessionId) },
    }),
  );
  const row = (res.Item ?? null) as Record<string, unknown> | null;
  return row ? deserializeSession(row) : null;
}

async function updateSessionSummary(
  teamId: string,
  sessionId: string,
  updates: Partial<DiagnosisSessionSummary> & { updatedAt: string },
): Promise<DiagnosisSessionSummary> {
  const session = await getDiagnosisSessionSummary(teamId, sessionId);
  if (!session) throw new Error("NOT_FOUND");

  const TableName = getDiagnosisDdbTableName();
  const ddb = getDdbDocClient();
  const names: Record<string, string> = {};
  const values: Record<string, unknown> = {
    ":updated_at": updates.updatedAt,
  };
  const exprs = ["updated_at = :updated_at"];

  const maybeSet = (field: keyof DiagnosisSessionSummary, attr: string, value: unknown) => {
    if (value === undefined) return;
    names[`#${attr}`] = attr;
    values[`:${attr}`] = value;
    exprs.push(`#${attr} = :${attr}`);
  };

  maybeSet("title", "title", updates.title);
  maybeSet("status", "status", updates.status);
  maybeSet("originalFileName", "original_file_name", updates.originalFileName);
  maybeSet("latestRunId", "latest_run_id", updates.latestRunId ?? "");
  maybeSet("legacyJobId", "legacy_job_id", updates.legacyJobId ?? "");
  maybeSet("latestArtifactCount", "latest_artifact_count", updates.latestArtifactCount);

  const updateInput = {
    TableName,
    UpdateExpression: `SET ${exprs.join(", ")}`,
    ExpressionAttributeNames: names,
    ExpressionAttributeValues: values,
  };

  await ddb.send(
    new UpdateCommand({
      ...updateInput,
      Key: { pk: pkTeam(teamId), sk: skSession(sessionId) },
    }),
  );
  await ddb.send(
    new UpdateCommand({
      ...updateInput,
      Key: {
        pk: pkTeamDiagnosisSessions(teamId),
        sk: skCreated(session.createdAt, "SESSION", sessionId),
      },
    }),
  );

  return {
    ...session,
    ...updates,
    updatedAt: updates.updatedAt,
    latestRunId: updates.latestRunId === undefined ? session.latestRunId : updates.latestRunId ?? null,
    legacyJobId: updates.legacyJobId === undefined ? session.legacyJobId : updates.legacyJobId ?? null,
    latestArtifactCount: updates.latestArtifactCount ?? session.latestArtifactCount,
  };
}

async function appendHistoryEvent(args: {
  teamId: string;
  sessionId: string;
  sessionTitle: string;
  type: DiagnosisEventType;
  actor: string;
  description: string;
  createdAt?: string;
  legacyJobId?: string;
}): Promise<DiagnosisHistoryEvent> {
  const createdAt = args.createdAt ?? new Date().toISOString();
  const eventId = newId("diag_evt");
  const TableName = getDiagnosisDdbTableName();
  const ddb = getDdbDocClient();

  const item = {
    event_id: eventId,
    session_id: args.sessionId,
    session_title: args.sessionTitle,
    type: args.type,
    actor: args.actor,
    created_at: createdAt,
    description: args.description,
    legacy_job_id: args.legacyJobId ?? "",
  };

  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkDiagnosisSession(args.teamId, args.sessionId),
        sk: skEvent(createdAt, eventId),
        entity: "diagnosis_event",
        ...item,
      },
    }),
  );
  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkTeamDiagnosisHistory(args.teamId),
        sk: skCreated(createdAt, "EVENT", eventId),
        entity: "diagnosis_history",
        ...item,
      },
    }),
  );

  return deserializeEvent(item);
}

export async function createDiagnosisSession(args: {
  teamId: string;
  title?: string;
  createdBy: string;
  originalFileName?: string;
}): Promise<DiagnosisSessionSummary> {
  const createdAt = new Date().toISOString();
  const sessionId = newId("diag");
  const title = (args.title ?? args.originalFileName ?? "현황진단").trim();
  const session: DiagnosisSessionSummary = {
    sessionId,
    title,
    status: "uploaded",
    createdBy: args.createdBy,
    createdAt,
    updatedAt: createdAt,
    originalFileName: args.originalFileName?.trim() || undefined,
    latestRunId: null,
    legacyJobId: null,
    latestArtifactCount: 0,
  };

  const item = {
    session_id: session.sessionId,
    title: session.title,
    status: session.status,
    created_by: session.createdBy,
    created_at: session.createdAt,
    updated_at: session.updatedAt,
    original_file_name: session.originalFileName ?? "",
    latest_run_id: "",
    legacy_job_id: "",
    latest_artifact_count: 0,
  };

  const TableName = getDiagnosisDdbTableName();
  const ddb = getDdbDocClient();
  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkTeam(args.teamId),
        sk: skSession(sessionId),
        entity: "diagnosis_session",
        ...item,
      },
    }),
  );
  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkTeamDiagnosisSessions(args.teamId),
        sk: skCreated(createdAt, "SESSION", sessionId),
        entity: "diagnosis_session_index",
        ...item,
      },
    }),
  );
  await appendHistoryEvent({
    teamId: args.teamId,
    sessionId,
    sessionTitle: title,
    type: "session_created",
    actor: args.createdBy,
    description: "진단 세션이 생성되었습니다.",
    createdAt,
  });

  return session;
}

export async function recordDiagnosisUpload(args: {
  teamId: string;
  sessionId: string;
  file: UploadFileRecord;
  actor: string;
}): Promise<DiagnosisUploadRecord> {
  const session = await getDiagnosisSessionSummary(args.teamId, args.sessionId);
  if (!session) throw new Error("NOT_FOUND");

  const createdAt = new Date().toISOString();
  const uploadId = newId("diag_upl");
  const record: DiagnosisUploadRecord = {
    uploadId,
    sessionId: args.sessionId,
    fileId: args.file.fileId,
    originalName: args.file.originalName,
    contentType: args.file.contentType,
    sizeBytes: args.file.sizeBytes,
    s3Bucket: args.file.s3Bucket,
    s3Key: args.file.s3Key,
    createdAt,
    uploadedAt: args.file.uploadedAt,
  };

  const TableName = getDiagnosisDdbTableName();
  const ddb = getDdbDocClient();
  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkDiagnosisSession(args.teamId, args.sessionId),
        sk: skUpload(uploadId),
        entity: "diagnosis_upload",
        upload_id: uploadId,
        session_id: args.sessionId,
        file_id: args.file.fileId,
        original_name: args.file.originalName,
        content_type: args.file.contentType,
        size_bytes: args.file.sizeBytes,
        s3_bucket: args.file.s3Bucket,
        s3_key: args.file.s3Key,
        created_at: createdAt,
        uploaded_at: args.file.uploadedAt ?? "",
      },
    }),
  );

  await updateSessionSummary(args.teamId, args.sessionId, {
    updatedAt: createdAt,
    originalFileName: args.file.originalName,
  });
  await appendHistoryEvent({
    teamId: args.teamId,
    sessionId: args.sessionId,
    sessionTitle: session.title,
    type: "upload_recorded",
    actor: args.actor,
    description: `진단 파일 ${args.file.originalName} 업로드를 기록했습니다.`,
    createdAt,
  });

  return record;
}

export async function createDiagnosisRun(args: {
  teamId: string;
  sessionId: string;
  legacyJobId: string;
  status: DiagnosisRunStatus;
  actor: string;
}): Promise<DiagnosisRunRecord> {
  const session = await getDiagnosisSessionSummary(args.teamId, args.sessionId);
  if (!session) throw new Error("NOT_FOUND");

  const createdAt = new Date().toISOString();
  const runId = newId("diag_run");
  const run: DiagnosisRunRecord = {
    runId,
    sessionId: args.sessionId,
    legacyJobId: args.legacyJobId,
    status: args.status,
    createdAt,
    updatedAt: createdAt,
  };

  const TableName = getDiagnosisDdbTableName();
  const ddb = getDdbDocClient();
  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkDiagnosisSession(args.teamId, args.sessionId),
        sk: skRun(runId),
        entity: "diagnosis_run",
        run_id: runId,
        session_id: args.sessionId,
        legacy_job_id: args.legacyJobId,
        status: args.status,
        created_at: createdAt,
        updated_at: createdAt,
        error: "",
      },
    }),
  );

  await updateSessionSummary(args.teamId, args.sessionId, {
    updatedAt: createdAt,
    status: "processing",
    latestRunId: runId,
    legacyJobId: args.legacyJobId,
  });
  await appendHistoryEvent({
    teamId: args.teamId,
    sessionId: args.sessionId,
    sessionTitle: session.title,
    type: "run_started",
    actor: args.actor,
    description: "진단 실행을 시작했습니다.",
    createdAt,
    legacyJobId: args.legacyJobId,
  });

  return run;
}

async function updateDiagnosisRun(teamId: string, sessionId: string, runId: string, updates: {
  status?: DiagnosisRunStatus;
  updatedAt: string;
  error?: string;
}) {
  const TableName = getDiagnosisDdbTableName();
  const ddb = getDdbDocClient();
  const exprs = ["updated_at = :updated_at"];
  const names: Record<string, string> = {};
  const values: Record<string, unknown> = {
    ":updated_at": updates.updatedAt,
  };
  if (updates.status !== undefined) {
    names["#status"] = "status";
    values[":status"] = updates.status;
    exprs.push("#status = :status");
  }
  if (updates.error !== undefined) {
    names["#error"] = "error";
    values[":error"] = updates.error;
    exprs.push("#error = :error");
  }
  await ddb.send(
    new UpdateCommand({
      TableName,
      Key: { pk: pkDiagnosisSession(teamId, sessionId), sk: skRun(runId) },
      UpdateExpression: `SET ${exprs.join(", ")}`,
      ExpressionAttributeNames: names,
      ExpressionAttributeValues: values,
    }),
  );
}

export async function listDiagnosisSessions(teamId: string, limit = 20): Promise<DiagnosisSessionSummary[]> {
  const ddb = getDdbDocClient();
  const TableName = getDiagnosisDdbTableName();
  const res = await ddb.send(
    new QueryCommand({
      TableName,
      KeyConditionExpression: "pk = :pk",
      ExpressionAttributeValues: { ":pk": pkTeamDiagnosisSessions(teamId) },
      ScanIndexForward: false,
      Limit: Math.max(1, Math.min(limit, 100)),
    }),
  );
  return (res.Items ?? [])
    .map((item) => deserializeSession(item as Record<string, unknown>));
}

export async function getDiagnosisSessionDetail(teamId: string, sessionId: string): Promise<DiagnosisSessionDetail | null> {
  const session = await getDiagnosisSessionSummary(teamId, sessionId);
  if (!session) return null;

  const ddb = getDdbDocClient();
  const TableName = getDiagnosisDdbTableName();
  const res = await ddb.send(
    new QueryCommand({
      TableName,
      KeyConditionExpression: "pk = :pk",
      ExpressionAttributeValues: { ":pk": pkDiagnosisSession(teamId, sessionId) },
    }),
  );

  const uploads: DiagnosisUploadRecord[] = [];
  const runs: DiagnosisRunRecord[] = [];
  const events: DiagnosisHistoryEvent[] = [];

  for (const item of res.Items ?? []) {
    const row = item as Record<string, unknown>;
    if (row["entity"] === "diagnosis_upload") uploads.push(deserializeUpload(row, sessionId));
    if (row["entity"] === "diagnosis_run") runs.push(deserializeRun(row, sessionId));
    if (row["entity"] === "diagnosis_event") events.push(deserializeEvent(row));
  }

  uploads.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  runs.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  events.sort((a, b) => b.createdAt.localeCompare(a.createdAt));

  return {
    ...session,
    uploads,
    runs,
    events,
  };
}

export async function listDiagnosisHistory(teamId: string, limit = 30): Promise<DiagnosisHistoryEvent[]> {
  const ddb = getDdbDocClient();
  const TableName = getDiagnosisDdbTableName();
  const res = await ddb.send(
    new QueryCommand({
      TableName,
      KeyConditionExpression: "pk = :pk",
      ExpressionAttributeValues: { ":pk": pkTeamDiagnosisHistory(teamId) },
      ScanIndexForward: false,
      Limit: Math.max(1, Math.min(limit, 100)),
    }),
  );
  return (res.Items ?? []).map((item) => deserializeEvent(item as Record<string, unknown>));
}

export async function syncDiagnosisSessionFromLegacyJob(
  teamId: string,
  sessionId: string,
): Promise<DiagnosisSessionDetail | null> {
  const detail = await getDiagnosisSessionDetail(teamId, sessionId);
  if (!detail?.legacyJobId) return detail;

  const job = await getJob(teamId, detail.legacyJobId);
  if (!job) return detail;

  const latestRun = detail.latestRunId ? detail.runs.find((run) => run.runId === detail.latestRunId) : detail.runs[0];
  const updatedAt = job.updatedAt ?? new Date().toISOString();

  if ((job.status === "queued" || job.status === "running") && latestRun && latestRun.status !== job.status) {
    await updateDiagnosisRun(teamId, sessionId, latestRun.runId, {
      status: job.status,
      updatedAt,
      error: job.error ?? "",
    });
    return await getDiagnosisSessionDetail(teamId, sessionId);
  }

  if (detail.status !== "processing" || (job.status !== "succeeded" && job.status !== "failed")) {
    return detail;
  }

  const nextStatus: DiagnosisSessionStatus = job.status === "succeeded" ? "ready" : "failed";
  await updateSessionSummary(teamId, sessionId, {
    updatedAt,
    status: nextStatus,
    latestArtifactCount: (job.artifacts ?? []).length,
  });
  if (latestRun) {
    await updateDiagnosisRun(teamId, sessionId, latestRun.runId, {
      status: job.status,
      updatedAt,
      error: job.error ?? "",
    });
  }
  await appendHistoryEvent({
    teamId,
    sessionId,
    sessionTitle: detail.title,
    type: job.status === "succeeded" ? "run_succeeded" : "run_failed",
    actor: detail.createdBy,
    description: job.status === "succeeded" ? "진단 실행이 완료되었습니다." : "진단 실행이 실패했습니다.",
    createdAt: updatedAt,
    legacyJobId: detail.legacyJobId,
  });
  return await getDiagnosisSessionDetail(teamId, sessionId);
}
