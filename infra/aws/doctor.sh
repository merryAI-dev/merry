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

if [[ -z "$MERRY_S3_BUCKET" ]]; then
  echo "ERROR: MERRY_S3_BUCKET is required (S3 bucket name in ap-northeast-2)." >&2
  exit 1
fi

echo "[doctor] region=$AWS_REGION"

echo "[doctor] verifying credentials..."
if ! aws sts get-caller-identity --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "ERROR: AWS credentials not configured." >&2
  echo "  - Access keys: aws configure" >&2
  echo "  - SSO: aws configure sso && aws sso login" >&2
  exit 1
fi

ACCOUNT_ID="$(aws sts get-caller-identity --region "$AWS_REGION" --query Account --output text)"
echo "[doctor] account=$ACCOUNT_ID"

echo
echo "[doctor] S3 bucket: $MERRY_S3_BUCKET"
if aws s3api head-bucket --bucket "$MERRY_S3_BUCKET" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "  - exists"
else
  echo "  - MISSING (create it first)" >&2
fi

echo "  - public access block:"
aws s3api get-public-access-block --bucket "$MERRY_S3_BUCKET" --region "$AWS_REGION" --output json 2>/dev/null || echo "    (none)"
echo "  - ownership controls:"
aws s3api get-bucket-ownership-controls --bucket "$MERRY_S3_BUCKET" --region "$AWS_REGION" --output json 2>/dev/null || echo "    (none)"
echo "  - encryption:"
aws s3api get-bucket-encryption --bucket "$MERRY_S3_BUCKET" --region "$AWS_REGION" --output json 2>/dev/null || echo "    (none)"
echo "  - CORS:"
aws s3api get-bucket-cors --bucket "$MERRY_S3_BUCKET" --region "$AWS_REGION" --output json 2>/dev/null || echo "    (none)"
echo "  - lifecycle:"
aws s3api get-bucket-lifecycle-configuration --bucket "$MERRY_S3_BUCKET" --region "$AWS_REGION" --output json 2>/dev/null || echo "    (none)"
echo "  - policy:"
aws s3api get-bucket-policy --bucket "$MERRY_S3_BUCKET" --region "$AWS_REGION" --output json 2>/dev/null || echo "    (none)"

echo
echo "[doctor] DynamoDB table: $MERRY_DDB_TABLE"
if aws dynamodb describe-table --table-name "$MERRY_DDB_TABLE" --region "$AWS_REGION" >/dev/null 2>&1; then
  STATUS="$(aws dynamodb describe-table --table-name "$MERRY_DDB_TABLE" --region "$AWS_REGION" --query 'Table.TableStatus' --output text)"
  ARN="$(aws dynamodb describe-table --table-name "$MERRY_DDB_TABLE" --region "$AWS_REGION" --query 'Table.TableArn' --output text)"
  echo "  - status=$STATUS"
  echo "  - arn=$ARN"
else
  echo "  - MISSING (run infra/aws/bootstrap.sh)" >&2
fi

echo
echo "[doctor] SQS queue: $MERRY_SQS_QUEUE_NAME"
QUEUE_URL="$(aws sqs get-queue-url --queue-name "$MERRY_SQS_QUEUE_NAME" --region "$AWS_REGION" --query QueueUrl --output text 2>/dev/null || true)"
if [[ -z "$QUEUE_URL" || "$QUEUE_URL" == "None" ]]; then
  echo "  - MISSING (run infra/aws/bootstrap.sh)" >&2
else
  QUEUE_ARN="$(aws sqs get-queue-attributes --queue-url "$QUEUE_URL" --region "$AWS_REGION" --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)"
  echo "  - url=$QUEUE_URL"
  echo "  - arn=$QUEUE_ARN"
fi

echo
echo "[doctor] Suggested env (Vercel + worker):"
echo "AWS_REGION=$AWS_REGION"
echo "MERRY_S3_BUCKET=$MERRY_S3_BUCKET"
echo "MERRY_DDB_TABLE=$MERRY_DDB_TABLE"
if [[ -n "$QUEUE_URL" && "$QUEUE_URL" != "None" ]]; then
  echo "MERRY_SQS_QUEUE_URL=$QUEUE_URL"
fi
