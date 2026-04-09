export function getAwsRegion(): string {
  const region = process.env.AWS_REGION ?? process.env.AWS_DEFAULT_REGION;
  if (!region) {
    throw new Error("Missing env AWS_REGION");
  }
  return region;
}

export function getDdbTableName(): string {
  const name = process.env.MERRY_DDB_TABLE;
  if (!name) {
    throw new Error("Missing env MERRY_DDB_TABLE");
  }
  return name;
}

export function getReviewDdbTableName(): string {
  const name = process.env.MERRY_REVIEW_DDB_TABLE;
  if (!name) {
    throw new Error("Missing env MERRY_REVIEW_DDB_TABLE");
  }
  return name;
}

export function getDiagnosisDdbTableName(): string {
  const name = process.env.MERRY_DIAGNOSIS_DDB_TABLE;
  if (!name) {
    throw new Error("Missing env MERRY_DIAGNOSIS_DDB_TABLE");
  }
  return name;
}

export function getS3BucketName(): string {
  const name = process.env.MERRY_S3_BUCKET;
  if (!name) {
    throw new Error("Missing env MERRY_S3_BUCKET");
  }
  return name;
}

export function getSqsQueueUrl(): string {
  const url = process.env.MERRY_SQS_QUEUE_URL;
  if (!url) {
    throw new Error("Missing env MERRY_SQS_QUEUE_URL");
  }
  return url;
}

/** Derive DLQ URL from main queue URL (convention: {queue-name}-dlq). */
export function getSqsDlqUrl(): string {
  const explicit = process.env.MERRY_SQS_DLQ_URL;
  if (explicit) return explicit;
  const mainUrl = getSqsQueueUrl();
  return `${mainUrl}-dlq`;
}
