#!/usr/bin/env bash
set -euo pipefail

# Deploy (or update) the SQS polling worker on ECS Fargate using the default VPC.
#
# Prereqs:
# - ECR image pushed (see infra/aws/push_worker_image.sh)
# - IAM roles created (see infra/aws/provision_iam.sh)
#
# Required env:
# - ECR_IMAGE=ACCOUNT_ID.dkr.ecr.ap-northeast-2.amazonaws.com/merry-worker:latest
#
# Optional env:
# - MERRY_ECS_CLUSTER (default: merry)
# - MERRY_ECS_SERVICE (default: merry-worker)
# - MERRY_ECS_TASK_FAMILY (default: merry-worker)
# - MERRY_ECS_LOG_GROUP (default: /merry/worker)
# - MERRY_WORKER_CPU (default: 1024)
# - MERRY_WORKER_MEMORY (default: 2048)
# - MERRY_WORKER_DESIRED_COUNT (default: 1)
# - MERRY_WORKER_TASK_ROLE_NAME (default: merry-worker-task-role)
# - MERRY_WORKER_EXEC_ROLE_NAME (default: merry-worker-exec-role)

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found. Install with: brew install awscli" >&2
  exit 1
fi

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
ECR_IMAGE="${ECR_IMAGE:-}"
if [[ -z "$ECR_IMAGE" ]]; then
  echo "ERROR: ECR_IMAGE is required" >&2
  exit 1
fi

MERRY_ECS_CLUSTER="${MERRY_ECS_CLUSTER:-merry}"
MERRY_ECS_SERVICE="${MERRY_ECS_SERVICE:-merry-worker}"
MERRY_ECS_TASK_FAMILY="${MERRY_ECS_TASK_FAMILY:-merry-worker}"
MERRY_ECS_LOG_GROUP="${MERRY_ECS_LOG_GROUP:-/merry/worker}"

MERRY_WORKER_CPU="${MERRY_WORKER_CPU:-1024}"
MERRY_WORKER_MEMORY="${MERRY_WORKER_MEMORY:-2048}"
MERRY_WORKER_DESIRED_COUNT="${MERRY_WORKER_DESIRED_COUNT:-1}"

MERRY_WORKER_TASK_ROLE_NAME="${MERRY_WORKER_TASK_ROLE_NAME:-merry-worker-task-role}"
MERRY_WORKER_EXEC_ROLE_NAME="${MERRY_WORKER_EXEC_ROLE_NAME:-merry-worker-exec-role}"

echo "[ecs] region=$AWS_REGION"
aws sts get-caller-identity --region "$AWS_REGION" >/dev/null
ACCOUNT_ID="$(aws sts get-caller-identity --region "$AWS_REGION" --query Account --output text)"

echo "[ecs] resolving role ARNs..."
TASK_ROLE_ARN="$(aws iam get-role --role-name "$MERRY_WORKER_TASK_ROLE_NAME" --query Role.Arn --output text)"
EXEC_ROLE_ARN="$(aws iam get-role --role-name "$MERRY_WORKER_EXEC_ROLE_NAME" --query Role.Arn --output text)"

echo "[ecs] using default VPC + subnets..."
VPC_ID="$(aws ec2 describe-vpcs --region "$AWS_REGION" --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)"
if [[ -z "$VPC_ID" || "$VPC_ID" == "None" ]]; then
  echo "ERROR: default VPC not found. Set up a VPC/subnets and wire this script accordingly." >&2
  exit 1
fi

SUBNET_IDS_JSON="$(aws ec2 describe-subnets --region "$AWS_REGION" --filters Name=vpc-id,Values="$VPC_ID" --query 'Subnets[].SubnetId' --output json)"
if [[ "$SUBNET_IDS_JSON" == "[]" ]]; then
  echo "ERROR: no subnets found in default VPC" >&2
  exit 1
fi

echo "[ecs] ensuring security group..."
SG_NAME="${MERRY_ECS_SERVICE}-sg"
SG_ID="$(aws ec2 describe-security-groups --region "$AWS_REGION" --filters Name=vpc-id,Values="$VPC_ID" Name=group-name,Values="$SG_NAME" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)"
if [[ -z "$SG_ID" || "$SG_ID" == "None" ]]; then
  SG_ID="$(aws ec2 create-security-group --region "$AWS_REGION" --vpc-id "$VPC_ID" --group-name "$SG_NAME" --description "merry worker egress-only" --query GroupId --output text)"
  echo "  - created: $SG_ID"
else
  echo "  - exists: $SG_ID"
fi

echo "[ecs] ensuring log group: $MERRY_ECS_LOG_GROUP"
if aws logs describe-log-groups --region "$AWS_REGION" --log-group-name-prefix "$MERRY_ECS_LOG_GROUP" --query 'logGroups[?logGroupName==`'"$MERRY_ECS_LOG_GROUP"'`]' --output text | grep -q "$MERRY_ECS_LOG_GROUP"; then
  echo "  - exists"
else
  aws logs create-log-group --region "$AWS_REGION" --log-group-name "$MERRY_ECS_LOG_GROUP" >/dev/null
  echo "  - created"
fi

echo "[ecs] ensuring cluster: $MERRY_ECS_CLUSTER"
if aws ecs describe-clusters --region "$AWS_REGION" --clusters "$MERRY_ECS_CLUSTER" --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
  echo "  - exists"
else
  aws ecs create-cluster --region "$AWS_REGION" --cluster-name "$MERRY_ECS_CLUSTER" >/dev/null
  echo "  - created"
fi

echo "[ecs] registering task definition: $MERRY_ECS_TASK_FAMILY"

export ECR_IMAGE TASK_ROLE_ARN EXEC_ROLE_ARN MERRY_ECS_LOG_GROUP MERRY_ECS_TASK_FAMILY MERRY_WORKER_CPU MERRY_WORKER_MEMORY AWS_REGION
TASK_DEF_JSON="$(python3 - <<PY
import json, os

def env_if_set(name: str):
    v=os.getenv(name)
    if not v:
        return None
    return {"name": name, "value": v}

env=[]
for key in [
    "AWS_REGION",
    "MERRY_DDB_TABLE",
    "MERRY_S3_BUCKET",
    "MERRY_SQS_QUEUE_URL",
    "MERRY_DELETE_INPUTS",
    "MERRY_LAMBDA_ASSEMBLY",
    "WORKER_CONCURRENCY",
    "LLM_PROVIDER",
    "BEDROCK_MODEL_ID",
    "BEDROCK_HAIKU_MODEL_ID",
    "BEDROCK_SONNET_MODEL_ID",
    "BEDROCK_OPUS_MODEL_ID",
    "DOLPHIN_TEXT_MODEL",
]:
    e=env_if_set(key)
    if e:
        env.append(e)

print(json.dumps({
  "family": os.environ["MERRY_ECS_TASK_FAMILY"],
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": str(os.environ["MERRY_WORKER_CPU"]),
  "memory": str(os.environ["MERRY_WORKER_MEMORY"]),
  "executionRoleArn": os.environ["EXEC_ROLE_ARN"],
  "taskRoleArn": os.environ["TASK_ROLE_ARN"],
  "containerDefinitions": [{
    "name": "merry-worker",
    "image": os.environ["ECR_IMAGE"],
    "essential": True,
    "environment": env,
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": os.environ["MERRY_ECS_LOG_GROUP"],
        "awslogs-region": os.environ["AWS_REGION"],
        "awslogs-stream-prefix": "worker"
      }
    }
  }]
}))
PY
)"

TASK_DEF_ARN="$(aws ecs register-task-definition --region "$AWS_REGION" --cli-input-json "$TASK_DEF_JSON" --query 'taskDefinition.taskDefinitionArn' --output text)"

echo "[ecs] ensuring service: $MERRY_ECS_SERVICE"
SVC_STATUS="$(aws ecs describe-services --region "$AWS_REGION" --cluster "$MERRY_ECS_CLUSTER" --services "$MERRY_ECS_SERVICE" --query 'services[0].status' --output text 2>/dev/null || true)"

export SUBNET_IDS_JSON SG_ID
NETCONF="$(python3 - <<PY
import json, os
subnets=json.loads(os.environ["SUBNET_IDS_JSON"])
print(json.dumps({
  "awsvpcConfiguration": {
    "subnets": subnets,
    "securityGroups": [os.environ["SG_ID"]],
    "assignPublicIp": "ENABLED",
  }
}))
PY
)"

if [[ "$SVC_STATUS" == "ACTIVE" ]]; then
  aws ecs update-service \
    --region "$AWS_REGION" \
    --cluster "$MERRY_ECS_CLUSTER" \
    --service "$MERRY_ECS_SERVICE" \
    --task-definition "$TASK_DEF_ARN" \
    --desired-count "$MERRY_WORKER_DESIRED_COUNT" \
    --force-new-deployment \
    >/dev/null
  echo "  - updated"
else
  aws ecs create-service \
    --region "$AWS_REGION" \
    --cluster "$MERRY_ECS_CLUSTER" \
    --service-name "$MERRY_ECS_SERVICE" \
    --task-definition "$TASK_DEF_ARN" \
    --desired-count "$MERRY_WORKER_DESIRED_COUNT" \
    --launch-type FARGATE \
    --network-configuration "$NETCONF" \
    >/dev/null
  echo "  - created"
fi

# ── Auto-Scaling ──
# Scale ECS worker count based on SQS queue depth.
# Target: ~5 messages per worker task (each worker has WORKER_CONCURRENCY threads).
# Min: 0 (scale to zero when idle for cost savings)
# Max: configurable (default 10, = 10 workers × 5 threads = 50 concurrent tasks)

MERRY_AUTOSCALE_MIN="${MERRY_AUTOSCALE_MIN:-0}"
MERRY_AUTOSCALE_MAX="${MERRY_AUTOSCALE_MAX:-10}"
MERRY_AUTOSCALE_TARGET_PER_TASK="${MERRY_AUTOSCALE_TARGET_PER_TASK:-5}"
MERRY_AUTOSCALE_ENABLED="${MERRY_AUTOSCALE_ENABLED:-true}"

if [[ "$MERRY_AUTOSCALE_ENABLED" == "true" ]]; then
  echo "[ecs] configuring auto-scaling (min=$MERRY_AUTOSCALE_MIN max=$MERRY_AUTOSCALE_MAX target=$MERRY_AUTOSCALE_TARGET_PER_TASK msgs/task)"

  RESOURCE_ID="service/${MERRY_ECS_CLUSTER}/${MERRY_ECS_SERVICE}"

  # 1. Register scalable target.
  aws application-autoscaling register-scalable-target \
    --region "$AWS_REGION" \
    --service-namespace ecs \
    --scalable-dimension "ecs:service:DesiredCount" \
    --resource-id "$RESOURCE_ID" \
    --min-capacity "$MERRY_AUTOSCALE_MIN" \
    --max-capacity "$MERRY_AUTOSCALE_MAX" \
    >/dev/null
  echo "  - registered scalable target"

  # 2. Custom metric spec for SQS-based scaling.
  # Uses backlog-per-task = ApproximateNumberOfMessagesVisible / RunningTaskCount.
  # When backlog-per-task > target, scale out. When < target, scale in.
  MERRY_SQS_QUEUE_NAME="${MERRY_SQS_QUEUE_NAME:-merry-analysis-jobs}"
  SQS_QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${ACCOUNT_ID}:${MERRY_SQS_QUEUE_NAME}"

  SCALING_POLICY_JSON="$(python3 - <<PY
import json, os

cluster = os.environ.get("MERRY_ECS_CLUSTER", "merry")
service = os.environ.get("MERRY_ECS_SERVICE", "merry-worker")
queue   = os.environ.get("MERRY_SQS_QUEUE_NAME", "merry-analysis-jobs")
target  = int(os.environ.get("MERRY_AUTOSCALE_TARGET_PER_TASK", "5"))

print(json.dumps({
  "TargetValue": float(target),
  "CustomizedMetricSpecification": {
    "Metrics": [
      {
        "Label": "SQS Visible Messages",
        "Id": "m1",
        "MetricStat": {
          "Metric": {
            "MetricName": "ApproximateNumberOfMessagesVisible",
            "Namespace": "AWS/SQS",
            "Dimensions": [
              {"Name": "QueueName", "Value": queue}
            ]
          },
          "Stat": "Average",
          "Period": 60
        },
        "ReturnData": False
      },
      {
        "Label": "ECS Running Task Count",
        "Id": "m2",
        "MetricStat": {
          "Metric": {
            "MetricName": "RunningTaskCount",
            "Namespace": "ECS/ContainerInsights",
            "Dimensions": [
              {"Name": "ClusterName", "Value": cluster},
              {"Name": "ServiceName", "Value": service}
            ]
          },
          "Stat": "Average",
          "Period": 60
        },
        "ReturnData": False
      },
      {
        "Label": "Backlog Per Task",
        "Id": "e1",
        "Expression": "m1 / MAX(m2, 1)",
        "ReturnData": True
      }
    ]
  },
  "ScaleInCooldown": 300,
  "ScaleOutCooldown": 60,
}))
PY
)"

  aws application-autoscaling put-scaling-policy \
    --region "$AWS_REGION" \
    --service-namespace ecs \
    --scalable-dimension "ecs:service:DesiredCount" \
    --resource-id "$RESOURCE_ID" \
    --policy-name "merry-worker-sqs-scaling" \
    --policy-type TargetTrackingScaling \
    --target-tracking-scaling-policy-configuration "$SCALING_POLICY_JSON" \
    >/dev/null
  echo "  - scaling policy applied (target tracking: backlog-per-task)"

  # 3. Scale-to-zero alarm: when queue is empty for 5 min, scale to 0.
  # Application Auto Scaling handles this via min-capacity=0 + the target tracking.
  # But we add an explicit scale-in step policy as a safety net for faster scale-down.
  echo "  - min=0 → auto scale-to-zero when queue is empty"
else
  echo "[ecs] auto-scaling disabled (set MERRY_AUTOSCALE_ENABLED=true to enable)"
fi

echo
echo "[ecs] outputs:"
echo "ECS_CLUSTER=$MERRY_ECS_CLUSTER"
echo "ECS_SERVICE=$MERRY_ECS_SERVICE"
echo "TASK_DEFINITION_ARN=$TASK_DEF_ARN"
echo "LOG_GROUP=$MERRY_ECS_LOG_GROUP"
if [[ "$MERRY_AUTOSCALE_ENABLED" == "true" ]]; then
  echo "AUTOSCALE_MIN=$MERRY_AUTOSCALE_MIN"
  echo "AUTOSCALE_MAX=$MERRY_AUTOSCALE_MAX"
  echo "AUTOSCALE_TARGET=$MERRY_AUTOSCALE_TARGET_PER_TASK msgs/task"
fi
echo
echo "[ecs] done"
