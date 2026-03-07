"""
DynamoDB Streams → Completion Detector → Assembly Lambda Invoker.

Trigger: DynamoDB Streams (MODIFY events on JOB entities with fanout=true).

When processed_count + failed_count reaches total_tasks AND fanout_status
is still "running", this function invokes the Assembly Lambda asynchronously.

Design:
- Filters: only JOB entities (sk starts with "JOB#"), fanout=true.
- Compares OLD vs NEW image to detect counter changes.
- Invokes assembly ONLY when the new counts first reach total (debounce).
- Idempotent: Assembly Lambda itself has a conditional write guard.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

import boto3

log = logging.getLogger()
log.setLevel(logging.INFO)

ASSEMBLY_FUNCTION_NAME = os.environ.get("ASSEMBLY_FUNCTION_NAME", "merry-assembly")
lambda_client = boto3.client("lambda")


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    records = event.get("Records", [])
    invoked = 0

    for record in records:
        if record.get("eventName") != "MODIFY":
            continue

        new_image = record.get("dynamodb", {}).get("NewImage", {})
        old_image = record.get("dynamodb", {}).get("OldImage", {})

        # Filter: only JOB entities.
        sk = _ddb_str(new_image.get("sk"))
        if not sk or not sk.startswith("JOB#"):
            continue

        # Filter: only fan-out jobs.
        fanout = _ddb_bool(new_image.get("fanout"))
        if not fanout:
            continue

        # Filter: fanout_status must be "running".
        fanout_status = _ddb_str(new_image.get("fanout_status"))
        if fanout_status != "running":
            continue

        total = _ddb_int(new_image.get("total_tasks"))
        processed = _ddb_int(new_image.get("processed_count"))
        failed = _ddb_int(new_image.get("failed_count"))
        old_processed = _ddb_int(old_image.get("processed_count"))
        old_failed = _ddb_int(old_image.get("failed_count"))

        if total <= 0:
            continue

        new_done = processed + failed
        old_done = old_processed + old_failed

        # Only trigger when we JUST crossed the completion threshold.
        if new_done >= total and old_done < total:
            team_id = _ddb_str(new_image.get("team_id"))
            job_id = sk.removeprefix("JOB#")
            pk = _ddb_str(new_image.get("pk"))
            if not team_id:
                # Extract from pk: "TEAM#{teamId}"
                team_id = pk.removeprefix("TEAM#") if pk else ""

            if not team_id or not job_id:
                log.warning("Missing team_id or job_id, skipping: pk=%s sk=%s", pk, sk)
                continue

            log.info(
                "All tasks complete: team=%s job=%s total=%d processed=%d failed=%d → invoking assembly",
                team_id, job_id, total, processed, failed,
            )

            payload = json.dumps({
                "source": "stream_processor",
                "teamId": team_id,
                "jobId": job_id,
            })

            lambda_client.invoke(
                FunctionName=ASSEMBLY_FUNCTION_NAME,
                InvocationType="Event",  # Async invocation.
                Payload=payload.encode("utf-8"),
            )
            invoked += 1

    return {"processed": len(records), "invoked": invoked}


def _ddb_str(attr: Any) -> str:
    """Extract string from DynamoDB attribute."""
    if attr is None:
        return ""
    if isinstance(attr, dict):
        return str(attr.get("S", ""))
    return str(attr)


def _ddb_int(attr: Any) -> int:
    """Extract integer from DynamoDB attribute."""
    if attr is None:
        return 0
    if isinstance(attr, dict):
        return int(attr.get("N", 0))
    try:
        return int(attr)
    except (ValueError, TypeError):
        return 0


def _ddb_bool(attr: Any) -> bool:
    """Extract boolean from DynamoDB attribute."""
    if attr is None:
        return False
    if isinstance(attr, dict):
        return attr.get("BOOL", False)
    return bool(attr)
