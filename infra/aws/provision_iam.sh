#!/usr/bin/env bash
set -euo pipefail

# Creates the minimal IAM principals for:
# - Vercel (Next.js API): S3 presign + DDB metadata + SQS enqueue + (optional) Bedrock invoke
# - Worker (ECS task role): SQS consume + DDB update + S3 read/write/delete + Bedrock invoke
#
# This script is intentionally conservative:
# - It uses INLINE policies (put-user-policy / put-role-policy) so updates are idempotent.
# - It does NOT create access keys by default. To create keys for Vercel:
#     MERRY_CREATE_VERCEL_KEYS=1 bash infra/aws/provision_iam.sh

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

MERRY_VERCEL_USER_NAME="${MERRY_VERCEL_USER_NAME:-merry-vercel}"
MERRY_VERCEL_INLINE_POLICY_NAME="${MERRY_VERCEL_INLINE_POLICY_NAME:-merry-vercel-inline}"

MERRY_WORKER_TASK_ROLE_NAME="${MERRY_WORKER_TASK_ROLE_NAME:-merry-worker-task-role}"
MERRY_WORKER_EXEC_ROLE_NAME="${MERRY_WORKER_EXEC_ROLE_NAME:-merry-worker-exec-role}"
MERRY_WORKER_INLINE_POLICY_NAME="${MERRY_WORKER_INLINE_POLICY_NAME:-merry-worker-inline}"

MERRY_CREATE_VERCEL_KEYS="${MERRY_CREATE_VERCEL_KEYS:-0}"

echo "[iam] region=$AWS_REGION"
aws sts get-caller-identity --region "$AWS_REGION" >/dev/null
ACCOUNT_ID="$(aws sts get-caller-identity --region "$AWS_REGION" --query Account --output text)"

S3_UPLOADS_ARN="arn:aws:s3:::${MERRY_S3_BUCKET}/uploads/*"
S3_ARTIFACTS_ARN="arn:aws:s3:::${MERRY_S3_BUCKET}/artifacts/*"
DDB_TABLE_ARN="arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${MERRY_DDB_TABLE}"
SQS_QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${ACCOUNT_ID}:${MERRY_SQS_QUEUE_NAME}"
export S3_UPLOADS_ARN S3_ARTIFACTS_ARN DDB_TABLE_ARN SQS_QUEUE_ARN

echo "[iam] ensuring Vercel user: $MERRY_VERCEL_USER_NAME"
if aws iam get-user --user-name "$MERRY_VERCEL_USER_NAME" >/dev/null 2>&1; then
  echo "  - exists"
else
  aws iam create-user --user-name "$MERRY_VERCEL_USER_NAME" >/dev/null
  echo "  - created"
fi

echo "[iam] putting inline policy for Vercel user: $MERRY_VERCEL_INLINE_POLICY_NAME"
VECREL_POLICY_JSON="$(python3 - <<PY
import json, os
print(json.dumps({
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3UploadsAndArtifacts",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:HeadObject",
        "s3:AbortMultipartUpload",
        "s3:ListBucketMultipartUploads",
        "s3:ListMultipartUploadParts",
      ],
      "Resource": [os.environ["S3_UPLOADS_ARN"], os.environ["S3_ARTIFACTS_ARN"]],
    },
    {
      "Sid": "DynamoDbCrud",
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"],
      "Resource": os.environ["DDB_TABLE_ARN"],
    },
    {
      "Sid": "SqsSend",
      "Effect": "Allow",
      "Action": ["sqs:SendMessage"],
      "Resource": os.environ["SQS_QUEUE_ARN"],
    },
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": "*",
    },
  ],
}))
PY
)"
aws iam put-user-policy \
  --user-name "$MERRY_VERCEL_USER_NAME" \
  --policy-name "$MERRY_VERCEL_INLINE_POLICY_NAME" \
  --policy-document "$VECREL_POLICY_JSON" \
  >/dev/null

if [[ "$MERRY_CREATE_VERCEL_KEYS" == "1" ]]; then
  echo "[iam] creating access key for Vercel user (stored in temp/aws/)..."
  out_dir="temp/aws"
  mkdir -p "$out_dir"
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  out_path="${out_dir}/vercel_access_key_${ts}.json"
  aws iam create-access-key --user-name "$MERRY_VERCEL_USER_NAME" --output json >"$out_path"
  echo "  - wrote: $out_path"
else
  echo "[iam] skipping access key creation (set MERRY_CREATE_VERCEL_KEYS=1 to enable)"
fi

TRUST_JSON="$(cat <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ecs-tasks.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON
)"

echo "[iam] ensuring ECS task role: $MERRY_WORKER_TASK_ROLE_NAME"
if aws iam get-role --role-name "$MERRY_WORKER_TASK_ROLE_NAME" >/dev/null 2>&1; then
  echo "  - exists"
else
  aws iam create-role --role-name "$MERRY_WORKER_TASK_ROLE_NAME" --assume-role-policy-document "$TRUST_JSON" >/dev/null
  echo "  - created"
fi

echo "[iam] putting inline policy for worker task role: $MERRY_WORKER_INLINE_POLICY_NAME"
WORKER_POLICY_JSON="$(python3 - <<PY
import json, os
print(json.dumps({
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3ReadWriteAndDelete",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:HeadObject"],
      "Resource": [os.environ["S3_UPLOADS_ARN"], os.environ["S3_ARTIFACTS_ARN"]],
    },
    {
      "Sid": "DynamoDbReadUpdate",
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:UpdateItem"],
      "Resource": os.environ["DDB_TABLE_ARN"],
    },
    {
      "Sid": "SqsConsume",
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility",
        "sqs:GetQueueAttributes",
      ],
      "Resource": os.environ["SQS_QUEUE_ARN"],
    },
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": "*",
    },
  ],
}))
PY
)"
aws iam put-role-policy \
  --role-name "$MERRY_WORKER_TASK_ROLE_NAME" \
  --policy-name "$MERRY_WORKER_INLINE_POLICY_NAME" \
  --policy-document "$WORKER_POLICY_JSON" \
  >/dev/null

echo "[iam] ensuring ECS execution role: $MERRY_WORKER_EXEC_ROLE_NAME"
if aws iam get-role --role-name "$MERRY_WORKER_EXEC_ROLE_NAME" >/dev/null 2>&1; then
  echo "  - exists"
else
  aws iam create-role --role-name "$MERRY_WORKER_EXEC_ROLE_NAME" --assume-role-policy-document "$TRUST_JSON" >/dev/null
  echo "  - created"
fi

echo "[iam] attaching AmazonECSTaskExecutionRolePolicy to execution role (idempotent)"
aws iam attach-role-policy \
  --role-name "$MERRY_WORKER_EXEC_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy \
  >/dev/null || true

TASK_ROLE_ARN="$(aws iam get-role --role-name "$MERRY_WORKER_TASK_ROLE_NAME" --query Role.Arn --output text)"
EXEC_ROLE_ARN="$(aws iam get-role --role-name "$MERRY_WORKER_EXEC_ROLE_NAME" --query Role.Arn --output text)"

echo
echo "[iam] outputs:"
echo "AWS_ACCOUNT_ID=$ACCOUNT_ID"
echo "MERRY_VERCEL_USER_NAME=$MERRY_VERCEL_USER_NAME"
echo "MERRY_WORKER_TASK_ROLE_ARN=$TASK_ROLE_ARN"
echo "MERRY_WORKER_EXEC_ROLE_ARN=$EXEC_ROLE_ARN"
echo
echo "[iam] done"
