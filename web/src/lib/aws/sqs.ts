import { SQSClient } from "@aws-sdk/client-sqs";

import { getAwsRegion } from "@/lib/aws/env";

declare global {
  var __merry_sqs: SQSClient | undefined;
}

export function getSqsClient(): SQSClient {
  if (globalThis.__merry_sqs) return globalThis.__merry_sqs;
  const client = new SQSClient({ region: getAwsRegion() });
  globalThis.__merry_sqs = client;
  return client;
}
