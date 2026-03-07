"""
DLQ Processor Lambda: Handle failed SQS messages.

Trigger: SQS DLQ (merry-analysis-jobs-dlq).

For fan-out v2 messages:
1. Mark TASK as failed (if not already completed).
2. Atomically increment JOB failed_count + processed_count.
3. Check if all tasks are now done → invoke Assembly Lambda if so.

For legacy messages:
1. Mark JOB as failed.

This ensures no job is stuck waiting for a task that will never complete
because the worker gave up after maxReceiveCount retries.
"""

from __future__ import annotations

import json
import logging
import os
import time
import random
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3

log = logging.getLogger()
log.setLevel(logging.INFO)

DDB_TABLE_NAME = os.environ.get("MERRY_DDB_TABLE", "merry-main")
ASSEMBLY_FUNCTION_NAME = os.environ.get("ASSEMBLY_FUNCTION_NAME", "merry-assembly")
WEBHOOK_URL = os.environ.get("MERRY_WEBHOOK_URL", "")
WEBHOOK_MAX_RETRIES = int(os.environ.get("MERRY_WEBHOOK_MAX_RETRIES", "3"))

ddb = boto3.resource("dynamodb").Table(DDB_TABLE_NAME)
ddb_client = boto3.client("dynamodb")
lambda_client = boto3.client("lambda")


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    records = event.get("Records", [])
    processed = 0
    errors = 0

    for record in records:
        body_raw = record.get("body", "")
        try:
            payload = json.loads(body_raw)
        except json.JSONDecodeError:
            log.warning("Invalid JSON in DLQ message, skipping")
            _emit_metric("DLQInvalidMessage", 1)
            continue

        version = payload.get("version")
        team_id = str(payload.get("teamId", ""))
        job_id = str(payload.get("jobId", ""))

        if not team_id or not job_id:
            log.warning("Missing teamId/jobId in DLQ message: %s", body_raw[:200])
            _emit_metric("DLQInvalidMessage", 1)
            continue

        try:
            if version == 2:
                _handle_fanout_dlq(payload, team_id, job_id)
                _emit_metric("DLQFanoutTaskFailed", 1, team_id=team_id)
            else:
                _handle_legacy_dlq(team_id, job_id)
                _emit_metric("DLQLegacyJobFailed", 1, team_id=team_id)
            processed += 1
        except Exception as exc:
            log.error("DLQ processing error: team=%s job=%s error=%s", team_id, job_id, exc)
            _emit_metric("DLQProcessingError", 1, team_id=team_id)
            errors += 1

    _emit_metric("DLQMessagesProcessed", processed)
    _emit_metric("DLQProcessingErrors", errors)

    return {"processed": processed, "errors": errors}


def _handle_fanout_dlq(
    payload: Dict[str, Any], team_id: str, job_id: str,
) -> None:
    """Mark a fan-out task as failed and update job counters."""
    task_id = str(payload.get("taskId", ""))
    file_id = str(payload.get("fileId", ""))
    now = _now_iso()

    log.info("DLQ fan-out: team=%s job=%s task=%s file=%s", team_id, job_id, task_id, file_id)

    if not task_id:
        log.warning("Missing taskId in DLQ v2 message")
        return

    pk = f"TEAM#{team_id}"
    sk = f"TASK#{job_id}#{task_id}"

    # Only update if task is still pending or processing (not already succeeded/failed).
    try:
        ddb.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression=(
                "SET #status = :failed, #error = :error, #ended_at = :now, #updated_at = :now"
            ),
            ConditionExpression="#status IN (:pending, :processing)",
            ExpressionAttributeNames={
                "#status": "status",
                "#error": "error",
                "#ended_at": "ended_at",
                "#updated_at": "updated_at",
            },
            ExpressionAttributeValues={
                ":failed": "failed",
                ":error": "Exceeded max retries (DLQ)",
                ":now": now,
                ":pending": "pending",
                ":processing": "processing",
            },
        )
    except ddb.meta.client.exceptions.ConditionalCheckFailedException:
        log.info("Task %s/%s already completed, skipping DLQ update", job_id, task_id)
        return

    # Update TASK index.
    try:
        ddb.update_item(
            Key={
                "pk": f"TEAM#{team_id}#TASKS#{job_id}",
                "sk": f"TASK#{task_id}",
            },
            UpdateExpression="SET #status = :failed, #updated_at = :now",
            ExpressionAttributeNames={
                "#status": "status",
                "#updated_at": "updated_at",
            },
            ExpressionAttributeValues={
                ":failed": "failed",
                ":now": now,
            },
        )
    except Exception:
        pass  # Best-effort.

    # Atomically increment job counters.
    ddb_client.transact_write_items(
        TransactItems=[
            {
                "Update": {
                    "TableName": DDB_TABLE_NAME,
                    "Key": {"pk": {"S": pk}, "sk": {"S": f"JOB#{job_id}"}},
                    "UpdateExpression": "ADD #pc :one, #fc :one SET #updated_at = :now",
                    "ExpressionAttributeNames": {
                        "#pc": "processed_count",
                        "#fc": "failed_count",
                        "#updated_at": "updated_at",
                    },
                    "ExpressionAttributeValues": {
                        ":one": {"N": "1"},
                        ":now": {"S": now},
                    },
                }
            }
        ]
    )

    # Notify via webhook.
    _send_webhook(job_id, f"Task {task_id} exceeded max retries (file={file_id})")

    # Check completion → trigger assembly.
    _maybe_trigger_assembly(team_id, job_id)


def _handle_legacy_dlq(team_id: str, job_id: str) -> None:
    """Mark a legacy job as failed."""
    now = _now_iso()
    log.info("DLQ legacy: team=%s job=%s", team_id, job_id)

    ddb.update_item(
        Key={"pk": f"TEAM#{team_id}", "sk": f"JOB#{job_id}"},
        UpdateExpression="SET #status = :failed, #error = :error, #updated_at = :now",
        ExpressionAttributeNames={
            "#status": "status",
            "#error": "error",
            "#updated_at": "updated_at",
        },
        ExpressionAttributeValues={
            ":failed": "failed",
            ":error": "Exceeded max retries (DLQ)",
            ":now": now,
        },
    )
    _send_webhook(job_id, "Legacy job exceeded max retries")


def _maybe_trigger_assembly(team_id: str, job_id: str) -> None:
    """Check if all tasks are done and invoke assembly if so."""
    job = _get_item(f"TEAM#{team_id}", f"JOB#{job_id}")
    if not job:
        return

    total = int(job.get("total_tasks", 0))
    processed = int(job.get("processed_count", 0))

    if total <= 0 or processed < total:
        return

    fanout_status = str(job.get("fanout_status", ""))
    if fanout_status != "running":
        return

    log.info("All tasks done (via DLQ): job=%s → invoking assembly", job_id)
    lambda_client.invoke(
        FunctionName=ASSEMBLY_FUNCTION_NAME,
        InvocationType="Event",
        Payload=json.dumps({
            "source": "dlq_processor",
            "teamId": team_id,
            "jobId": job_id,
        }).encode("utf-8"),
    )


def _get_item(pk: str, sk: str) -> Optional[Dict[str, Any]]:
    resp = ddb.get_item(Key={"pk": pk, "sk": sk})
    return resp.get("Item")


def _send_webhook(job_id: str, message: str) -> None:
    """Send Slack-compatible webhook with exponential backoff retry."""
    if not WEBHOOK_URL:
        return
    import urllib.request
    import urllib.error

    payload = json.dumps({"text": f"\u26a0\ufe0f *DLQ Alert*: {message} (`{job_id}`)"}).encode()

    for attempt in range(WEBHOOK_MAX_RETRIES):
        try:
            req = urllib.request.Request(
                WEBHOOK_URL, data=payload,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            return  # Success
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                log.warning("Webhook non-retryable HTTP %d for job=%s", e.code, job_id)
                return  # 4xx (except 429) are not retryable
            log.warning(
                "Webhook attempt %d/%d failed (HTTP %d) for job=%s",
                attempt + 1, WEBHOOK_MAX_RETRIES, e.code, job_id,
            )
        except Exception as e:
            log.warning(
                "Webhook attempt %d/%d failed for job=%s: %s",
                attempt + 1, WEBHOOK_MAX_RETRIES, job_id, e,
            )
        if attempt < WEBHOOK_MAX_RETRIES - 1:
            delay = min(2 ** attempt + random.uniform(0, 1), 10)
            time.sleep(delay)

    _emit_metric("WebhookDeliveryFailed", 1)
    log.error("Webhook delivery failed after %d attempts for job=%s", WEBHOOK_MAX_RETRIES, job_id)


def _emit_metric(
    name: str, value: float, *, team_id: str = "", unit: str = "Count",
) -> None:
    """Emit CloudWatch EMF (Embedded Metric Format) structured log."""
    dimensions: Dict[str, str] = {"Service": "MerryDLQProcessor"}
    if team_id:
        dimensions["TeamId"] = team_id
    emf = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": "Merry/DLQ",
                    "Dimensions": [list(dimensions.keys())],
                    "Metrics": [{"Name": name, "Unit": unit}],
                }
            ],
        },
        name: value,
        **dimensions,
    }
    print(json.dumps(emf))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
