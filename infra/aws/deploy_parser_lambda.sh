#!/usr/bin/env bash
set -euo pipefail

# Deploy Ralph PDF parser as a Lambda container image with Function URL.
#
# Prereqs:
#   - Admin/root AWS credentials configured
#   - Docker running locally
#   - IAM roles created: provision_iam.sh (creates merry-lambda-role)
#
# Usage:
#   AWS_PROFILE=merry-admin AWS_REGION=ap-northeast-2 bash infra/aws/deploy_parser_lambda.sh
#
# Outputs PARSER_INTERNAL_URL (set this in Vercel env).

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found." >&2; exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found." >&2; exit 1
fi

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
FUNCTION_NAME="${MERRY_PARSER_FUNCTION:-merry-parser}"
ECR_REPO="${MERRY_PARSER_ECR_REPO:-merry-parser}"
LAMBDA_ROLE_NAME="${MERRY_LAMBDA_ROLE_NAME:-merry-lambda-role}"
MEMORY_MB="${MERRY_PARSER_MEMORY:-1024}"
TIMEOUT_S="${MERRY_PARSER_TIMEOUT:-120}"

echo "[parser-lambda] region=$AWS_REGION"
aws sts get-caller-identity --region "$AWS_REGION" >/dev/null
ACCOUNT_ID="$(aws sts get-caller-identity --region "$AWS_REGION" --query Account --output text)"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

# ── 1. ECR repo ──
echo "[parser-lambda] ensuring ECR repo: $ECR_REPO"
if aws ecr describe-repositories --region "$AWS_REGION" --repository-names "$ECR_REPO" >/dev/null 2>&1; then
  echo "  - exists"
else
  aws ecr create-repository --region "$AWS_REGION" --repository-name "$ECR_REPO" >/dev/null
  echo "  - created"
fi

# ── 2. Build & push image ──
echo "[parser-lambda] building Docker image..."
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
docker build \
  -t "${ECR_REPO}:latest" \
  -f "${PROJECT_ROOT}/infra/lambda/Dockerfile" \
  "${PROJECT_ROOT}"

echo "[parser-lambda] pushing to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker tag "${ECR_REPO}:latest" "${ECR_URI}:latest"
docker push "${ECR_URI}:latest"
IMAGE_URI="${ECR_URI}:latest"
echo "  - pushed: $IMAGE_URI"

# ── 3. IAM role ──
echo "[parser-lambda] resolving Lambda role: $LAMBDA_ROLE_NAME"
LAMBDA_ROLE_ARN="$(aws iam get-role --role-name "$LAMBDA_ROLE_NAME" \
  --query Role.Arn --output text)"
echo "  - $LAMBDA_ROLE_ARN"

# ── 4. Lambda function ──
echo "[parser-lambda] deploying Lambda function: $FUNCTION_NAME"
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "  - updating code..."
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --region "$AWS_REGION" \
    --image-uri "$IMAGE_URI" >/dev/null
  aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$AWS_REGION"
  echo "  - updating config..."
  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$AWS_REGION" \
    --memory-size "$MEMORY_MB" \
    --timeout "$TIMEOUT_S" >/dev/null
else
  echo "  - creating..."
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --region "$AWS_REGION" \
    --package-type Image \
    --code ImageUri="$IMAGE_URI" \
    --role "$LAMBDA_ROLE_ARN" \
    --memory-size "$MEMORY_MB" \
    --timeout "$TIMEOUT_S" >/dev/null
  aws lambda wait function-active \
    --function-name "$FUNCTION_NAME" \
    --region "$AWS_REGION"
fi

# ── 5. Environment variables ──
echo "[parser-lambda] setting environment variables..."
ENV_VARS="Variables={\
RALPH_USE_VLM=true,\
RALPH_VLM_NOVA_MODEL_ID=us.amazon.nova-pro-v1:0,\
RALPH_VLM_NOVA_LITE_MODEL_ID=us.amazon.nova-lite-v1:0,\
RALPH_VLM_NOVA_REGION=us-east-1\
}"
if [[ -n "${PARSER_INTERNAL_SECRET:-}" ]]; then
  ENV_VARS="Variables={\
RALPH_USE_VLM=true,\
RALPH_VLM_NOVA_MODEL_ID=us.amazon.nova-pro-v1:0,\
RALPH_VLM_NOVA_LITE_MODEL_ID=us.amazon.nova-lite-v1:0,\
RALPH_VLM_NOVA_REGION=us-east-1,\
PARSER_INTERNAL_SECRET=${PARSER_INTERNAL_SECRET}\
}"
fi
aws lambda update-function-configuration \
  --function-name "$FUNCTION_NAME" \
  --region "$AWS_REGION" \
  --environment "$ENV_VARS" >/dev/null

# ── 6. Bedrock invoke permission on task role ──
echo "[parser-lambda] ensuring Bedrock permission on Lambda role..."
BEDROCK_POLICY='{"Version":"2012-10-17","Statement":[{"Sid":"BedrockNova","Effect":"Allow","Action":["bedrock:InvokeModel"],"Resource":"*"}]}'
aws iam put-role-policy \
  --role-name "$LAMBDA_ROLE_NAME" \
  --policy-name "merry-lambda-bedrock" \
  --policy-document "$BEDROCK_POLICY" >/dev/null || true

# ── 7. Function URL ──
echo "[parser-lambda] ensuring Function URL..."
FUNC_URL="$(aws lambda get-function-url-config \
  --function-name "$FUNCTION_NAME" \
  --region "$AWS_REGION" \
  --query FunctionUrl --output text 2>/dev/null || true)"

if [[ -z "$FUNC_URL" || "$FUNC_URL" == "None" ]]; then
  FUNC_URL="$(aws lambda create-function-url-config \
    --function-name "$FUNCTION_NAME" \
    --region "$AWS_REGION" \
    --auth-type NONE \
    --query FunctionUrl --output text)"
  # Allow public invocation
  aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --region "$AWS_REGION" \
    --statement-id AllowPublicURL \
    --action lambda:InvokeFunctionUrl \
    --principal "*" \
    --function-url-auth-type NONE >/dev/null
  echo "  - created"
else
  echo "  - exists"
fi

echo
echo "======================================"
echo "[parser-lambda] deploy complete!"
echo "PARSER_INTERNAL_URL=${FUNC_URL%/}"
echo ""
echo "Next steps:"
echo "  1. Add to Vercel: vercel env add PARSER_INTERNAL_URL production"
echo "     Value: ${FUNC_URL%/}"
if [[ -n "${PARSER_INTERNAL_SECRET:-}" ]]; then
echo "  2. Add to Vercel: vercel env add PARSER_INTERNAL_SECRET production"
fi
echo "  3. Redeploy Vercel: vercel --prod --archive=tgz"
echo "======================================"
