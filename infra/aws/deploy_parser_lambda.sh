#!/usr/bin/env bash
set -euo pipefail

# Deploy Ralph PDF parser as Lambda + API Gateway REST API with API Key auth.
#
# Prereqs:
#   - Admin/root AWS credentials configured
#   - Docker running locally
#   - IAM roles created: bash infra/aws/provision_iam.sh
#
# Usage:
#   AWS_PROFILE=merry-admin AWS_REGION=ap-northeast-2 bash infra/aws/deploy_parser_lambda.sh
#
# Re-running is idempotent (updates existing resources).

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
API_NAME="${MERRY_PARSER_API_NAME:-merry-parser}"
API_STAGE="${MERRY_PARSER_API_STAGE:-prod}"
API_KEY_NAME="${MERRY_PARSER_API_KEY_NAME:-merry-parser-key}"
USAGE_PLAN_NAME="${MERRY_PARSER_USAGE_PLAN:-merry-parser-plan}"
MEMORY_MB="${MERRY_PARSER_MEMORY:-1024}"
TIMEOUT_S="${MERRY_PARSER_TIMEOUT:-120}"

echo "[parser] region=$AWS_REGION"
aws sts get-caller-identity --region "$AWS_REGION" >/dev/null
ACCOUNT_ID="$(aws sts get-caller-identity --region "$AWS_REGION" --query Account --output text)"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

# ── 1. ECR repo ──────────────────────────────────────────────────────────────
echo "[parser] ensuring ECR repo: $ECR_REPO"
if aws ecr describe-repositories --region "$AWS_REGION" --repository-names "$ECR_REPO" >/dev/null 2>&1; then
  echo "  - exists"
else
  aws ecr create-repository --region "$AWS_REGION" --repository-name "$ECR_REPO" >/dev/null
  echo "  - created"
fi

# ── 2. Build & push image ─────────────────────────────────────────────────────
echo "[parser] building Docker image..."
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
docker build \
  --platform linux/amd64 \
  --provenance=false \
  -t "${ECR_REPO}:latest" \
  -f "${PROJECT_ROOT}/infra/lambda/Dockerfile" \
  "${PROJECT_ROOT}"

echo "[parser] pushing to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
docker tag "${ECR_REPO}:latest" "${ECR_URI}:latest"
docker push "${ECR_URI}:latest"
IMAGE_URI="${ECR_URI}:latest"
echo "  - pushed: $IMAGE_URI"

# ── 3. IAM role ───────────────────────────────────────────────────────────────
echo "[parser] resolving Lambda role: $LAMBDA_ROLE_NAME"
LAMBDA_ROLE_ARN="$(aws iam get-role --role-name "$LAMBDA_ROLE_NAME" \
  --query Role.Arn --output text)"

echo "[parser] ensuring Bedrock + S3 permissions on Lambda role..."
aws iam put-role-policy \
  --role-name "$LAMBDA_ROLE_NAME" \
  --policy-name "merry-lambda-bedrock" \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Sid":"BedrockNova","Effect":"Allow","Action":["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream"],"Resource":"*"}]}' \
  >/dev/null
aws iam put-role-policy \
  --role-name "$LAMBDA_ROLE_NAME" \
  --policy-name "merry-lambda-s3-read" \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Sid":"S3ReadUploads","Effect":"Allow","Action":["s3:GetObject"],"Resource":"arn:aws:s3:::merry-*/*"}]}' \
  >/dev/null

# ── 4. Lambda function ────────────────────────────────────────────────────────
echo "[parser] deploying Lambda: $FUNCTION_NAME"
ENV_VARS="Variables={RALPH_USE_VLM=true,RALPH_VLM_NOVA_MODEL_ID=us.amazon.nova-pro-v1:0,RALPH_VLM_NOVA_LITE_MODEL_ID=us.amazon.nova-lite-v1:0,RALPH_VLM_NOVA_REGION=us-east-1}"

if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "  - updating code..."
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" --region "$AWS_REGION" \
    --image-uri "$IMAGE_URI" >/dev/null
  aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" --region "$AWS_REGION"
  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" --region "$AWS_REGION" \
    --memory-size "$MEMORY_MB" --timeout "$TIMEOUT_S" \
    --environment "$ENV_VARS" >/dev/null
  aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" --region "$AWS_REGION"
else
  echo "  - creating..."
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" --region "$AWS_REGION" \
    --package-type Image --code ImageUri="$IMAGE_URI" \
    --role "$LAMBDA_ROLE_ARN" \
    --memory-size "$MEMORY_MB" --timeout "$TIMEOUT_S" \
    --environment "$ENV_VARS" >/dev/null
  aws lambda wait function-active \
    --function-name "$FUNCTION_NAME" --region "$AWS_REGION"
fi

LAMBDA_ARN="$(aws lambda get-function \
  --function-name "$FUNCTION_NAME" --region "$AWS_REGION" \
  --query Configuration.FunctionArn --output text)"
echo "  - ARN: $LAMBDA_ARN"

# ── 5. API Gateway REST API ───────────────────────────────────────────────────
echo "[parser] ensuring API Gateway: $API_NAME"
API_ID="$(aws apigateway get-rest-apis --region "$AWS_REGION" \
  --query "items[?name=='${API_NAME}'].id | [0]" --output text 2>/dev/null || true)"

if [[ -z "$API_ID" || "$API_ID" == "None" ]]; then
  API_ID="$(aws apigateway create-rest-api \
    --name "$API_NAME" --region "$AWS_REGION" \
    --description "Ralph PDF parser API" \
    --endpoint-configuration types=REGIONAL \
    --query id --output text)"
  echo "  - created: $API_ID"
else
  echo "  - exists: $API_ID"
fi

# Root resource
ROOT_ID="$(aws apigateway get-resources \
  --rest-api-id "$API_ID" --region "$AWS_REGION" \
  --query "items[?path=='/'].id | [0]" --output text)"

# /parse resource
RESOURCE_ID="$(aws apigateway get-resources \
  --rest-api-id "$API_ID" --region "$AWS_REGION" \
  --query "items[?pathPart=='parse'].id | [0]" --output text 2>/dev/null || true)"

if [[ -z "$RESOURCE_ID" || "$RESOURCE_ID" == "None" ]]; then
  RESOURCE_ID="$(aws apigateway create-resource \
    --rest-api-id "$API_ID" --region "$AWS_REGION" \
    --parent-id "$ROOT_ID" --path-part "parse" \
    --query id --output text)"
  echo "  - created /parse resource"
fi

# POST method (API Key required)
echo "[parser] configuring POST /parse..."
aws apigateway put-method \
  --rest-api-id "$API_ID" --region "$AWS_REGION" \
  --resource-id "$RESOURCE_ID" \
  --http-method POST \
  --authorization-type NONE \
  --api-key-required \
  >/dev/null 2>&1 || true   # already exists → ignore

LAMBDA_INTEGRATION_URI="arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations"
aws apigateway put-integration \
  --rest-api-id "$API_ID" --region "$AWS_REGION" \
  --resource-id "$RESOURCE_ID" \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "$LAMBDA_INTEGRATION_URI" \
  --content-handling CONVERT_TO_BINARY \
  >/dev/null

# Binary media types (PDF)
aws apigateway update-rest-api \
  --rest-api-id "$API_ID" --region "$AWS_REGION" \
  --patch-operations op=add,path=/binaryMediaTypes/application~1pdf \
  >/dev/null 2>&1 || true

# Method response
aws apigateway put-method-response \
  --rest-api-id "$API_ID" --region "$AWS_REGION" \
  --resource-id "$RESOURCE_ID" \
  --http-method POST --status-code 200 \
  >/dev/null 2>&1 || true

# ── 6. Lambda permission for API Gateway ─────────────────────────────────────
echo "[parser] granting API Gateway → Lambda invoke permission..."
aws lambda remove-permission \
  --function-name "$FUNCTION_NAME" --region "$AWS_REGION" \
  --statement-id AllowAPIGateway >/dev/null 2>&1 || true
aws lambda add-permission \
  --function-name "$FUNCTION_NAME" --region "$AWS_REGION" \
  --statement-id AllowAPIGateway \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${AWS_REGION}:${ACCOUNT_ID}:${API_ID}/*" \
  >/dev/null

# ── 7. Deploy to stage ────────────────────────────────────────────────────────
echo "[parser] deploying to stage: $API_STAGE"
aws apigateway create-deployment \
  --rest-api-id "$API_ID" --region "$AWS_REGION" \
  --stage-name "$API_STAGE" \
  >/dev/null

# ── 8. API Key + Usage Plan ───────────────────────────────────────────────────
echo "[parser] ensuring API Key: $API_KEY_NAME"
KEY_ID="$(aws apigateway get-api-keys --region "$AWS_REGION" \
  --query "items[?name=='${API_KEY_NAME}'].id | [0]" --output text 2>/dev/null || true)"

if [[ -z "$KEY_ID" || "$KEY_ID" == "None" ]]; then
  KEY_ID="$(aws apigateway create-api-key \
    --name "$API_KEY_NAME" --region "$AWS_REGION" \
    --enabled \
    --query id --output text)"
  echo "  - created: $KEY_ID"
else
  echo "  - exists: $KEY_ID"
fi

KEY_VALUE="$(aws apigateway get-api-key \
  --api-key "$KEY_ID" --region "$AWS_REGION" \
  --include-value --query value --output text)"

echo "[parser] ensuring Usage Plan: $USAGE_PLAN_NAME"
PLAN_ID="$(aws apigateway get-usage-plans --region "$AWS_REGION" \
  --query "items[?name=='${USAGE_PLAN_NAME}'].id | [0]" --output text 2>/dev/null || true)"

if [[ -z "$PLAN_ID" || "$PLAN_ID" == "None" ]]; then
  PLAN_ID="$(aws apigateway create-usage-plan \
    --name "$USAGE_PLAN_NAME" --region "$AWS_REGION" \
    --api-stages apiId="$API_ID",stage="$API_STAGE" \
    --throttle burstLimit=10,rateLimit=5 \
    --quota limit=1000,period=DAY \
    --query id --output text)"
  echo "  - created: $PLAN_ID"
else
  echo "  - exists (adding stage if needed)"
  aws apigateway update-usage-plan \
    --usage-plan-id "$PLAN_ID" --region "$AWS_REGION" \
    --patch-operations op=add,path=/apiStages,value="${API_ID}:${API_STAGE}" \
    >/dev/null 2>&1 || true
fi

# Link key to plan
aws apigateway create-usage-plan-key \
  --usage-plan-id "$PLAN_ID" --region "$AWS_REGION" \
  --key-id "$KEY_ID" --key-type API_KEY \
  >/dev/null 2>&1 || true   # already linked → ignore

ENDPOINT="https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${API_STAGE}/parse"

echo
echo "======================================"
echo "[parser] deploy complete!"
echo ""
echo "PARSER_INTERNAL_URL=${ENDPOINT%/parse}"
echo "PARSER_API_KEY=${KEY_VALUE}"
echo ""
echo "Test:"
echo "  curl -X POST \\"
echo "    -H 'x-api-key: ${KEY_VALUE}' \\"
echo "    -H 'Content-Type: application/pdf' \\"
echo "    --data-binary @sample.pdf \\"
echo "    '${ENDPOINT}'"
echo ""
echo "Next → add to Vercel:"
echo "  vercel env add PARSER_INTERNAL_URL production  # ${ENDPOINT%/parse}"
echo "  vercel env add PARSER_API_KEY production        # ${KEY_VALUE}"
echo "  vercel --prod --archive=tgz"
echo "======================================"
