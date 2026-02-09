import { S3Client } from "@aws-sdk/client-s3";

import { getAwsRegion } from "@/lib/aws/env";

declare global {
  var __merry_s3: S3Client | undefined;
}

export function getS3Client(): S3Client {
  if (globalThis.__merry_s3) return globalThis.__merry_s3;
  const client = new S3Client({ region: getAwsRegion() });
  globalThis.__merry_s3 = client;
  return client;
}
