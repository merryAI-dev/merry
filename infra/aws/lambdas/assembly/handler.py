"""
Assembly Lambda: Aggregate fan-out task results into final artifacts.

Invoked by: Stream Processor Lambda (async) or DLQ Processor Lambda.

Steps:
1. Conditional write: fanout_status running → assembling (idempotent guard).
2. Query all TASK records for the job.
3. Parse task results, build CSV + JSON.
4. Upload artifacts to S3.
5. (Optional) Delete input files from S3.
6. Mark JOB as succeeded with artifact metadata.

If assembly fails, marks JOB as failed so it doesn't hang in "assembling".
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import random
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3
from boto3.dynamodb.conditions import Key

log = logging.getLogger()
log.setLevel(logging.INFO)

DDB_TABLE_NAME = os.environ.get("MERRY_DDB_TABLE", "merry-main")
S3_BUCKET = os.environ.get("MERRY_S3_BUCKET", "")
DELETE_INPUTS = os.environ.get("MERRY_DELETE_INPUTS", "true").lower() != "false"
WEBHOOK_URL = os.environ.get("MERRY_WEBHOOK_URL", "")
WEBHOOK_MAX_RETRIES = int(os.environ.get("MERRY_WEBHOOK_MAX_RETRIES", "3"))

ddb = boto3.resource("dynamodb").Table(DDB_TABLE_NAME)
s3 = boto3.client("s3")


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    team_id = event.get("teamId", "")
    job_id = event.get("jobId", "")
    source = event.get("source", "unknown")

    if not team_id or not job_id:
        log.error("Missing teamId or jobId in event: %s", json.dumps(event))
        return {"error": "MISSING_PARAMS"}

    log.info("Assembly start: team=%s job=%s source=%s", team_id, job_id, source)

    # 1. Try to claim assembly (idempotent).
    if not _try_claim_assembly(team_id, job_id):
        log.info("Assembly already claimed or not in running state: %s", job_id)
        return {"status": "ALREADY_CLAIMED"}

    try:
        # 2. Load job record.
        job = _get_item(f"TEAM#{team_id}", f"JOB#{job_id}")
        if not job:
            raise RuntimeError(f"Job not found: {job_id}")

        job_type = str(job.get("type", ""))
        params = job.get("params", {}) if isinstance(job.get("params"), dict) else {}
        conditions: List[str] = [str(c) for c in (params.get("conditions") or []) if c]

        # 3. Query all tasks.
        tasks = _query_all_tasks(team_id, job_id)
        tasks.sort(key=lambda t: str(t.get("sk", "")))

        # 4. Parse results.
        rows: List[Dict[str, Any]] = []
        for task in tasks:
            result_raw = task.get("result")
            if isinstance(result_raw, str):
                try:
                    result_data = json.loads(result_raw)
                except json.JSONDecodeError:
                    result_data = {"filename": str(task.get("file_id", "")), "error": result_raw}
            elif isinstance(result_raw, dict):
                result_data = result_raw
            else:
                result_data = {
                    "filename": str(task.get("file_id", "")),
                    "error": str(task.get("error", "unknown")),
                }
            rows.append(result_data)

        # 5. Build artifacts.
        uploaded: List[Dict[str, Any]] = []
        total_bytes = 0

        # Artifact labels by job type.
        _labels = {
            "condition_check": ("조건 검사 결과", "condition_check"),
            "document_extraction": ("문서 추출 결과", "document_extraction"),
        }
        label_prefix, artifact_prefix = _labels.get(job_type, ("결과", "results"))

        with tempfile.TemporaryDirectory() as tmpdir:
            if job_type == "condition_check" and conditions:
                csv_path, json_path = _build_condition_check_csv(
                    Path(tmpdir), rows, conditions
                )
                # Upload CSV.
                if csv_path.exists():
                    dest_key = f"artifacts/{team_id}/{job_id}/{artifact_prefix}_csv.csv"
                    size = _s3_upload(dest_key, csv_path, "text/csv")
                    total_bytes += size
                    uploaded.append({
                        "artifactId": f"{artifact_prefix}_csv",
                        "label": f"{label_prefix} (CSV)",
                        "contentType": "text/csv",
                        "s3Bucket": S3_BUCKET,
                        "s3Key": dest_key,
                        "sizeBytes": size,
                    })
                # Upload JSON.
                if json_path.exists():
                    dest_key = f"artifacts/{team_id}/{job_id}/{artifact_prefix}_json.json"
                    size = _s3_upload(dest_key, json_path, "application/json")
                    total_bytes += size
                    uploaded.append({
                        "artifactId": f"{artifact_prefix}_json",
                        "label": f"{label_prefix} (JSON)",
                        "contentType": "application/json",
                        "s3Bucket": S3_BUCKET,
                        "s3Key": dest_key,
                        "sizeBytes": size,
                    })
            else:
                # Generic JSON output.
                json_path = Path(tmpdir) / "results.json"
                json_path.write_text(
                    json.dumps({"total": len(rows), "results": rows}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                dest_key = f"artifacts/{team_id}/{job_id}/{artifact_prefix}_json.json"
                size = _s3_upload(dest_key, json_path, "application/json")
                total_bytes += size
                uploaded.append({
                    "artifactId": f"{artifact_prefix}_json",
                    "label": f"{label_prefix} (JSON)",
                    "contentType": "application/json",
                    "s3Bucket": S3_BUCKET,
                    "s3Key": dest_key,
                    "sizeBytes": size,
                })

        # 6. Delete input files (security).
        deleted_inputs: List[str] = []
        if DELETE_INPUTS:
            file_ids = job.get("input_file_ids", [])
            if isinstance(file_ids, list):
                for fid in file_ids:
                    fid = str(fid)
                    if not fid:
                        continue
                    try:
                        row = _get_item(f"TEAM#{team_id}", f"FILE#{fid}")
                        if row:
                            bucket = str(row.get("s3_bucket") or S3_BUCKET)
                            key = str(row.get("s3_key") or "")
                            if key:
                                s3.delete_object(Bucket=bucket, Key=key)
                                _mark_file_deleted(team_id, fid)
                                deleted_inputs.append(fid)
                    except Exception:
                        pass  # Best-effort.

        # 7. Finalize job.
        success_count = sum(1 for r in rows if "error" not in r)
        now = _now_iso()

        # Aggregate token usage across all tasks.
        total_input_tokens = 0
        total_output_tokens = 0
        for r in rows:
            tu = r.get("token_usage") if isinstance(r.get("token_usage"), dict) else {}
            total_input_tokens += int(tu.get("input_tokens", 0))
            total_output_tokens += int(tu.get("output_tokens", 0))

        metrics = {
            "total": len(rows),
            "success_count": success_count,
            "failed_count": len(rows) - success_count,
            "conditions": conditions,
            "artifacts_bytes": total_bytes,
            "deleted_inputs": deleted_inputs,
            "ended_at": now,
            "assembled_by": "lambda",
            "token_usage": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
            },
        }

        ddb.update_item(
            Key={"pk": f"TEAM#{team_id}", "sk": f"JOB#{job_id}"},
            UpdateExpression=(
                "SET #status = :status, #fs = :fs, #artifacts = :artifacts, "
                "#metrics = :metrics, #error = :error, #updated_at = :now"
            ),
            ExpressionAttributeNames={
                "#status": "status",
                "#fs": "fanout_status",
                "#artifacts": "artifacts",
                "#metrics": "metrics",
                "#error": "error",
                "#updated_at": "updated_at",
            },
            ExpressionAttributeValues={
                ":status": "succeeded",
                ":fs": "succeeded",
                ":artifacts": uploaded,
                ":metrics": _sanitize(metrics),
                ":error": "",
                ":now": now,
            },
        )

        log.info(
            "Assembly complete: job=%s artifacts=%d success=%d failed=%d",
            job_id, len(uploaded), success_count, len(rows) - success_count,
        )
        job_title = str(job.get("title") or job_type)
        _send_webhook(
            job_id, job_title, "succeeded",
            total=len(rows), success=success_count, failed=len(rows) - success_count,
        )
        return {"status": "OK", "artifacts": len(uploaded)}

    except Exception as exc:
        log.error("Assembly failed for job=%s: %s", job_id, exc, exc_info=True)
        now = _now_iso()
        try:
            ddb.update_item(
                Key={"pk": f"TEAM#{team_id}", "sk": f"JOB#{job_id}"},
                UpdateExpression="SET #status = :failed, #fs = :failed, #error = :error, #updated_at = :now",
                ExpressionAttributeNames={
                    "#status": "status",
                    "#fs": "fanout_status",
                    "#error": "error",
                    "#updated_at": "updated_at",
                },
                ExpressionAttributeValues={
                    ":failed": "failed",
                    ":error": f"Assembly error: {exc}",
                    ":now": now,
                },
            )
        except Exception:
            log.error("Failed to mark job as failed", exc_info=True)
        _send_webhook(job_id, f"Job {job_id}", "failed", error=str(exc))
        return {"status": "ERROR", "error": str(exc)}


# ── Helpers ──


def _send_webhook(
    job_id: str, title: str, status: str,
    *, total: int = 0, success: int = 0, failed: int = 0, error: str = "",
) -> None:
    """Send Slack-compatible webhook with exponential backoff retry."""
    if not WEBHOOK_URL:
        return
    import urllib.request
    import urllib.error

    emoji = "\u2705" if status == "succeeded" else "\u274c"
    lines = [f"{emoji} *Job {status}*: {title} (`{job_id}`)"]
    if total > 0:
        lines.append(f"  Total: {total} | Success: {success} | Failed: {failed}")
    if error:
        lines.append(f"  Error: {error[:200]}")
    payload_bytes = json.dumps({"text": "\n".join(lines)}).encode()

    for attempt in range(WEBHOOK_MAX_RETRIES):
        try:
            req = urllib.request.Request(
                WEBHOOK_URL, data=payload_bytes,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            return  # Success
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                log.warning("Webhook non-retryable HTTP %d for job=%s", e.code, job_id)
                return
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

    log.error("Webhook delivery failed after %d attempts for job=%s", WEBHOOK_MAX_RETRIES, job_id)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_item(pk: str, sk: str) -> Optional[Dict[str, Any]]:
    resp = ddb.get_item(Key={"pk": pk, "sk": sk})
    return resp.get("Item")


def _try_claim_assembly(team_id: str, job_id: str) -> bool:
    """Conditional write: fanout_status running → assembling."""
    try:
        ddb.update_item(
            Key={"pk": f"TEAM#{team_id}", "sk": f"JOB#{job_id}"},
            UpdateExpression="SET #fs = :assembling, #updated_at = :now",
            ConditionExpression="#fs = :running",
            ExpressionAttributeNames={
                "#fs": "fanout_status",
                "#updated_at": "updated_at",
            },
            ExpressionAttributeValues={
                ":running": "running",
                ":assembling": "assembling",
                ":now": _now_iso(),
            },
        )
        return True
    except ddb.meta.client.exceptions.ConditionalCheckFailedException:
        return False


def _query_all_tasks(team_id: str, job_id: str) -> List[Dict[str, Any]]:
    """Query all TASK records for a job."""
    pk = f"TEAM#{team_id}"
    sk_prefix = f"TASK#{job_id}#"
    items: List[Dict[str, Any]] = []
    kwargs: Dict[str, Any] = {
        "KeyConditionExpression": Key("pk").eq(pk) & Key("sk").begins_with(sk_prefix),
    }
    while True:
        resp = ddb.query(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items


def _mark_file_deleted(team_id: str, file_id: str) -> None:
    now = _now_iso()
    ddb.update_item(
        Key={"pk": f"TEAM#{team_id}", "sk": f"FILE#{file_id}"},
        UpdateExpression="SET #status = :deleted, deleted_at = :now",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":deleted": "deleted", ":now": now},
    )


def _s3_upload(key: str, local_path: Path, content_type: str) -> int:
    s3.upload_file(
        str(local_path), S3_BUCKET, key,
        ExtraArgs={"ContentType": content_type},
    )
    return int(local_path.stat().st_size)


def _sanitize(value: Any) -> Any:
    """Recursively sanitize for DynamoDB (float → Decimal-safe string)."""
    from decimal import Decimal
    import math

    if value is None:
        return None
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return Decimal(str(value))
    if isinstance(value, dict):
        return {str(k): _sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    return str(value)


def _build_condition_check_csv(
    output_dir: Path,
    rows: List[Dict[str, Any]],
    conditions: List[str],
) -> Tuple[Path, Path]:
    """Build CSV and JSON files from condition check results."""
    buf = io.StringIO()
    fieldnames = ["filename", "company_name", "method", "pages", "elapsed_s", "error"]
    for c in conditions:
        short = c[:30].replace(" ", "_")
        fieldnames += [f"{short}_result", f"{short}_evidence"]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        row: Dict[str, Any] = {
            k: r.get(k, "") for k in ["filename", "company_name", "method", "pages", "elapsed_s", "error"]
        }
        cond_results = r.get("conditions") or []
        for j, c in enumerate(conditions):
            short = c[:30].replace(" ", "_")
            if j < len(cond_results):
                cr = cond_results[j]
                row[f"{short}_result"] = "\u2713" if cr.get("result") else "\u2717"
                row[f"{short}_evidence"] = cr.get("evidence", "")
            else:
                row[f"{short}_result"] = ""
                row[f"{short}_evidence"] = ""
        writer.writerow(row)

    csv_path = output_dir / "condition_check_results.csv"
    csv_path.write_text(buf.getvalue(), encoding="utf-8-sig")

    json_path = output_dir / "condition_check_results.json"
    json_path.write_text(
        json.dumps({"conditions": conditions, "total": len(rows), "results": rows},
                    ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return csv_path, json_path
