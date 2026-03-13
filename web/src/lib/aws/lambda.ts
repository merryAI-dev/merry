import { LambdaClient } from "@aws-sdk/client-lambda";

import { getAwsRegion } from "@/lib/aws/env";

declare global {
  var __merry_lambda: LambdaClient | undefined;
}

export function getLambdaClient(): LambdaClient {
  if (globalThis.__merry_lambda) return globalThis.__merry_lambda;
  const client = new LambdaClient({ region: getAwsRegion() });
  globalThis.__merry_lambda = client;
  return client;
}
