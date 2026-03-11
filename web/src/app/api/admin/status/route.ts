import { ListObjectsV2Command } from "@aws-sdk/client-s3";
import { GetQueueAttributesCommand } from "@aws-sdk/client-sqs";
import { QueryCommand, ScanCommand } from "@aws-sdk/lib-dynamodb";
import { NextResponse } from "next/server";

import { getDdbDocClient } from "@/lib/aws/ddb";
import { getDdbTableName, getS3BucketName, getSqsDlqUrl, getSqsQueueUrl } from "@/lib/aws/env";
import { getS3Client } from "@/lib/aws/s3";
import { getSqsClient } from "@/lib/aws/sqs";
import { withCache } from "@/lib/cache";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

/** Comma-separated list of team IDs allowed to access this endpoint. */
const ADMIN_TEAM_IDS = new Set(
  (process.env.MERRY_ADMIN_TEAM_IDS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
);

export async function GET() {
  try {
    const ws = await requireWorkspaceFromCookies();
    if (ADMIN_TEAM_IDS.size > 0 && !ADMIN_TEAM_IDS.has(ws.teamId)) {
      return NextResponse.json({ ok: false, error: "FORBIDDEN" }, { status: 403 });
    }

    const ddb = getDdbDocClient();
    const TableName = getDdbTableName();

    // 1. SQS queue depth.
    let sqsStats: Record<string, number> = {};
    try {
      const sqsUrl = getSqsQueueUrl();
      const sqs = getSqsClient();
      const attrs = await sqs.send(
        new GetQueueAttributesCommand({
          QueueUrl: sqsUrl,
          AttributeNames: [
            "ApproximateNumberOfMessages",
            "ApproximateNumberOfMessagesNotVisible",
            "ApproximateNumberOfMessagesDelayed",
          ],
        }),
      );
      const a = attrs.Attributes ?? {};
      sqsStats = {
        messagesVisible: Number(a.ApproximateNumberOfMessages ?? 0),
        messagesInFlight: Number(a.ApproximateNumberOfMessagesNotVisible ?? 0),
        messagesDelayed: Number(a.ApproximateNumberOfMessagesDelayed ?? 0),
      };
    } catch {
      // SQS might not be configured in dev.
    }

    // 1b. SQS DLQ depth.
    let dlqStats: Record<string, number> = {};
    try {
      const dlqUrl = getSqsDlqUrl();
      const sqs = getSqsClient();
      const dlqAttrs = await sqs.send(
        new GetQueueAttributesCommand({
          QueueUrl: dlqUrl,
          AttributeNames: [
            "ApproximateNumberOfMessages",
            "ApproximateNumberOfMessagesNotVisible",
          ],
        }),
      );
      const d = dlqAttrs.Attributes ?? {};
      dlqStats = {
        messagesVisible: Number(d.ApproximateNumberOfMessages ?? 0),
        messagesInFlight: Number(d.ApproximateNumberOfMessagesNotVisible ?? 0),
      };
    } catch {
      // DLQ might not be configured in dev.
    }

    // 2. Running jobs across all teams (scan with filter — expensive but admin-only).
    const runningJobs: Array<Record<string, unknown>> = [];
    let lastKey: Record<string, unknown> | undefined;
    let scanCount = 0;
    const MAX_SCAN_PAGES = 3; // Limit scan cost.

    do {
      const res = await ddb.send(
        new ScanCommand({
          TableName,
          FilterExpression: "#entity = :job AND #status IN (:queued, :running)",
          ExpressionAttributeNames: {
            "#entity": "entity",
            "#status": "status",
            "#type": "type",
          },
          ExpressionAttributeValues: { ":job": "job", ":queued": "queued", ":running": "running" },
          ProjectionExpression: "pk, job_id, #status, title, #type, created_at, fanout, total_tasks, processed_count, failed_count, fanout_status",
          ...(lastKey ? { ExclusiveStartKey: lastKey } : {}),
        }),
      );
      for (const item of res.Items ?? []) {
        const teamId = typeof item.pk === "string" ? item.pk.replace("TEAM#", "") : "";
        runningJobs.push({
          teamId,
          jobId: item.job_id,
          status: item.status,
          title: item.title,
          type: item.type,
          createdAt: item.created_at,
          fanout: item.fanout ?? false,
          totalTasks: item.total_tasks ?? 0,
          processedCount: item.processed_count ?? 0,
          failedCount: item.failed_count ?? 0,
          fanoutStatus: item.fanout_status ?? null,
        });
      }
      lastKey = res.LastEvaluatedKey as Record<string, unknown> | undefined;
      scanCount++;
    } while (lastKey && scanCount < MAX_SCAN_PAGES);

    // 3. Recent failure rate (last 30 jobs for requesting team).
    const recentRes = await ddb.send(
      new QueryCommand({
        TableName,
        KeyConditionExpression: "pk = :pk",
        ExpressionAttributeValues: { ":pk": `TEAM#${ws.teamId}#JOBS` },
        Limit: 30,
        ScanIndexForward: false,
      }),
    );
    const recentIds = (recentRes.Items ?? [])
      .map((it) => (typeof it.job_id === "string" ? it.job_id : ""))
      .filter(Boolean);

    let totalRecent = 0;
    let failedRecent = 0;
    let totalTokens = 0;
    for (const id of recentIds) {
      const jobRes = await ddb.send(
        new QueryCommand({
          TableName,
          KeyConditionExpression: "pk = :pk AND sk = :sk",
          ExpressionAttributeValues: { ":pk": `TEAM#${ws.teamId}`, ":sk": `JOB#${id}` },
          Limit: 1,
        }),
      );
      const job = jobRes.Items?.[0];
      if (!job) continue;
      totalRecent++;
      if (job.status === "failed") failedRecent++;
      const metrics = typeof job.metrics === "object" && job.metrics !== null ? job.metrics as Record<string, unknown> : {};
      const tu = typeof metrics.token_usage === "object" && metrics.token_usage !== null
        ? metrics.token_usage as Record<string, unknown>
        : {};
      totalTokens += Number(tu.total_tokens ?? 0);
    }

    // 4. S3 orphan / stale upload detection.
    let s3Stats: Record<string, number> = {};
    try {
      const s3 = getS3Client();
      const Bucket = getS3BucketName();
      const now = Date.now();
      const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000; // 24 hours

      let staleUploads = 0;
      let totalUploadObjects = 0;
      let totalUploadBytes = 0;
      let continuationToken: string | undefined;

      do {
        const listRes = await s3.send(
          new ListObjectsV2Command({
            Bucket,
            Prefix: "uploads/",
            MaxKeys: 1000,
            ...(continuationToken ? { ContinuationToken: continuationToken } : {}),
          }),
        );
        for (const obj of listRes.Contents ?? []) {
          totalUploadObjects++;
          totalUploadBytes += obj.Size ?? 0;
          if (obj.LastModified && now - obj.LastModified.getTime() > STALE_THRESHOLD_MS) {
            staleUploads++;
          }
        }
        continuationToken = listRes.IsTruncated ? listRes.NextContinuationToken : undefined;
      } while (continuationToken);

      s3Stats = {
        totalUploadObjects,
        totalUploadBytes,
        staleUploads,
      };
    } catch {
      // S3 might not be configured in dev.
    }

    return withCache(
      NextResponse.json({
        ok: true,
        sqs: sqsStats,
        dlq: dlqStats,
        s3: s3Stats,
        runningJobs: runningJobs.length,
        runningJobDetails: runningJobs,
        recentStats: {
          total: totalRecent,
          failed: failedRecent,
          failureRate: totalRecent > 0 ? Math.round((failedRecent / totalRecent) * 100) : 0,
          totalTokens,
        },
        teamId: ws.teamId,
      }),
      10, 20,
    );
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}
