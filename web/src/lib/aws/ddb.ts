import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient } from "@aws-sdk/lib-dynamodb";

import { getAwsRegion } from "@/lib/aws/env";

declare global {
  var __merry_ddb_doc: DynamoDBDocumentClient | undefined;
}

export function getDdbDocClient(): DynamoDBDocumentClient {
  if (globalThis.__merry_ddb_doc) return globalThis.__merry_ddb_doc;
  const client = new DynamoDBClient({ region: getAwsRegion() });
  const doc = DynamoDBDocumentClient.from(client, {
    marshallOptions: {
      removeUndefinedValues: true,
    },
  });
  globalThis.__merry_ddb_doc = doc;
  return doc;
}
