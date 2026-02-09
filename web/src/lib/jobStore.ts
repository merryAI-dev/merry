import { GetCommand, PutCommand, QueryCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";

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

export type JobType = "exit_projection" | "diagnosis_analysis" | "pdf_evidence" | "pdf_parse" | "contract_review";

export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export type JobArtifact = {
  artifactId: string;
  label: string;
  contentType: string;
  s3Bucket: string;
  s3Key: string;
  sizeBytes?: number;
};

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

  const item = {
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
  };

  await ddb.send(new PutCommand({ TableName, Item: item }));
  await ddb.send(
    new PutCommand({
      TableName,
      Item: {
        pk: pkTeamJobs(record.teamId),
        sk: skCreated(record.createdAt, "JOB", record.jobId),
        entity: "job_index",
        job_id: record.jobId,
        team_id: record.teamId,
        type: record.type,
        title: record.title,
        created_at: record.createdAt,
        created_by: record.createdBy,
      },
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
    typeRaw === "exit_projection"
      ? typeRaw
      : "pdf_evidence";
  const statusRaw = row["status"];
  const status: JobStatus =
    statusRaw === "running" || statusRaw === "succeeded" || statusRaw === "failed" ? statusRaw : "queued";
  const artifacts = Array.isArray(row["artifacts"]) ? (row["artifacts"] as JobArtifact[]) : [];

  return {
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
}

export async function listRecentJobs(teamId: string, limit = 30): Promise<JobRecord[]> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  const res = await ddb.send(
    new QueryCommand({
      TableName,
      KeyConditionExpression: "pk = :pk",
      ExpressionAttributeValues: { ":pk": pkTeamJobs(teamId) },
      Limit: limit,
      ScanIndexForward: false,
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
  return jobs;
}
