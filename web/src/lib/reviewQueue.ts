import { ConditionalCheckFailedException } from "@aws-sdk/client-dynamodb";
import { GetCommand, PutCommand, QueryCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";

import { getDdbDocClient } from "@/lib/aws/ddb";
import { getReviewDdbTableName } from "@/lib/aws/env";
import { listRecentJobs, listTasksByJob } from "@/lib/jobStore";
import {
  deriveReviewQueueCandidates,
  type ReviewQueueCandidate,
  type ReviewQueueReason,
  type ReviewQueueSeverity,
  type ReviewQueueStatus,
} from "@/lib/reviewQueueCandidates";

export type ReviewQueueRecord = ReviewQueueCandidate & {
  teamId: string;
  reviewedResult?: boolean;
  reviewComment?: string;
  assignedTo?: string;
  resolvedAt?: string;
};

export type ReviewQueueSummary = Record<string, number>;

type ReviewQueueFilters = {
  status?: ReviewQueueStatus | "open" | "all";
  reason?: ReviewQueueReason | "all";
  limit?: number;
};

function pkTeam(teamId: string) {
  return `TEAM#${teamId}`;
}

function pkTeamReviewQueue(teamId: string) {
  return `TEAM#${teamId}#REVIEW_QUEUE`;
}

function skReviewQueue(queueId: string) {
  return `REVIEW_QUEUE#${queueId}`;
}

function skCreated(createdAt: string, queueId: string) {
  return `CREATED#${createdAt}#REVIEW_QUEUE#${queueId}`;
}

function ttlEpoch(days = 90): number {
  return Math.floor(Date.now() / 1000) + days * 86400;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function asOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value ? value : undefined;
}

function asOptionalBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function isOpenStatus(status: ReviewQueueStatus): boolean {
  return status === "queued" || status === "in_review";
}

function isConditionalCheckFailed(error: unknown): boolean {
  return error instanceof ConditionalCheckFailedException
    || (error instanceof Error && error.name === "ConditionalCheckFailedException");
}

function deserializeReviewQueueRecord(teamId: string, row: Record<string, unknown>): ReviewQueueRecord {
  return {
    queueId: asString(row["queue_id"]),
    teamId,
    jobId: asString(row["job_id"]),
    taskId: asString(row["task_id"]),
    fileId: asString(row["file_id"]),
    filename: asString(row["filename"]),
    companyGroupKey: asString(row["company_group_key"]),
    companyGroupName: asString(row["company_group_name"]),
    jobTitle: asString(row["job_title"]),
    policyId: asString(row["policy_id"]),
    policyText: asString(row["policy_text"]),
    queueReason: asString(row["queue_reason"]) as ReviewQueueReason,
    severity: asString(row["severity"]) as ReviewQueueSeverity,
    status: asString(row["status"]) as ReviewQueueStatus,
    autoResult: asOptionalBoolean(row["auto_result"]),
    reviewedResult: asOptionalBoolean(row["reviewed_result"]),
    evidence: asString(row["evidence"]),
    parseWarning: asString(row["parse_warning"]),
    error: asString(row["error"]),
    aliasFrom: asString(row["alias_from"]),
    reviewComment: asOptionalString(row["review_comment"]),
    assignedTo: asOptionalString(row["assigned_to"]),
    createdAt: asString(row["created_at"]),
    updatedAt: asString(row["updated_at"]),
    resolvedAt: asOptionalString(row["resolved_at"]),
  };
}

async function putReviewQueueIndex(record: ReviewQueueRecord): Promise<void> {
  const ddb = getDdbDocClient();
  const TableName = getReviewDdbTableName();
  await ddb.send(new PutCommand({
    TableName,
    Item: {
      pk: pkTeamReviewQueue(record.teamId),
      sk: skCreated(record.createdAt, record.queueId),
      entity: "review_queue_index",
      queue_id: record.queueId,
      team_id: record.teamId,
      status: record.status,
      queue_reason: record.queueReason,
      severity: record.severity,
      filename: record.filename,
      policy_text: record.policyText,
      company_group_name: record.companyGroupName,
      assigned_to: record.assignedTo ?? "",
      updated_at: record.updatedAt,
      ttl: ttlEpoch(90),
    },
  }));
}

export async function ensureReviewQueueCandidates(teamId: string, candidates: ReviewQueueCandidate[]): Promise<void> {
  const ddb = getDdbDocClient();
  const TableName = getReviewDdbTableName();

  for (const candidate of candidates) {
    const record: ReviewQueueRecord = { ...candidate, teamId };
    try {
      await ddb.send(new PutCommand({
        TableName,
        Item: {
          pk: pkTeam(teamId),
          sk: skReviewQueue(candidate.queueId),
          entity: "review_queue",
          queue_id: candidate.queueId,
          team_id: teamId,
          job_id: candidate.jobId,
          task_id: candidate.taskId,
          file_id: candidate.fileId,
          filename: candidate.filename,
          company_group_key: candidate.companyGroupKey,
          company_group_name: candidate.companyGroupName,
          job_title: candidate.jobTitle,
          policy_id: candidate.policyId,
          policy_text: candidate.policyText,
          queue_reason: candidate.queueReason,
          severity: candidate.severity,
          status: candidate.status,
          auto_result: candidate.autoResult,
          reviewed_result: "",
          evidence: candidate.evidence,
          parse_warning: candidate.parseWarning,
          error: candidate.error,
          alias_from: candidate.aliasFrom,
          review_comment: "",
          assigned_to: "",
          created_at: candidate.createdAt,
          updated_at: candidate.updatedAt,
          resolved_at: "",
          ttl: ttlEpoch(90),
        },
        ConditionExpression: "attribute_not_exists(pk)",
      }));
      await putReviewQueueIndex(record);
    } catch (error) {
      if (isConditionalCheckFailed(error)) continue;
      throw error;
    }
  }
}

export async function syncReviewQueueFromRecentConditionJobs(teamId: string, jobLimit = 20): Promise<number> {
  const { jobs } = await listRecentJobs(teamId, jobLimit);
  const candidates: ReviewQueueCandidate[] = [];
  for (const job of jobs) {
    if (job.type !== "condition_check" || !job.fanout) continue;
    if (job.status === "queued") continue;
    const tasks = await listTasksByJob(teamId, job.jobId);
    candidates.push(...deriveReviewQueueCandidates(job, tasks));
  }
  await ensureReviewQueueCandidates(teamId, candidates);
  return candidates.length;
}

export async function getReviewQueueRecord(teamId: string, queueId: string): Promise<ReviewQueueRecord | null> {
  const ddb = getDdbDocClient();
  const TableName = getReviewDdbTableName();
  const res = await ddb.send(new GetCommand({
    TableName,
    Key: { pk: pkTeam(teamId), sk: skReviewQueue(queueId) },
  }));
  const row = res.Item as Record<string, unknown> | undefined;
  return row ? deserializeReviewQueueRecord(teamId, row) : null;
}

export async function listReviewQueueRecords(teamId: string, filters: ReviewQueueFilters = {}): Promise<ReviewQueueRecord[]> {
  const ddb = getDdbDocClient();
  const TableName = getReviewDdbTableName();
  const limit = Math.min(Math.max(filters.limit ?? 100, 1), 200);

  const res = await ddb.send(new QueryCommand({
    TableName,
    KeyConditionExpression: "pk = :pk",
    ExpressionAttributeValues: { ":pk": pkTeamReviewQueue(teamId) },
    ScanIndexForward: false,
    Limit: limit * 2,
  }));

  const ids = (res.Items ?? [])
    .map((item) => item as Record<string, unknown>)
    .filter((item) => {
      const status = asString(item["status"]) as ReviewQueueStatus;
      const reason = asString(item["queue_reason"]) as ReviewQueueReason;
      if (filters.status && filters.status !== "all") {
        if (filters.status === "open" && !isOpenStatus(status)) return false;
        if (filters.status !== "open" && status !== filters.status) return false;
      }
      if (filters.reason && filters.reason !== "all" && reason !== filters.reason) return false;
      return true;
    })
    .map((item) => asString(item["queue_id"]))
    .filter(Boolean)
    .slice(0, limit);

  const items = await Promise.all(ids.map((queueId) => getReviewQueueRecord(teamId, queueId)));
  return items.filter((item): item is ReviewQueueRecord => item !== null);
}

export async function getReviewQueueSummary(teamId: string): Promise<ReviewQueueSummary> {
  const ddb = getDdbDocClient();
  const TableName = getReviewDdbTableName();

  const summary: ReviewQueueSummary = { total: 0 };
  let exclusiveStartKey: Record<string, unknown> | undefined;

  do {
    const res = await ddb.send(new QueryCommand({
      TableName,
      KeyConditionExpression: "pk = :pk",
      ExpressionAttributeValues: { ":pk": pkTeamReviewQueue(teamId) },
      ScanIndexForward: false,
      ExclusiveStartKey: exclusiveStartKey,
    }));

    for (const item of res.Items ?? []) {
      const row = item as Record<string, unknown>;
      const status = asString(row["status"]) as ReviewQueueStatus;
      const reason = asString(row["queue_reason"]) as ReviewQueueReason;
      summary.total = (summary.total ?? 0) + 1;
      if (status) summary[status] = (summary[status] ?? 0) + 1;
      if (reason) summary[reason] = (summary[reason] ?? 0) + 1;
    }

    exclusiveStartKey = res.LastEvaluatedKey as Record<string, unknown> | undefined;
  } while (exclusiveStartKey);

  return summary;
}

async function updateReviewQueueIndex(record: ReviewQueueRecord): Promise<void> {
  const ddb = getDdbDocClient();
  const TableName = getReviewDdbTableName();
  await ddb.send(new UpdateCommand({
    TableName,
    Key: { pk: pkTeamReviewQueue(record.teamId), sk: skCreated(record.createdAt, record.queueId) },
    UpdateExpression: "SET #status = :status, assigned_to = :assigned_to, updated_at = :updated_at",
    ExpressionAttributeNames: { "#status": "status" },
    ExpressionAttributeValues: {
      ":status": record.status,
      ":assigned_to": record.assignedTo ?? "",
      ":updated_at": record.updatedAt,
    },
  }));
}

async function persistReviewQueueRecord(record: ReviewQueueRecord): Promise<void> {
  const ddb = getDdbDocClient();
  const TableName = getReviewDdbTableName();
  await ddb.send(new UpdateCommand({
    TableName,
    Key: { pk: pkTeam(record.teamId), sk: skReviewQueue(record.queueId) },
    UpdateExpression: [
      "SET #status = :status",
      "updated_at = :updated_at",
      "assigned_to = :assigned_to",
      "reviewed_result = :reviewed_result",
      "review_comment = :review_comment",
      "resolved_at = :resolved_at",
    ].join(", "),
    ExpressionAttributeNames: { "#status": "status" },
    ExpressionAttributeValues: {
      ":status": record.status,
      ":updated_at": record.updatedAt,
      ":assigned_to": record.assignedTo ?? "",
      ":reviewed_result": typeof record.reviewedResult === "boolean" ? record.reviewedResult : "",
      ":review_comment": record.reviewComment ?? "",
      ":resolved_at": record.resolvedAt ?? "",
    },
  }));
  await updateReviewQueueIndex(record);
}

export async function claimReviewQueueRecord(teamId: string, queueId: string, memberName: string): Promise<ReviewQueueRecord> {
  const record = await getReviewQueueRecord(teamId, queueId);
  if (!record) throw new Error("QUEUE_NOT_FOUND");
  if (record.status === "suppressed" || record.status.startsWith("resolved_")) {
    throw new Error("QUEUE_NOT_OPEN");
  }
  if (record.status === "in_review" && record.assignedTo && record.assignedTo !== memberName) {
    throw new Error("QUEUE_ALREADY_CLAIMED");
  }
  const updated: ReviewQueueRecord = {
    ...record,
    status: "in_review",
    assignedTo: memberName,
    updatedAt: new Date().toISOString(),
  };
  await persistReviewQueueRecord(updated);
  return updated;
}

export async function resolveReviewQueueRecord(
  teamId: string,
  queueId: string,
  args: {
    memberName: string;
    status: "resolved_correct" | "resolved_incorrect" | "resolved_ambiguous";
    reviewedResult?: boolean;
    reviewComment?: string;
  },
): Promise<ReviewQueueRecord> {
  const record = await getReviewQueueRecord(teamId, queueId);
  if (!record) throw new Error("QUEUE_NOT_FOUND");
  if (record.status === "suppressed") throw new Error("QUEUE_NOT_OPEN");

  const now = new Date().toISOString();
  const updated: ReviewQueueRecord = {
    ...record,
    status: args.status,
    reviewedResult: args.reviewedResult,
    reviewComment: args.reviewComment?.trim() || record.reviewComment,
    assignedTo: record.assignedTo || args.memberName,
    updatedAt: now,
    resolvedAt: now,
  };
  await persistReviewQueueRecord(updated);
  return updated;
}

export async function suppressReviewQueueRecord(
  teamId: string,
  queueId: string,
  args: { memberName: string; reviewComment?: string },
): Promise<ReviewQueueRecord> {
  const record = await getReviewQueueRecord(teamId, queueId);
  if (!record) throw new Error("QUEUE_NOT_FOUND");

  const now = new Date().toISOString();
  const updated: ReviewQueueRecord = {
    ...record,
    status: "suppressed",
    reviewComment: args.reviewComment?.trim() || record.reviewComment,
    assignedTo: record.assignedTo || args.memberName,
    updatedAt: now,
    resolvedAt: now,
  };
  await persistReviewQueueRecord(updated);
  return updated;
}
