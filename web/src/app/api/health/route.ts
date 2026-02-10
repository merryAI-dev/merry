import { NextResponse } from "next/server";

import { HeadBucketCommand } from "@aws-sdk/client-s3";
import { GetQueueAttributesCommand } from "@aws-sdk/client-sqs";
import { DescribeTableCommand } from "@aws-sdk/client-dynamodb";

import { getAirtableConfig } from "@/lib/airtableServer";
import { getDdbDocClient } from "@/lib/aws/ddb";
import { getS3Client } from "@/lib/aws/s3";
import { getSqsClient } from "@/lib/aws/sqs";
import { getAwsRegion, getDdbTableName, getS3BucketName, getSqsQueueUrl } from "@/lib/aws/env";

export const runtime = "nodejs";

type CheckResult = { ok: true } | { ok: false; error: string };

function asErrorString(err: unknown): string {
  if (err instanceof Error) return err.message || err.name || "Error";
  if (err && typeof err === "object" && "name" in err) return String((err as any).name);
  return String(err);
}

async function safeCheck(fn: () => Promise<void>): Promise<CheckResult> {
  try {
    await fn();
    return { ok: true };
  } catch (err) {
    return { ok: false, error: asErrorString(err) };
  }
}

export async function GET() {
  const env = {
    AWS_REGION: Boolean(process.env.AWS_REGION ?? process.env.AWS_DEFAULT_REGION),
    AWS_ACCESS_KEY_ID: Boolean(process.env.AWS_ACCESS_KEY_ID),
    AWS_SECRET_ACCESS_KEY: Boolean(process.env.AWS_SECRET_ACCESS_KEY),
    MERRY_DDB_TABLE: Boolean(process.env.MERRY_DDB_TABLE),
    MERRY_S3_BUCKET: Boolean(process.env.MERRY_S3_BUCKET),
    MERRY_SQS_QUEUE_URL: Boolean(process.env.MERRY_SQS_QUEUE_URL),
    LLM_PROVIDER: Boolean(process.env.LLM_PROVIDER),
    BEDROCK_MODEL_ID: Boolean(process.env.BEDROCK_MODEL_ID),
    AIRTABLE_API_TOKEN: Boolean(process.env.AIRTABLE_API_TOKEN ?? process.env.AIRTABLE_API_KEY),
    AIRTABLE_BASE_ID: Boolean(process.env.AIRTABLE_BASE_ID),
    GOOGLE_CLIENT_ID: Boolean(process.env.GOOGLE_CLIENT_ID),
    GOOGLE_CLIENT_SECRET: Boolean(process.env.GOOGLE_CLIENT_SECRET),
  };

  const airtable = getAirtableConfig();

  const region = env.AWS_REGION ? getAwsRegion() : null;
  const ddbTable = env.MERRY_DDB_TABLE ? getDdbTableName() : null;
  const bucket = env.MERRY_S3_BUCKET ? getS3BucketName() : null;
  const sqsUrl = env.MERRY_SQS_QUEUE_URL ? getSqsQueueUrl() : null;

  const checks = {
    ddbDescribeTable: await safeCheck(async () => {
      if (!ddbTable) throw new Error("Missing env MERRY_DDB_TABLE");
      const ddb = getDdbDocClient();
      await ddb.send(new DescribeTableCommand({ TableName: ddbTable }));
    }),
    s3HeadBucket: await safeCheck(async () => {
      if (!bucket) throw new Error("Missing env MERRY_S3_BUCKET");
      const s3 = getS3Client();
      await s3.send(new HeadBucketCommand({ Bucket: bucket }));
    }),
    sqsGetQueueAttributes: await safeCheck(async () => {
      if (!sqsUrl) throw new Error("Missing env MERRY_SQS_QUEUE_URL");
      const sqs = getSqsClient();
      await sqs.send(new GetQueueAttributesCommand({ QueueUrl: sqsUrl, AttributeNames: ["QueueArn"] }));
    }),
  } as const;

  const ok = Object.values(checks).every((c) => c.ok);

  return NextResponse.json(
    {
      ok,
      env,
      region,
      ddbTable,
      bucket,
      sqsUrl,
      airtableConfigured: Boolean(airtable),
      airtableTables: airtable
        ? {
            fundsTable: airtable.fundsTable,
            fundsView: airtable.fundsView ?? null,
            companiesTable: airtable.companiesTable ?? null,
            snapshotsTable: airtable.snapshotsTable ?? null,
            snapshotsView: airtable.snapshotsView ?? null,
          }
        : null,
      checks,
    },
    { headers: { "cache-control": "no-store" } },
  );
}
