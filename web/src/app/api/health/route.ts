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
type LlmProvider = "bedrock" | "anthropic";

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
  const llmProviderRaw = (process.env.LLM_PROVIDER ?? "bedrock").toLowerCase().trim();
  const llmProvider: LlmProvider = llmProviderRaw === "anthropic" ? "anthropic" : "bedrock";

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
    NEXTAUTH_SECRET: Boolean(process.env.NEXTAUTH_SECRET),
    NEXTAUTH_URL: Boolean(process.env.NEXTAUTH_URL),
    AUTH_TEAM_ID: Boolean(process.env.AUTH_TEAM_ID),
    WORKSPACE_JWT_SECRET: Boolean(process.env.WORKSPACE_JWT_SECRET),
    ANTHROPIC_API_KEY: Boolean(process.env.ANTHROPIC_API_KEY),
  };

  const airtable = getAirtableConfig();
  const requiredEnv = [
    "AWS_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "MERRY_DDB_TABLE",
    "MERRY_S3_BUCKET",
    "MERRY_SQS_QUEUE_URL",
    "LLM_PROVIDER",
    llmProvider === "bedrock" ? "BEDROCK_MODEL_ID" : "ANTHROPIC_API_KEY",
  ] as const;

  const missingRequiredEnvs = requiredEnv.filter((key) => !env[key]);
  const hints: string[] = [];
  if (llmProvider === "bedrock" && !env.BEDROCK_MODEL_ID) {
    hints.push("LLM_PROVIDER=bedrock 인 경우 BEDROCK_MODEL_ID가 필요합니다.");
  }
  if (llmProvider === "anthropic" && !env.ANTHROPIC_API_KEY) {
    hints.push("LLM_PROVIDER=anthropic 인 경우 ANTHROPIC_API_KEY가 필요합니다.");
  }
  if (!env.NEXTAUTH_SECRET || !env.NEXTAUTH_URL) {
    hints.push("Google 로그인 사용 시 NEXTAUTH_SECRET, NEXTAUTH_URL 설정을 확인하세요.");
  }
  if (!env.AUTH_TEAM_ID || !env.WORKSPACE_JWT_SECRET) {
    hints.push("워크스페이스 세션 격리를 위해 AUTH_TEAM_ID, WORKSPACE_JWT_SECRET 설정을 확인하세요.");
  }

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

  const ok = missingRequiredEnvs.length === 0 && Object.values(checks).every((c) => c.ok);

  return NextResponse.json(
    {
      ok,
      summary: {
        llmProvider,
        missingRequiredEnvs,
      },
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
      hints,
    },
    { headers: { "cache-control": "no-store" } },
  );
}
