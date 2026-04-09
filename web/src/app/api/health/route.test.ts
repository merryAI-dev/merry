import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { ddbSendMock, s3SendMock, sqsSendMock, airtableConfigMock } = vi.hoisted(() => ({
  ddbSendMock: vi.fn(),
  s3SendMock: vi.fn(),
  sqsSendMock: vi.fn(),
  airtableConfigMock: vi.fn(),
}));

vi.mock("@/lib/aws/ddb", () => ({
  getDdbDocClient: () => ({ send: ddbSendMock }),
}));

vi.mock("@/lib/aws/s3", () => ({
  getS3Client: () => ({ send: s3SendMock }),
}));

vi.mock("@/lib/aws/sqs", () => ({
  getSqsClient: () => ({ send: sqsSendMock }),
}));

vi.mock("@/lib/airtableServer", () => ({
  getAirtableConfig: airtableConfigMock,
}));

import { GET } from "./route";

const ENV_KEYS = [
  "AWS_REGION",
  "AWS_ACCESS_KEY_ID",
  "AWS_SECRET_ACCESS_KEY",
  "MERRY_DDB_TABLE",
  "MERRY_REVIEW_DDB_TABLE",
  "MERRY_DIAGNOSIS_DDB_TABLE",
  "MERRY_S3_BUCKET",
  "MERRY_SQS_QUEUE_URL",
  "LLM_PROVIDER",
  "BEDROCK_MODEL_ID",
  "ANTHROPIC_API_KEY",
] as const;

let originalEnv: Partial<Record<(typeof ENV_KEYS)[number], string | undefined>> = {};

function setHealthyBaseEnv() {
  process.env.AWS_REGION = "ap-northeast-2";
  process.env.AWS_ACCESS_KEY_ID = "test-key";
  process.env.AWS_SECRET_ACCESS_KEY = "test-secret";
  process.env.MERRY_DDB_TABLE = "merry-main";
  process.env.MERRY_REVIEW_DDB_TABLE = "merry-review";
  process.env.MERRY_DIAGNOSIS_DDB_TABLE = "merry-diagnosis";
  process.env.MERRY_S3_BUCKET = "merry-bucket";
  process.env.MERRY_SQS_QUEUE_URL = "https://example.com/queue";
  process.env.LLM_PROVIDER = "bedrock";
  process.env.BEDROCK_MODEL_ID = "model";
  delete process.env.ANTHROPIC_API_KEY;
}

beforeEach(() => {
  originalEnv = {};
  for (const key of ENV_KEYS) {
    originalEnv[key] = process.env[key];
  }
  setHealthyBaseEnv();
  ddbSendMock.mockReset();
  s3SendMock.mockReset();
  sqsSendMock.mockReset();
  airtableConfigMock.mockReset();
  ddbSendMock.mockResolvedValue({});
  s3SendMock.mockResolvedValue({});
  sqsSendMock.mockResolvedValue({});
  airtableConfigMock.mockReturnValue(null);
});

afterEach(() => {
  for (const key of ENV_KEYS) {
    const value = originalEnv[key];
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }
});

describe("health route", () => {
  it("reports unhealthy when the review table env is missing", async () => {
    delete process.env.MERRY_REVIEW_DDB_TABLE;

    const response = await GET();
    const body = await response.json();

    expect(body.ok).toBe(false);
    expect(body.summary.missingRequiredEnvs).toContain("MERRY_REVIEW_DDB_TABLE");
  });

  it("reports unhealthy when the review table describe check fails", async () => {
    ddbSendMock.mockImplementation(async (command: { input?: { TableName?: string } }) => {
      if (command.input?.TableName === "merry-review") {
        throw new Error("review table missing");
      }
      return {};
    });

    const response = await GET();
    const body = await response.json();

    expect(body.ok).toBe(false);
    expect(body.checks.ddbDescribeReviewTable.ok).toBe(false);
    expect(body.checks.ddbDescribeReviewTable.error).toContain("review table missing");
  });
});
