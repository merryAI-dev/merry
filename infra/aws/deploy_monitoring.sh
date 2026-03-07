#!/usr/bin/env bash
set -euo pipefail

# Deploy CloudWatch monitoring for the Merry batch processing system:
# 1. CloudWatch Dashboard: SQS depth, ECS task count, Lambda metrics, DLQ depth
# 2. SNS Topic for alerts
# 3. CloudWatch Alarms: DLQ messages, Lambda errors, high queue depth
#
# Usage:
#   AWS_REGION=ap-northeast-2 \
#   MERRY_ALERT_EMAIL=team@example.com \
#   bash infra/aws/deploy_monitoring.sh

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found." >&2
  exit 1
fi

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
MERRY_SQS_QUEUE_NAME="${MERRY_SQS_QUEUE_NAME:-merry-analysis-jobs}"
MERRY_ECS_CLUSTER="${MERRY_ECS_CLUSTER:-merry}"
MERRY_ECS_SERVICE="${MERRY_ECS_SERVICE:-merry-worker}"
MERRY_ALERT_EMAIL="${MERRY_ALERT_EMAIL:-}"

DASHBOARD_NAME="merry-batch-processing"
SNS_TOPIC_NAME="merry-alerts"
DLQ_NAME="${MERRY_SQS_QUEUE_NAME}-dlq"

echo "[monitoring] region=$AWS_REGION"
aws sts get-caller-identity --region "$AWS_REGION" >/dev/null
ACCOUNT_ID="$(aws sts get-caller-identity --region "$AWS_REGION" --query Account --output text)"

# ── 1. SNS Topic ──
echo "[monitoring] ensuring SNS topic: $SNS_TOPIC_NAME"
SNS_ARN="$(aws sns create-topic --name "$SNS_TOPIC_NAME" --region "$AWS_REGION" --query TopicArn --output text)"
echo "  - ARN: $SNS_ARN"

if [[ -n "$MERRY_ALERT_EMAIL" ]]; then
  echo "[monitoring] subscribing email: $MERRY_ALERT_EMAIL"
  aws sns subscribe \
    --topic-arn "$SNS_ARN" \
    --protocol email \
    --notification-endpoint "$MERRY_ALERT_EMAIL" \
    --region "$AWS_REGION" \
    >/dev/null 2>&1 || true
  echo "  - subscription created (check email for confirmation)"
fi

# ── 2. CloudWatch Alarms ──

echo "[monitoring] creating alarms..."

# Alarm: DLQ has messages (any message in DLQ = something failed max retries)
aws cloudwatch put-metric-alarm \
  --region "$AWS_REGION" \
  --alarm-name "merry-dlq-messages" \
  --alarm-description "Messages in DLQ — tasks exceeded max retries" \
  --namespace "AWS/SQS" \
  --metric-name "ApproximateNumberOfMessagesVisible" \
  --dimensions "Name=QueueName,Value=$DLQ_NAME" \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --alarm-actions "$SNS_ARN" \
  --ok-actions "$SNS_ARN" \
  --treat-missing-data notBreaching \
  >/dev/null
echo "  - merry-dlq-messages"

# Alarm: Queue depth too high (>500 messages for >10 min = potential backlog)
aws cloudwatch put-metric-alarm \
  --region "$AWS_REGION" \
  --alarm-name "merry-queue-backlog" \
  --alarm-description "SQS queue depth >500 for >10 min — possible processing bottleneck" \
  --namespace "AWS/SQS" \
  --metric-name "ApproximateNumberOfMessagesVisible" \
  --dimensions "Name=QueueName,Value=$MERRY_SQS_QUEUE_NAME" \
  --statistic Average \
  --period 300 \
  --threshold 500 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions "$SNS_ARN" \
  --ok-actions "$SNS_ARN" \
  --treat-missing-data notBreaching \
  >/dev/null
echo "  - merry-queue-backlog"

# Alarm: Stream Processor Lambda errors
aws cloudwatch put-metric-alarm \
  --region "$AWS_REGION" \
  --alarm-name "merry-stream-processor-errors" \
  --alarm-description "Stream Processor Lambda invocation errors" \
  --namespace "AWS/Lambda" \
  --metric-name "Errors" \
  --dimensions "Name=FunctionName,Value=merry-stream-processor" \
  --statistic Sum \
  --period 300 \
  --threshold 3 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --alarm-actions "$SNS_ARN" \
  --treat-missing-data notBreaching \
  >/dev/null
echo "  - merry-stream-processor-errors"

# Alarm: Assembly Lambda errors
aws cloudwatch put-metric-alarm \
  --region "$AWS_REGION" \
  --alarm-name "merry-assembly-errors" \
  --alarm-description "Assembly Lambda invocation errors" \
  --namespace "AWS/Lambda" \
  --metric-name "Errors" \
  --dimensions "Name=FunctionName,Value=merry-assembly" \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --alarm-actions "$SNS_ARN" \
  --treat-missing-data notBreaching \
  >/dev/null
echo "  - merry-assembly-errors"

# ── 3. CloudWatch Dashboard ──

echo "[monitoring] creating dashboard: $DASHBOARD_NAME"

export MERRY_SQS_QUEUE_NAME DLQ_NAME MERRY_ECS_CLUSTER MERRY_ECS_SERVICE AWS_REGION
DASHBOARD_BODY="$(python3 - <<'PY'
import json, os

region = os.environ["AWS_REGION"]
queue = os.environ["MERRY_SQS_QUEUE_NAME"]
dlq = os.environ["DLQ_NAME"]
cluster = os.environ["MERRY_ECS_CLUSTER"]
service = os.environ["MERRY_ECS_SERVICE"]

widgets = [
  # Row 1: SQS metrics
  {
    "type": "metric", "x": 0, "y": 0, "width": 12, "height": 6,
    "properties": {
      "title": "SQS Queue Depth",
      "region": region,
      "metrics": [
        ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", queue, {"label": "Visible"}],
        ["AWS/SQS", "ApproximateNumberOfMessagesNotVisible", "QueueName", queue, {"label": "In-Flight"}],
        ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", dlq, {"label": "DLQ", "color": "#d62728"}],
      ],
      "view": "timeSeries", "stacked": False, "period": 60, "stat": "Average",
    },
  },
  {
    "type": "metric", "x": 12, "y": 0, "width": 12, "height": 6,
    "properties": {
      "title": "SQS Throughput",
      "region": region,
      "metrics": [
        ["AWS/SQS", "NumberOfMessagesSent", "QueueName", queue, {"label": "Sent", "stat": "Sum"}],
        ["AWS/SQS", "NumberOfMessagesReceived", "QueueName", queue, {"label": "Received", "stat": "Sum"}],
        ["AWS/SQS", "NumberOfMessagesDeleted", "QueueName", queue, {"label": "Deleted", "stat": "Sum"}],
      ],
      "view": "timeSeries", "stacked": False, "period": 60,
    },
  },
  # Row 2: ECS metrics
  {
    "type": "metric", "x": 0, "y": 6, "width": 12, "height": 6,
    "properties": {
      "title": "ECS Worker Tasks",
      "region": region,
      "metrics": [
        ["ECS/ContainerInsights", "RunningTaskCount", "ClusterName", cluster, "ServiceName", service],
        ["ECS/ContainerInsights", "DesiredTaskCount", "ClusterName", cluster, "ServiceName", service],
      ],
      "view": "timeSeries", "stacked": False, "period": 60, "stat": "Average",
    },
  },
  {
    "type": "metric", "x": 12, "y": 6, "width": 12, "height": 6,
    "properties": {
      "title": "ECS CPU / Memory",
      "region": region,
      "metrics": [
        ["ECS/ContainerInsights", "CpuUtilized", "ClusterName", cluster, "ServiceName", service, {"label": "CPU Used"}],
        ["ECS/ContainerInsights", "MemoryUtilized", "ClusterName", cluster, "ServiceName", service, {"label": "Memory Used"}],
      ],
      "view": "timeSeries", "stacked": False, "period": 60, "stat": "Average",
    },
  },
  # Row 3: Lambda metrics
  {
    "type": "metric", "x": 0, "y": 12, "width": 8, "height": 6,
    "properties": {
      "title": "Lambda Invocations",
      "region": region,
      "metrics": [
        ["AWS/Lambda", "Invocations", "FunctionName", "merry-stream-processor", {"label": "Stream", "stat": "Sum"}],
        ["AWS/Lambda", "Invocations", "FunctionName", "merry-assembly", {"label": "Assembly", "stat": "Sum"}],
        ["AWS/Lambda", "Invocations", "FunctionName", "merry-dlq-processor", {"label": "DLQ", "stat": "Sum"}],
      ],
      "view": "timeSeries", "stacked": False, "period": 60,
    },
  },
  {
    "type": "metric", "x": 8, "y": 12, "width": 8, "height": 6,
    "properties": {
      "title": "Lambda Errors",
      "region": region,
      "metrics": [
        ["AWS/Lambda", "Errors", "FunctionName", "merry-stream-processor", {"label": "Stream", "stat": "Sum", "color": "#d62728"}],
        ["AWS/Lambda", "Errors", "FunctionName", "merry-assembly", {"label": "Assembly", "stat": "Sum", "color": "#ff7f0e"}],
        ["AWS/Lambda", "Errors", "FunctionName", "merry-dlq-processor", {"label": "DLQ", "stat": "Sum", "color": "#9467bd"}],
      ],
      "view": "timeSeries", "stacked": False, "period": 60,
    },
  },
  {
    "type": "metric", "x": 16, "y": 12, "width": 8, "height": 6,
    "properties": {
      "title": "Lambda Duration (ms)",
      "region": region,
      "metrics": [
        ["AWS/Lambda", "Duration", "FunctionName", "merry-stream-processor", {"label": "Stream", "stat": "Average"}],
        ["AWS/Lambda", "Duration", "FunctionName", "merry-assembly", {"label": "Assembly", "stat": "Average"}],
        ["AWS/Lambda", "Duration", "FunctionName", "merry-dlq-processor", {"label": "DLQ", "stat": "Average"}],
      ],
      "view": "timeSeries", "stacked": False, "period": 60,
    },
  },
]

print(json.dumps({"widgets": widgets}))
PY
)"

aws cloudwatch put-dashboard \
  --region "$AWS_REGION" \
  --dashboard-name "$DASHBOARD_NAME" \
  --dashboard-body "$DASHBOARD_BODY" \
  >/dev/null
echo "  - created"

echo
echo "[monitoring] outputs:"
echo "DASHBOARD=https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=${DASHBOARD_NAME}"
echo "SNS_TOPIC_ARN=$SNS_ARN"
echo
echo "[monitoring] done"
