import type { JobRecord, TaskRecord } from "@/lib/jobStore";

export type ReviewQueueReason =
  | "task_error"
  | "company_unrecognized"
  | "parse_warning"
  | "alias_correction"
  | "evidence_missing";

export type ReviewQueueSeverity = "high" | "medium" | "low";

export type ReviewQueueStatus =
  | "queued"
  | "in_review"
  | "resolved_correct"
  | "resolved_incorrect"
  | "resolved_ambiguous"
  | "suppressed";

export type ReviewQueueCandidate = {
  queueId: string;
  jobId: string;
  taskId: string;
  fileId: string;
  filename: string;
  companyGroupKey: string;
  companyGroupName: string;
  jobTitle: string;
  policyId: string;
  policyText: string;
  queueReason: ReviewQueueReason;
  severity: ReviewQueueSeverity;
  status: ReviewQueueStatus;
  autoResult?: boolean;
  evidence: string;
  parseWarning: string;
  error: string;
  aliasFrom: string;
  createdAt: string;
  updatedAt: string;
};

type ConditionResult = {
  condition?: string;
  result?: boolean;
  evidence?: string;
};

function normalizeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : value == null ? "" : String(value).trim();
}

function normalizePolicyId(policyText: string): string {
  const normalized = normalizeText(policyText).toLowerCase();
  if (!normalized) return "";
  return normalized.replace(/[^0-9a-z가-힣]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 60);
}

function makeQueueId(jobId: string, taskId: string, reason: ReviewQueueReason, policyId: string): string {
  const payload = `${jobId}:${taskId}:${reason}:${policyId}`;
  return Buffer.from(payload).toString("base64url").slice(0, 48);
}

function readConditions(result: Record<string, unknown> | undefined): ConditionResult[] {
  if (!Array.isArray(result?.conditions)) return [];
  return result.conditions.filter((item): item is ConditionResult => !!item && typeof item === "object");
}

function firstConditionWithMissingEvidence(conditions: ConditionResult[]): ConditionResult | undefined {
  return conditions.find((condition) => normalizeText(condition.condition) && normalizeText(condition.evidence).length < 8);
}

function baseCandidate(
  job: Pick<JobRecord, "jobId" | "title">,
  task: TaskRecord,
  result: Record<string, unknown> | undefined,
  reason: ReviewQueueReason,
  severity: ReviewQueueSeverity,
  policyText = "",
  autoResult?: boolean,
  evidence = "",
): ReviewQueueCandidate {
  const detectedFacts = result?.detected_facts && typeof result.detected_facts === "object"
    ? result.detected_facts as Record<string, unknown>
    : undefined;
  const filename = normalizeText(result?.filename) || task.fileId;
  const companyGroupName = normalizeText(result?.company_group_name) || normalizeText(detectedFacts?.company_group_name);
  const companyGroupKey = normalizeText(result?.company_group_key).toLowerCase() || normalizeText(detectedFacts?.company_group_key).toLowerCase();
  const parseWarning = normalizeText(result?.parse_warning);
  const aliasFrom = normalizeText(result?.company_group_alias_from);
  const taskError = normalizeText(task.error) || normalizeText(result?.error);
  const createdAt = normalizeText(task.endedAt) || normalizeText(task.updatedAt) || task.createdAt;
  const normalizedPolicyId = normalizePolicyId(policyText);

  return {
    queueId: makeQueueId(job.jobId, task.taskId, reason, normalizedPolicyId),
    jobId: job.jobId,
    taskId: task.taskId,
    fileId: task.fileId,
    filename,
    companyGroupKey,
    companyGroupName,
    jobTitle: job.title,
    policyId: normalizedPolicyId,
    policyText: normalizeText(policyText),
    queueReason: reason,
    severity,
    status: "queued",
    autoResult,
    evidence: normalizeText(evidence),
    parseWarning,
    error: taskError,
    aliasFrom,
    createdAt,
    updatedAt: createdAt,
  };
}

export function deriveReviewQueueCandidates(
  job: Pick<JobRecord, "jobId" | "title">,
  tasks: TaskRecord[],
): ReviewQueueCandidate[] {
  const dedup = new Map<string, ReviewQueueCandidate>();

  for (const task of tasks) {
    const result = task.result && typeof task.result === "object"
      ? task.result as Record<string, unknown>
      : undefined;
    const conditions = readConditions(result);

    if (task.status === "failed" || normalizeText(task.error) || normalizeText(result?.error)) {
      const candidate = baseCandidate(job, task, result, "task_error", "high");
      dedup.set(candidate.queueId, candidate);
    }

    if (!normalizeText(result?.company_group_key)) {
      const candidate = baseCandidate(job, task, result, "company_unrecognized", "high");
      dedup.set(candidate.queueId, candidate);
    }

    if (normalizeText(result?.parse_warning)) {
      const first = conditions[0];
      const candidate = baseCandidate(
        job,
        task,
        result,
        "parse_warning",
        "medium",
        normalizeText(first?.condition),
        typeof first?.result === "boolean" ? first.result : undefined,
        normalizeText(first?.evidence),
      );
      dedup.set(candidate.queueId, candidate);
    }

    if (normalizeText(result?.company_group_alias_from)) {
      const first = conditions[0];
      const candidate = baseCandidate(
        job,
        task,
        result,
        "alias_correction",
        "medium",
        normalizeText(first?.condition),
        typeof first?.result === "boolean" ? first.result : undefined,
        normalizeText(first?.evidence),
      );
      dedup.set(candidate.queueId, candidate);
    }

    const missingEvidence = firstConditionWithMissingEvidence(conditions);
    if (missingEvidence) {
      const candidate = baseCandidate(
        job,
        task,
        result,
        "evidence_missing",
        "low",
        normalizeText(missingEvidence.condition),
        typeof missingEvidence.result === "boolean" ? missingEvidence.result : undefined,
        normalizeText(missingEvidence.evidence),
      );
      dedup.set(candidate.queueId, candidate);
    }
  }

  return Array.from(dedup.values()).sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}
