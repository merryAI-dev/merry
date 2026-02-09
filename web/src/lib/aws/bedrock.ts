import { BedrockRuntimeClient } from "@aws-sdk/client-bedrock-runtime";

import { getAwsRegion } from "@/lib/aws/env";

declare global {
  // Cached across hot reloads in dev and across route handlers in a single runtime.
  var __merry_bedrock: BedrockRuntimeClient | undefined;
}

export function getBedrockRuntimeClient(): BedrockRuntimeClient {
  if (globalThis.__merry_bedrock) return globalThis.__merry_bedrock;
  const client = new BedrockRuntimeClient({ region: getAwsRegion() });
  globalThis.__merry_bedrock = client;
  return client;
}
