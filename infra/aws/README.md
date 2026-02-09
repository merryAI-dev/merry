# AWS Bootstrap (CLI)

Region: `ap-northeast-2` (Seoul)

This repo expects:
- Private S3 bucket for uploads/artifacts
- DynamoDB single-table for metadata (pk/sk)
- SQS queue for analysis jobs
- (Optional) ECR repo for the Python worker image

## 0) Install AWS CLI

macOS (Homebrew):
```bash
brew install awscli
```

Verify:
```bash
aws --version
```

## 1) Configure Credentials

Pick one:
- Access keys: `aws configure`
- AWS SSO: `aws configure sso` then `aws sso login`

Verify:
```bash
aws sts get-caller-identity
```

## 2) Bootstrap Core Resources

Defaults match the current code:
- Bucket: `merry-private-apne2`
- Table: `merry-main`
- Queue: `merry-analysis-jobs` (+ DLQ)

Run:
```bash
AWS_REGION=ap-northeast-2 \
MERRY_S3_BUCKET=merry-private-apne2 \
MERRY_DDB_TABLE=merry-main \
MERRY_SQS_QUEUE_NAME=merry-analysis-jobs \
bash infra/aws/bootstrap.sh
```

The script prints:
- `MERRY_SQS_QUEUE_URL`
- DynamoDB table ARN

Verify current AWS state (helpful for debugging):
```bash
AWS_REGION=ap-northeast-2 \
MERRY_S3_BUCKET=merry-private-apne2 \
MERRY_DDB_TABLE=merry-main \
MERRY_SQS_QUEUE_NAME=merry-analysis-jobs \
bash infra/aws/doctor.sh
```

## 3) IAM (Vercel + Worker)

This repo includes a helper that creates:
- IAM user for Vercel (`merry-vercel`) with an inline policy
- IAM roles for ECS tasks (`merry-worker-task-role`, `merry-worker-exec-role`)

Run:
```bash
AWS_REGION=ap-northeast-2 \
MERRY_S3_BUCKET=merry-private-apne2 \
MERRY_DDB_TABLE=merry-main \
MERRY_SQS_QUEUE_NAME=merry-analysis-jobs \
bash infra/aws/provision_iam.sh
```

Optional: create access keys for the Vercel user and store them under `temp/aws/` (gitignored):
```bash
MERRY_CREATE_VERCEL_KEYS=1 bash infra/aws/provision_iam.sh
```

## 4) (Optional) Push Worker Image to ECR

```bash
AWS_REGION=ap-northeast-2 \
MERRY_ECR_REPO=merry-worker \
bash infra/aws/push_worker_image.sh
```

## 5) Deploy Worker to ECS Fargate

After you have `ECR_IMAGE=...` from the push script:
```bash
AWS_REGION=ap-northeast-2 \
ECR_IMAGE=471036546503.dkr.ecr.ap-northeast-2.amazonaws.com/merry-worker:latest \
MERRY_DDB_TABLE=merry-main \
MERRY_S3_BUCKET=merry-private-apne2 \
MERRY_SQS_QUEUE_URL=... \
LLM_PROVIDER=bedrock \
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0 \
bash infra/aws/deploy_worker_ecs.sh
```

## Notes

- S3 CORS needs your actual app origin(s). For local dev, this repo uses `http://localhost:3000`.
- Bucket lifecycle auto-expires `uploads/` in 1 day as a safety net.
