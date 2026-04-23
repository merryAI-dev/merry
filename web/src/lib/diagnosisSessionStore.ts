import { GetCommand, PutCommand, QueryCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";

import { getDdbDocClient } from "@/lib/aws/ddb";
import { getDiagnosisDdbTableName } from "@/lib/aws/env";
import { getJob, type UploadFileRecord } from "@/lib/jobStore";

import type {
  DiagnosisAnalysisSummary,
  DiagnosisArtifactRecord,
  DiagnosisConversationState,
  DiagnosisConversationStatus,
  DiagnosisContextDocumentContent,
  DiagnosisContextDocumentSummary,
  DiagnosisDocumentRole,
  DiagnosisEventType,
  DiagnosisHistoryEvent,
  DiagnosisMessageRecord,
  DiagnosisMessageRole,
  DiagnosisNormalizedDocument,
  DiagnosisRunRecord,
  DiagnosisRunStatus,
  DiagnosisSessionDetail,
  DiagnosisSessionStatus,
  DiagnosisSessionSummary,
  DiagnosisSourceFile,
  DiagnosisUploadRecord,
} from "./diagnosisTypes";

export type DiagnosisSessionRuntimeState = {
  sourceFileLocalPath?: string;
  conversationState: DiagnosisConversationState | null;
};

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

function skMessage(createdAt: string, messageId: string) {
  return `MSG#${createdAt}#${messageId}`;
}

function skArtifact(createdAt: string, artifactId: string) {
  return `ARTIFACT#${createdAt}#${artifactId}`;
}

function skContextDocument(documentId: string) {
  return `CTXDOC#${documentId}`;
}

function skContextDocumentChunk(documentId: string, contentType: "markdown" | "plain", index: number) {
  return `CTXDOC#${documentId}#CHUNK#${contentType.toUpperCase()}#${String(index).padStart(4, "0")}`;
}

function skState() {
  return "STATE#CURRENT";
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

function asConversationStatus(value: unknown): DiagnosisConversationStatus {
  if (value === "thinking" || value === "generating_report" || value === "failed") return value;
  return "awaiting_user";
}

function asRunStatus(value: unknown): DiagnosisRunStatus {
  if (value === "running" || value === "succeeded" || value === "failed") return value;
  return "queued";
}

function asDocumentRole(value: unknown): DiagnosisDocumentRole {
  return value === "primary" ? "primary" : "context";
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
    typeRaw === "context_document_added" ||
    typeRaw === "conversation_started" ||
    typeRaw === "artifact_generated" ||
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

function deserializeMessage(row: Record<string, unknown>, sessionId: string): DiagnosisMessageRecord {
  const roleRaw = asString(row["role"]);
  const role: DiagnosisMessageRole =
    roleRaw === "user" || roleRaw === "assistant" || roleRaw === "system" ? roleRaw : "assistant";
  return {
    messageId: asString(row["message_id"]),
    sessionId,
    role,
    content: asString(row["content"]),
    createdAt: asString(row["created_at"]),
  };
}

function deserializeArtifact(row: Record<string, unknown>, sessionId: string): DiagnosisArtifactRecord {
  return {
    artifactId: asString(row["artifact_id"]),
    sessionId,
    label: asString(row["label"]),
    contentType: asString(row["content_type"]),
    createdAt: asString(row["created_at"]),
    s3Bucket: asString(row["s3_bucket"]),
    s3Key: asString(row["s3_key"]),
    sizeBytes: typeof row["size_bytes"] === "number" ? row["size_bytes"] : undefined,
  };
}

function deserializeContextDocument(
  row: Record<string, unknown>,
  sessionId: string,
): DiagnosisContextDocumentSummary {
  return {
    documentId: asString(row["document_id"]),
    sessionId,
    fileId: asString(row["file_id"]),
    originalName: asString(row["original_name"]),
    contentType: asString(row["content_type"]),
    role: asDocumentRole(row["role"]),
    sourceFormat: asString(row["source_format"]) as DiagnosisContextDocumentSummary["sourceFormat"],
    previewText: asString(row["preview_text"]),
    createdAt: asString(row["created_at"]),
    createdBy: asString(row["created_by"]),
    warningCount: asNumber(row["warning_count"]),
    markdownChunkCount: asNumber(row["markdown_chunk_count"]),
    plainTextChunkCount: asNumber(row["plain_text_chunk_count"]),
    metadata:
      row["metadata"] && typeof row["metadata"] === "object"
        ? (row["metadata"] as Record<string, unknown>)
        : {},
  };
}

function splitUtf8Text(value: string, maxBytes = 180_000): string[] {
  if (!value) return [""];
  const codePoints = Array.from(value);
  const chunks: string[] = [];
  let start = 0;
  while (start < codePoints.length) {
    let low = 1;
    let high = codePoints.length - start;
    let best = 1;
    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const bytes = Buffer.byteLength(codePoints.slice(start, start + mid).join(""), "utf8");
      if (bytes <= maxBytes) {
        best = mid;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }
    chunks.push(codePoints.slice(start, start + best).join(""));
    start += best;
  }
  return chunks;
}

function normalizePreviewText(value: string): string {
  return value.replace(/\s+/g, " ").trim().slice(0, 240);
}

function parseAnalysisSummary(value: unknown): DiagnosisAnalysisSummary | null {
  if (typeof value !== "string" || !value) return null;
  try {
    return JSON.parse(value) as DiagnosisAnalysisSummary;
  } catch {
    return null;
  }
}

function deserializeConversationState(row: Record<string, unknown>): DiagnosisSessionRuntimeState {
  const sourceFileId = asOptionalString(row["source_file_id"]);
  const sourceFileName = asOptionalString(row["source_file_name"]);
  const sourceFile: DiagnosisSourceFile | undefined =
    sourceFileId && sourceFileName
      ? {
          fileId: sourceFileId,
          originalName: sourceFileName,
        }
      : undefined;

  return {
    sourceFileLocalPath: asOptionalString(row["source_file_local_path"]),
    conversationState: {
      status: asConversationStatus(row["conversation_status"]),
      canGenerateReport: row["can_generate_report"] === true,
      sourceFile,
      analysisSummary: parseAnalysisSummary(row["analysis_summary"]),
    },
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

export async function markDiagnosisSessionStatus(args: {
  teamId: string;
  sessionId: string;
  status: DiagnosisSessionStatus;
  updatedAt?: string;
}) {
  return await updateSessionSummary(args.teamId, args.sessionId, {
    status: args.status,
    updatedAt: args.updatedAt ?? new Date().toISOString(),
  });
}

async function getConversationStateRow(
  teamId: string,
  sessionId: string,
): Promise<Record<string, unknown> | null> {
  const ddb = getDdbDocClient();
  const TableName = getDiagnosisDdbTableName();
  const res = await ddb.send(
    new GetCommand({
      TableName,
      Key: {
        pk: pkDiagnosisSession(teamId, sessionId),
        sk: skState(),
      },
    }),
  );
  return (res.Item ?? null) as Record<string, unknown> | null;
}

export async function getDiagnosisSessionRuntimeState(
  teamId: string,
  sessionId: string,
): Promise<DiagnosisSessionRuntimeState | null> {
  const row = await getConversationStateRow(teamId, sessionId);
  if (!row) return null;
  return deserializeConversationState(row);
}

export async function setDiagnosisConversationState(args: {
  teamId: string;
  sessionId: string;
  status: DiagnosisConversationStatus;
  canGenerateReport: boolean;
  sourceFile?: DiagnosisSourceFile;
  sourceFileLocalPath?: string;
  analysisSummary?: DiagnosisAnalysisSummary | null;
  updatedAt?: string;
}) {
  const existing = await getConversationStateRow(args.teamId, args.sessionId);
  const updatedAt = args.updatedAt ?? new Date().toISOString();
  const mergedSourceFileId = args.sourceFile?.fileId ?? asOptionalString(existing?.["source_file_id"]);
  const mergedSourceFileName = args.sourceFile?.originalName ?? asOptionalString(existing?.["source_file_name"]);
  const mergedSourceFilePath = args.sourceFileLocalPath ?? asOptionalString(existing?.["source_file_local_path"]);
  const mergedSummary =
    args.analysisSummary === undefined ? parseAnalysisSummary(existing?.["analysis_summary"]) : args.analysisSummary;

  const ddb = getDdbDocClient();
  const TableName = getDiagnosisDdbTableName();
  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkDiagnosisSession(args.teamId, args.sessionId),
        sk: skState(),
        entity: "diagnosis_state",
        conversation_status: args.status,
        can_generate_report: args.canGenerateReport,
        source_file_id: mergedSourceFileId ?? "",
        source_file_name: mergedSourceFileName ?? "",
        source_file_local_path: mergedSourceFilePath ?? "",
        analysis_summary: mergedSummary ? JSON.stringify(mergedSummary) : "",
        updated_at: updatedAt,
      },
    }),
  );
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

export async function saveDiagnosisConversationStart(args: {
  teamId: string;
  sessionId: string;
  actor: string;
  assistantText: string;
  sourceFile: DiagnosisSourceFile;
  sourceFileLocalPath: string;
  analysisSummary?: DiagnosisAnalysisSummary | null;
  createdAt?: string;
}): Promise<DiagnosisMessageRecord> {
  const session = await getDiagnosisSessionSummary(args.teamId, args.sessionId);
  if (!session) throw new Error("NOT_FOUND");

  const createdAt = args.createdAt ?? new Date().toISOString();
  const messageId = newId("diag_msg");
  const ddb = getDdbDocClient();
  const TableName = getDiagnosisDdbTableName();

  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkDiagnosisSession(args.teamId, args.sessionId),
        sk: skMessage(createdAt, messageId),
        entity: "diagnosis_message",
        message_id: messageId,
        session_id: args.sessionId,
        role: "assistant",
        content: args.assistantText,
        created_at: createdAt,
      },
    }),
  );

  await setDiagnosisConversationState({
    teamId: args.teamId,
    sessionId: args.sessionId,
    status: "awaiting_user",
    canGenerateReport: true,
    sourceFile: args.sourceFile,
    sourceFileLocalPath: args.sourceFileLocalPath,
    analysisSummary: args.analysisSummary ?? null,
    updatedAt: createdAt,
  });

  await appendHistoryEvent({
    teamId: args.teamId,
    sessionId: args.sessionId,
    sessionTitle: session.title,
    type: "conversation_started",
    actor: args.actor,
    description: "초기 진단 요약과 첫 질문을 생성했습니다.",
    createdAt,
  });

  return {
    messageId,
    sessionId: args.sessionId,
    role: "assistant",
    content: args.assistantText,
    createdAt,
  };
}

export async function appendDiagnosisConversationTurn(args: {
  teamId: string;
  sessionId: string;
  userContent: string;
  assistantText: string;
  analysisSummary?: DiagnosisAnalysisSummary | null;
}): Promise<DiagnosisMessageRecord> {
  const createdAt = new Date();
  const userCreatedAt = createdAt.toISOString();
  const assistantCreatedAt = new Date(createdAt.getTime() + 1).toISOString();
  const userMessageId = newId("diag_msg");
  const assistantMessageId = newId("diag_msg");
  const ddb = getDdbDocClient();
  const TableName = getDiagnosisDdbTableName();

  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkDiagnosisSession(args.teamId, args.sessionId),
        sk: skMessage(userCreatedAt, userMessageId),
        entity: "diagnosis_message",
        message_id: userMessageId,
        session_id: args.sessionId,
        role: "user",
        content: args.userContent,
        created_at: userCreatedAt,
      },
    }),
  );

  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkDiagnosisSession(args.teamId, args.sessionId),
        sk: skMessage(assistantCreatedAt, assistantMessageId),
        entity: "diagnosis_message",
        message_id: assistantMessageId,
        session_id: args.sessionId,
        role: "assistant",
        content: args.assistantText,
        created_at: assistantCreatedAt,
      },
    }),
  );

  await setDiagnosisConversationState({
    teamId: args.teamId,
    sessionId: args.sessionId,
    status: "awaiting_user",
    canGenerateReport: true,
    analysisSummary: args.analysisSummary,
    updatedAt: assistantCreatedAt,
  });

  return {
    messageId: assistantMessageId,
    sessionId: args.sessionId,
    role: "assistant",
    content: args.assistantText,
    createdAt: assistantCreatedAt,
  };
}

export async function appendDiagnosisAssistantMessage(args: {
  teamId: string;
  sessionId: string;
  assistantText: string;
  analysisSummary?: DiagnosisAnalysisSummary | null;
}): Promise<DiagnosisMessageRecord> {
  const createdAt = new Date().toISOString();
  const messageId = newId("diag_msg");
  const ddb = getDdbDocClient();
  const TableName = getDiagnosisDdbTableName();

  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkDiagnosisSession(args.teamId, args.sessionId),
        sk: skMessage(createdAt, messageId),
        entity: "diagnosis_message",
        message_id: messageId,
        session_id: args.sessionId,
        role: "assistant",
        content: args.assistantText,
        created_at: createdAt,
      },
    }),
  );

  await setDiagnosisConversationState({
    teamId: args.teamId,
    sessionId: args.sessionId,
    status: "awaiting_user",
    canGenerateReport: true,
    analysisSummary: args.analysisSummary,
    updatedAt: createdAt,
  });

  return {
    messageId,
    sessionId: args.sessionId,
    role: "assistant",
    content: args.assistantText,
    createdAt,
  };
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

export async function recordDiagnosisContextDocument(args: {
  teamId: string;
  sessionId: string;
  actor: string;
  file: Pick<
    UploadFileRecord,
    "fileId" | "originalName" | "contentType" | "s3Bucket" | "s3Key" | "createdAt"
  > & { sizeBytes?: number };
  normalized: DiagnosisNormalizedDocument;
}): Promise<DiagnosisContextDocumentSummary> {
  const session = await getDiagnosisSessionSummary(args.teamId, args.sessionId);
  if (!session) throw new Error("NOT_FOUND");

  const createdAt = new Date().toISOString();
  const documentId = newId("diag_doc");
  const markdownChunks = splitUtf8Text(args.normalized.markdown);
  const plainTextChunks = splitUtf8Text(args.normalized.plainText);
  const previewText = normalizePreviewText(args.normalized.plainText);

  const ddb = getDdbDocClient();
  const TableName = getDiagnosisDdbTableName();

  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkDiagnosisSession(args.teamId, args.sessionId),
        sk: skContextDocument(documentId),
        entity: "diagnosis_context_document",
        document_id: documentId,
        session_id: args.sessionId,
        file_id: args.file.fileId,
        original_name: args.file.originalName,
        content_type: args.file.contentType,
        s3_bucket: args.file.s3Bucket,
        s3_key: args.file.s3Key,
        size_bytes: args.file.sizeBytes,
        role: args.normalized.role,
        source_format: args.normalized.sourceFormat,
        preview_text: previewText,
        created_at: createdAt,
        created_by: args.actor,
        warning_count: args.normalized.warnings.length,
        warnings: args.normalized.warnings,
        metadata: args.normalized.metadata,
        markdown_chunk_count: markdownChunks.length,
        plain_text_chunk_count: plainTextChunks.length,
      },
    }),
  );

  for (const [index, chunk] of markdownChunks.entries()) {
    await ddb.send(
      new PutCommand({
        TableName,
        Item: {
          pk: pkDiagnosisSession(args.teamId, args.sessionId),
          sk: skContextDocumentChunk(documentId, "markdown", index),
          entity: "diagnosis_context_document_chunk",
          document_id: documentId,
          content_type: "markdown",
          chunk_index: index,
          content: chunk,
        },
      }),
    );
  }

  for (const [index, chunk] of plainTextChunks.entries()) {
    await ddb.send(
      new PutCommand({
        TableName,
        Item: {
          pk: pkDiagnosisSession(args.teamId, args.sessionId),
          sk: skContextDocumentChunk(documentId, "plain", index),
          entity: "diagnosis_context_document_chunk",
          document_id: documentId,
          content_type: "plain",
          chunk_index: index,
          content: chunk,
        },
      }),
    );
  }

  await updateSessionSummary(args.teamId, args.sessionId, {
    updatedAt: createdAt,
  });
  await appendHistoryEvent({
    teamId: args.teamId,
    sessionId: args.sessionId,
    sessionTitle: session.title,
    type: "context_document_added",
    actor: args.actor,
    description: `보조 문서 ${args.file.originalName}를 연결했습니다.`,
    createdAt,
  });

  return {
    documentId,
    sessionId: args.sessionId,
    fileId: args.file.fileId,
    originalName: args.file.originalName,
    contentType: args.file.contentType,
    role: args.normalized.role,
    sourceFormat: args.normalized.sourceFormat,
    previewText,
    createdAt,
    createdBy: args.actor,
    warningCount: args.normalized.warnings.length,
    markdownChunkCount: markdownChunks.length,
    plainTextChunkCount: plainTextChunks.length,
    metadata: args.normalized.metadata,
  };
}

export async function recordDiagnosisArtifact(args: {
  teamId: string;
  sessionId: string;
  actor: string;
  label: string;
  contentType: string;
  s3Bucket: string;
  s3Key: string;
  sizeBytes?: number;
  createdAt?: string;
}): Promise<DiagnosisArtifactRecord> {
  const session = await getDiagnosisSessionSummary(args.teamId, args.sessionId);
  if (!session) throw new Error("NOT_FOUND");

  const createdAt = args.createdAt ?? new Date().toISOString();
  const artifactId = newId("diag_art");
  const ddb = getDdbDocClient();
  const TableName = getDiagnosisDdbTableName();

  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkDiagnosisSession(args.teamId, args.sessionId),
        sk: skArtifact(createdAt, artifactId),
        entity: "diagnosis_artifact",
        artifact_id: artifactId,
        session_id: args.sessionId,
        label: args.label,
        content_type: args.contentType,
        created_at: createdAt,
        s3_bucket: args.s3Bucket,
        s3_key: args.s3Key,
        size_bytes: args.sizeBytes,
      },
    }),
  );

  await updateSessionSummary(args.teamId, args.sessionId, {
    updatedAt: createdAt,
    latestArtifactCount: session.latestArtifactCount + 1,
  });

  await appendHistoryEvent({
    teamId: args.teamId,
    sessionId: args.sessionId,
    sessionTitle: session.title,
    type: "artifact_generated",
    actor: args.actor,
    description: `${args.label} 결과물을 생성했습니다.`,
    createdAt,
  });

  return {
    artifactId,
    sessionId: args.sessionId,
    label: args.label,
    contentType: args.contentType,
    createdAt,
    s3Bucket: args.s3Bucket,
    s3Key: args.s3Key,
    sizeBytes: args.sizeBytes,
  };
}

export async function getDiagnosisArtifact(
  teamId: string,
  sessionId: string,
  artifactId: string,
): Promise<DiagnosisArtifactRecord | null> {
  const ddb = getDdbDocClient();
  const TableName = getDiagnosisDdbTableName();
  const res = await ddb.send(
    new QueryCommand({
      TableName,
      KeyConditionExpression: "pk = :pk AND begins_with(sk, :prefix)",
      ExpressionAttributeValues: {
        ":pk": pkDiagnosisSession(teamId, sessionId),
        ":prefix": "ARTIFACT#",
      },
    }),
  );

  for (const item of res.Items ?? []) {
    const row = item as Record<string, unknown>;
    if (asString(row["artifact_id"]) === artifactId) {
      return deserializeArtifact(row, sessionId);
    }
  }
  return null;
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
  const contextDocuments: DiagnosisContextDocumentSummary[] = [];
  const messages: DiagnosisMessageRecord[] = [];
  const artifacts: DiagnosisArtifactRecord[] = [];
  let conversationState: DiagnosisConversationState | null = null;

  for (const item of res.Items ?? []) {
    const row = item as Record<string, unknown>;
    if (row["entity"] === "diagnosis_upload") uploads.push(deserializeUpload(row, sessionId));
    if (row["entity"] === "diagnosis_run") runs.push(deserializeRun(row, sessionId));
    if (row["entity"] === "diagnosis_event") events.push(deserializeEvent(row));
    if (row["entity"] === "diagnosis_context_document") contextDocuments.push(deserializeContextDocument(row, sessionId));
    if (row["entity"] === "diagnosis_message") messages.push(deserializeMessage(row, sessionId));
    if (row["entity"] === "diagnosis_artifact") artifacts.push(deserializeArtifact(row, sessionId));
    if (row["entity"] === "diagnosis_state") {
      conversationState = deserializeConversationState(row).conversationState;
    }
  }

  uploads.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  runs.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  events.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  contextDocuments.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  messages.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  artifacts.sort((a, b) => b.createdAt.localeCompare(a.createdAt));

  return {
    ...session,
    uploads,
    runs,
    events,
    contextDocuments,
    messages,
    artifacts,
    conversationState,
  };
}

export async function getDiagnosisContextDocumentContent(
  teamId: string,
  sessionId: string,
  documentId: string,
): Promise<DiagnosisContextDocumentContent | null> {
  const ddb = getDdbDocClient();
  const TableName = getDiagnosisDdbTableName();
  const res = await ddb.send(
    new QueryCommand({
      TableName,
      KeyConditionExpression: "pk = :pk",
      ExpressionAttributeValues: { ":pk": pkDiagnosisSession(teamId, sessionId) },
    }),
  );

  const markdownChunks: Array<{ index: number; content: string }> = [];
  const plainTextChunks: Array<{ index: number; content: string }> = [];
  let found = false;

  for (const item of res.Items ?? []) {
    const row = item as Record<string, unknown>;
    if (row["entity"] === "diagnosis_context_document" && asString(row["document_id"]) === documentId) {
      found = true;
    }
    if (row["entity"] !== "diagnosis_context_document_chunk") continue;
    if (asString(row["document_id"]) !== documentId) continue;
    const contentType = asString(row["content_type"]);
    const entry = {
      index: asNumber(row["chunk_index"]),
      content: asString(row["content"]),
    };
    if (contentType === "markdown") markdownChunks.push(entry);
    if (contentType === "plain") plainTextChunks.push(entry);
  }

  if (!found) return null;

  markdownChunks.sort((a, b) => a.index - b.index);
  plainTextChunks.sort((a, b) => a.index - b.index);

  return {
    documentId,
    markdown: markdownChunks.map((chunk) => chunk.content).join(""),
    plainText: plainTextChunks.map((chunk) => chunk.content).join(""),
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
