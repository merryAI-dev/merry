#!/usr/bin/env bash
set -euo pipefail

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found. Install with: brew install awscli" >&2
  exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found" >&2
  exit 1
fi

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
MERRY_ECR_REPO="${MERRY_ECR_REPO:-merry-worker}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

aws sts get-caller-identity --region "$AWS_REGION" >/dev/null
ACCOUNT_ID="$(aws sts get-caller-identity --region "$AWS_REGION" --query Account --output text)"

REPO_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${MERRY_ECR_REPO}"

echo "[push] ensuring ECR repo: $MERRY_ECR_REPO"
if aws ecr describe-repositories --region "$AWS_REGION" --repository-names "$MERRY_ECR_REPO" >/dev/null 2>&1; then
  echo "  - exists"
else
  aws ecr create-repository --region "$AWS_REGION" --repository-name "$MERRY_ECR_REPO" >/dev/null
  echo "  - created"
fi

echo "[push] logging into ECR..."
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com" >/dev/null

echo "[push] building worker image..."
docker build -f worker/Dockerfile -t "merry-worker:${IMAGE_TAG}" . >/dev/null

echo "[push] tagging + pushing: ${REPO_URI}:${IMAGE_TAG}"
docker tag "merry-worker:${IMAGE_TAG}" "${REPO_URI}:${IMAGE_TAG}"
docker push "${REPO_URI}:${IMAGE_TAG}" >/dev/null

echo "[push] done"
echo "ECR_IMAGE=${REPO_URI}:${IMAGE_TAG}"

