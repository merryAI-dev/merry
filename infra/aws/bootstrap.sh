#!/usr/bin/env bash
set -euo pipefail

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found. Install with: brew install awscli" >&2
  exit 1
fi

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
MERRY_S3_BUCKET="${MERRY_S3_BUCKET:-}"
MERRY_DDB_TABLE="${MERRY_DDB_TABLE:-merry-main}"
MERRY_SQS_QUEUE_NAME="${MERRY_SQS_QUEUE_NAME:-merry-analysis-jobs}"
MERRY_SQS_DLQ_NAME="${MERRY_SQS_DLQ_NAME:-${MERRY_SQS_QUEUE_NAME}-dlq}"

if [[ -z "$MERRY_S3_BUCKET" ]]; then
  echo "ERROR: MERRY_S3_BUCKET is required (create an S3 bucket in ap-northeast-2 and export it)." >&2
  exit 1
fi

export AWS_REGION
export MERRY_S3_BUCKET
export MERRY_DDB_TABLE
export MERRY_SQS_QUEUE_NAME
export MERRY_SQS_DLQ_NAME

echo "[bootstrap] region=$AWS_REGION"

echo "[bootstrap] verifying credentials..."
aws sts get-caller-identity --region "$AWS_REGION" >/dev/null

echo "[bootstrap] ensuring DynamoDB table: $MERRY_DDB_TABLE"
if aws dynamodb describe-table --table-name "$MERRY_DDB_TABLE" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "  - exists"
else
  aws dynamodb create-table \
    --region "$AWS_REGION" \
    --table-name "$MERRY_DDB_TABLE" \
    --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    >/dev/null

  echo "  - created"
fi

TABLE_ARN="$(aws dynamodb describe-table --table-name "$MERRY_DDB_TABLE" --region "$AWS_REGION" --query 'Table.TableArn' --output text)"

echo "[bootstrap] ensuring DynamoDB Streams enabled on: $MERRY_DDB_TABLE"
STREAM_STATUS="$(aws dynamodb describe-table --table-name "$MERRY_DDB_TABLE" --region "$AWS_REGION" --query 'Table.StreamSpecification.StreamEnabled' --output text 2>/dev/null || echo "None")"
if [[ "$STREAM_STATUS" == "True" ]]; then
  echo "  - streams already enabled"
else
  aws dynamodb update-table \
    --region "$AWS_REGION" \
    --table-name "$MERRY_DDB_TABLE" \
    --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES \
    >/dev/null
  echo "  - enabled (NEW_AND_OLD_IMAGES)"
  echo "  - waiting for table to become ACTIVE..."
  aws dynamodb wait table-exists --table-name "$MERRY_DDB_TABLE" --region "$AWS_REGION"
fi

STREAM_ARN="$(aws dynamodb describe-table --table-name "$MERRY_DDB_TABLE" --region "$AWS_REGION" --query 'Table.LatestStreamArn' --output text)"

echo "[bootstrap] ensuring DynamoDB TTL enabled on: $MERRY_DDB_TABLE"
TTL_STATUS="$(aws dynamodb describe-time-to-live --table-name "$MERRY_DDB_TABLE" --region "$AWS_REGION" --query 'TimeToLiveDescription.TimeToLiveStatus' --output text 2>/dev/null || echo "DISABLED")"
if [[ "$TTL_STATUS" == "ENABLED" ]]; then
  echo "  - TTL already enabled"
else
  aws dynamodb update-time-to-live \
    --region "$AWS_REGION" \
    --table-name "$MERRY_DDB_TABLE" \
    --time-to-live-specification Enabled=true,AttributeName=ttl \
    >/dev/null 2>&1 || true
  echo "  - enabled (attribute=ttl)"
fi

echo "[bootstrap] ensuring SQS DLQ: $MERRY_SQS_DLQ_NAME"
DLQ_URL="$(aws sqs get-queue-url --queue-name "$MERRY_SQS_DLQ_NAME" --region "$AWS_REGION" --query 'QueueUrl' --output text 2>/dev/null || true)"
if [[ -z "$DLQ_URL" || "$DLQ_URL" == "None" ]]; then
  DLQ_URL="$(aws sqs create-queue --queue-name "$MERRY_SQS_DLQ_NAME" --region "$AWS_REGION" --query 'QueueUrl' --output text)"
  echo "  - created"
else
  echo "  - exists"
fi

DLQ_ARN="$(aws sqs get-queue-attributes --queue-url "$DLQ_URL" --region "$AWS_REGION" --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)"

echo "[bootstrap] ensuring SQS queue: $MERRY_SQS_QUEUE_NAME"
QUEUE_URL="$(aws sqs get-queue-url --queue-name "$MERRY_SQS_QUEUE_NAME" --region "$AWS_REGION" --query 'QueueUrl' --output text 2>/dev/null || true)"
if [[ -z "$QUEUE_URL" || "$QUEUE_URL" == "None" ]]; then
  # Use JSON syntax for --attributes because RedrivePolicy contains commas.
  ATTRS_JSON="$(python3 - <<PY
import json
redrive=json.dumps({"deadLetterTargetArn": "${DLQ_ARN}", "maxReceiveCount": "3"}, separators=(",", ":"))
print(json.dumps({
  "VisibilityTimeout": "900",
  "ReceiveMessageWaitTimeSeconds": "20",
  "RedrivePolicy": redrive,
}))
PY
)"
  QUEUE_URL="$(aws sqs create-queue \
    --queue-name "$MERRY_SQS_QUEUE_NAME" \
    --region "$AWS_REGION" \
    --attributes "$ATTRS_JSON" \
    --query 'QueueUrl' --output text)"
  echo "  - created"
else
  echo "  - exists (updating attributes)"
  # Ensure redrive policy is current on existing queues.
  REDRIVE_JSON="$(python3 -c "import json; print(json.dumps({'deadLetterTargetArn': '${DLQ_ARN}', 'maxReceiveCount': '3'}, separators=(',',':')))")"
  aws sqs set-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --region "$AWS_REGION" \
    --attributes "{\"RedrivePolicy\": $(python3 -c "import json; print(json.dumps('$REDRIVE_JSON'))")}" \
    >/dev/null 2>&1 || true
fi

echo "[bootstrap] configuring S3 bucket (guardrails): $MERRY_S3_BUCKET"

if aws s3api head-bucket --bucket "$MERRY_S3_BUCKET" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "  - bucket exists"
else
  echo "ERROR: bucket not found: $MERRY_S3_BUCKET (create it first)" >&2
  exit 1
fi

aws s3api put-public-access-block --region "$AWS_REGION" --bucket "$MERRY_S3_BUCKET" --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
  >/dev/null

aws s3api put-bucket-ownership-controls --region "$AWS_REGION" --bucket "$MERRY_S3_BUCKET" --ownership-controls \
  "Rules=[{ObjectOwnership=BucketOwnerEnforced}]" \
  >/dev/null

# CORS: default to localhost; override via MERRY_CORS_ORIGINS="https://your.vercel.app,http://localhost:3000"
CORS_ORIGINS_RAW="${MERRY_CORS_ORIGINS:-http://localhost:3000}"
export CORS_ORIGINS_RAW
CORS_JSON="$(python3 - <<PY
import json, os
origins=[o.strip() for o in os.environ["CORS_ORIGINS_RAW"].split(",") if o.strip()]
print(json.dumps({
  "CORSRules": [{
    "AllowedOrigins": origins,
    "AllowedMethods": ["PUT","GET","HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag","x-amz-request-id","x-amz-id-2"],
    "MaxAgeSeconds": 3000
  }]
}))
PY
)"
aws s3api put-bucket-cors --region "$AWS_REGION" --bucket "$MERRY_S3_BUCKET" --cors-configuration "$CORS_JSON" >/dev/null

# Lifecycle rules:
# - uploads/: expire after 7 days (buffer for delayed processing / retries)
# - artifacts/: expire after 90 days (completed job results)
#   + transition to Infrequent Access after 30 days for cost savings
# - Incomplete multipart uploads: abort after 3 days (prevent orphan cost)
LIFECYCLE_JSON="$(python3 - <<PY
import json
print(json.dumps({
  "Rules": [
    {
      "ID": "ExpireUploads",
      "Status": "Enabled",
      "Filter": {"Prefix": "uploads/"},
      "Expiration": {"Days": 7}
    },
    {
      "ID": "ExpireArtifacts",
      "Status": "Enabled",
      "Filter": {"Prefix": "artifacts/"},
      "Transitions": [
        {"Days": 30, "StorageClass": "STANDARD_IA"}
      ],
      "Expiration": {"Days": 90}
    },
    {
      "ID": "AbortIncompleteMultipart",
      "Status": "Enabled",
      "Filter": {"Prefix": ""},
      "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 3}
    },
  ]
}))
PY
)"
aws s3api put-bucket-lifecycle-configuration --region "$AWS_REGION" --bucket "$MERRY_S3_BUCKET" --lifecycle-configuration "$LIFECYCLE_JSON" >/dev/null

# Bucket policy: TLS-only (deny insecure transport)
POLICY_JSON="$(python3 - <<PY
import json, os
bucket=os.environ["MERRY_S3_BUCKET"]
print(json.dumps({
  "Version":"2012-10-17",
  "Statement":[{
    "Sid":"DenyInsecureTransport",
    "Effect":"Deny",
    "Principal":"*",
    "Action":"s3:*",
    "Resource":[f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"],
    "Condition":{"Bool":{"aws:SecureTransport":"false"}}
  }]
}))
PY
)"
aws s3api put-bucket-policy --region "$AWS_REGION" --bucket "$MERRY_S3_BUCKET" --policy "$POLICY_JSON" >/dev/null

echo
echo "[bootstrap] outputs:"
echo "AWS_REGION=$AWS_REGION"
echo "MERRY_S3_BUCKET=$MERRY_S3_BUCKET"
echo "MERRY_DDB_TABLE=$MERRY_DDB_TABLE"
echo "MERRY_SQS_QUEUE_URL=$QUEUE_URL"
echo "DDB_TABLE_ARN=$TABLE_ARN"
echo "DDB_STREAM_ARN=$STREAM_ARN"
echo
echo "[bootstrap] done"
