#!/usr/bin/env bash
set -euo pipefail

# Deploy three Lambda functions for fan-out job processing:
# 1. merry-stream-processor: DDB Streams → completion detection → invoke assembly
# 2. merry-assembly: aggregate task results → CSV/JSON → S3 → finalize job
# 3. merry-dlq-processor: SQS DLQ → mark failed tasks → maybe trigger assembly
#
# Prerequisites:
#   - Run bootstrap.sh first (creates DDB table with Streams, SQS queues)
#   - Run provision_iam.sh first (creates merry-lambda-role)
#
# Usage:
#   AWS_REGION=ap-northeast-2 \
#   MERRY_DDB_TABLE=merry-main \
#   MERRY_S3_BUCKET=merry-private-apne2-seoul-471036546503 \
#   bash infra/aws/deploy_lambdas.sh

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found." >&2
  exit 1
fi

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
MERRY_DDB_TABLE="${MERRY_DDB_TABLE:-merry-main}"
MERRY_S3_BUCKET="${MERRY_S3_BUCKET:-}"
MERRY_SQS_QUEUE_NAME="${MERRY_SQS_QUEUE_NAME:-merry-analysis-jobs}"
MERRY_LAMBDA_ROLE_NAME="${MERRY_LAMBDA_ROLE_NAME:-merry-lambda-role}"
MERRY_DELETE_INPUTS="${MERRY_DELETE_INPUTS:-true}"
MERRY_WEBHOOK_URL="${MERRY_WEBHOOK_URL:-}"

STREAM_PROCESSOR_NAME="merry-stream-processor"
ASSEMBLY_FUNCTION_NAME="merry-assembly"
DLQ_PROCESSOR_NAME="merry-dlq-processor"

if [[ -z "$MERRY_S3_BUCKET" ]]; then
  echo "ERROR: MERRY_S3_BUCKET is required." >&2
  exit 1
fi

echo "[lambdas] region=$AWS_REGION"
aws sts get-caller-identity --region "$AWS_REGION" >/dev/null
ACCOUNT_ID="$(aws sts get-caller-identity --region "$AWS_REGION" --query Account --output text)"

LAMBDA_ROLE_ARN="$(aws iam get-role --role-name "$MERRY_LAMBDA_ROLE_NAME" --query Role.Arn --output text 2>/dev/null || true)"
if [[ -z "$LAMBDA_ROLE_ARN" || "$LAMBDA_ROLE_ARN" == "None" ]]; then
  echo "ERROR: Lambda role '$MERRY_LAMBDA_ROLE_NAME' not found. Run provision_iam.sh first." >&2
  exit 1
fi
echo "[lambdas] role=$LAMBDA_ROLE_ARN"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAMBDAS_DIR="$SCRIPT_DIR/lambdas"
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

# ── Helper: package and deploy a Lambda function ──
deploy_lambda() {
  local func_name="$1"
  local source_dir="$2"
  local env_vars="$3"
  local timeout="${4:-60}"
  local memory="${5:-256}"

  echo "[lambdas] packaging: $func_name"
  local zip_path="$BUILD_DIR/${func_name}.zip"
  (cd "$source_dir" && zip -q -r "$zip_path" .)

  # Check if function exists.
  if aws lambda get-function --function-name "$func_name" --region "$AWS_REGION" >/dev/null 2>&1; then
    echo "[lambdas] updating code: $func_name"
    aws lambda update-function-code \
      --function-name "$func_name" \
      --region "$AWS_REGION" \
      --zip-file "fileb://$zip_path" \
      >/dev/null

    # Wait for update to complete before updating config.
    aws lambda wait function-updated --function-name "$func_name" --region "$AWS_REGION" 2>/dev/null || sleep 5

    echo "[lambdas] updating config: $func_name"
    aws lambda update-function-configuration \
      --function-name "$func_name" \
      --region "$AWS_REGION" \
      --timeout "$timeout" \
      --memory-size "$memory" \
      --environment "$env_vars" \
      >/dev/null
  else
    echo "[lambdas] creating: $func_name"
    aws lambda create-function \
      --function-name "$func_name" \
      --region "$AWS_REGION" \
      --runtime python3.12 \
      --handler handler.handler \
      --role "$LAMBDA_ROLE_ARN" \
      --zip-file "fileb://$zip_path" \
      --timeout "$timeout" \
      --memory-size "$memory" \
      --environment "$env_vars" \
      >/dev/null

    echo "  - waiting for function to become active..."
    aws lambda wait function-active --function-name "$func_name" --region "$AWS_REGION" 2>/dev/null || sleep 10
  fi

  echo "  - deployed: $func_name"
}

# ── 1. Stream Processor Lambda ──
STREAM_ENV="Variables={ASSEMBLY_FUNCTION_NAME=$ASSEMBLY_FUNCTION_NAME}"
deploy_lambda "$STREAM_PROCESSOR_NAME" "$LAMBDAS_DIR/stream_processor" "$STREAM_ENV" 30 128

# ── 2. Assembly Lambda ──
ASSEMBLY_ENV="Variables={MERRY_DDB_TABLE=$MERRY_DDB_TABLE,MERRY_S3_BUCKET=$MERRY_S3_BUCKET,MERRY_DELETE_INPUTS=$MERRY_DELETE_INPUTS,MERRY_WEBHOOK_URL=$MERRY_WEBHOOK_URL}"
deploy_lambda "$ASSEMBLY_FUNCTION_NAME" "$LAMBDAS_DIR/assembly" "$ASSEMBLY_ENV" 120 512

# ── 3. DLQ Processor Lambda ──
DLQ_ENV="Variables={MERRY_DDB_TABLE=$MERRY_DDB_TABLE,ASSEMBLY_FUNCTION_NAME=$ASSEMBLY_FUNCTION_NAME,MERRY_WEBHOOK_URL=$MERRY_WEBHOOK_URL}"
deploy_lambda "$DLQ_PROCESSOR_NAME" "$LAMBDAS_DIR/dlq_processor" "$DLQ_ENV" 60 256

# ── 4. Event Source Mapping: DDB Streams → Stream Processor ──
echo "[lambdas] configuring DDB Streams event source for: $STREAM_PROCESSOR_NAME"
STREAM_ARN="$(aws dynamodb describe-table --table-name "$MERRY_DDB_TABLE" --region "$AWS_REGION" --query 'Table.LatestStreamArn' --output text)"

if [[ -z "$STREAM_ARN" || "$STREAM_ARN" == "None" ]]; then
  echo "ERROR: DynamoDB Streams not enabled on $MERRY_DDB_TABLE. Run bootstrap.sh first." >&2
  exit 1
fi

# Check if mapping already exists.
EXISTING_UUID="$(aws lambda list-event-source-mappings \
  --function-name "$STREAM_PROCESSOR_NAME" \
  --event-source-arn "$STREAM_ARN" \
  --region "$AWS_REGION" \
  --query 'EventSourceMappings[0].UUID' \
  --output text 2>/dev/null || echo "None")"

if [[ -z "$EXISTING_UUID" || "$EXISTING_UUID" == "None" ]]; then
  # Create event source mapping with filter for JOB entities only.
  FILTER_JSON='{"Filters":[{"Pattern":"{\"dynamodb\":{\"NewImage\":{\"entity\":{\"S\":[\"job\"]}}}}"}]}'
  aws lambda create-event-source-mapping \
    --function-name "$STREAM_PROCESSOR_NAME" \
    --event-source-arn "$STREAM_ARN" \
    --region "$AWS_REGION" \
    --batch-size 10 \
    --starting-position LATEST \
    --maximum-retry-attempts 3 \
    --maximum-batching-window-in-seconds 5 \
    --filter-criteria "$FILTER_JSON" \
    >/dev/null
  echo "  - created event source mapping (DDB Streams → $STREAM_PROCESSOR_NAME)"
else
  echo "  - event source mapping already exists: $EXISTING_UUID"
fi

# ── 5. Event Source Mapping: SQS DLQ → DLQ Processor ──
echo "[lambdas] configuring SQS DLQ event source for: $DLQ_PROCESSOR_NAME"
DLQ_NAME="${MERRY_SQS_QUEUE_NAME}-dlq"
DLQ_ARN="arn:aws:sqs:${AWS_REGION}:${ACCOUNT_ID}:${DLQ_NAME}"

DLQ_UUID="$(aws lambda list-event-source-mappings \
  --function-name "$DLQ_PROCESSOR_NAME" \
  --event-source-arn "$DLQ_ARN" \
  --region "$AWS_REGION" \
  --query 'EventSourceMappings[0].UUID' \
  --output text 2>/dev/null || echo "None")"

if [[ -z "$DLQ_UUID" || "$DLQ_UUID" == "None" ]]; then
  aws lambda create-event-source-mapping \
    --function-name "$DLQ_PROCESSOR_NAME" \
    --event-source-arn "$DLQ_ARN" \
    --region "$AWS_REGION" \
    --batch-size 10 \
    >/dev/null
  echo "  - created event source mapping (SQS DLQ → $DLQ_PROCESSOR_NAME)"
else
  echo "  - event source mapping already exists: $DLQ_UUID"
fi

echo
echo "[lambdas] outputs:"
echo "STREAM_PROCESSOR=$STREAM_PROCESSOR_NAME"
echo "ASSEMBLY_FUNCTION=$ASSEMBLY_FUNCTION_NAME"
echo "DLQ_PROCESSOR=$DLQ_PROCESSOR_NAME"
echo "DDB_STREAM_ARN=$STREAM_ARN"
echo
echo "[lambdas] done"
