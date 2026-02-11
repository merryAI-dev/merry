"""
SQS-driven analysis worker.

Responsibilities:
- Poll SQS for {teamId, jobId}
- Load job + input file metadata from DynamoDB (single-table)
- Download originals from S3 to project temp/
- Run the existing Python analysis tools (no algorithm changes)
- Upload result artifacts to S3
- Update job status + artifact pointers in DynamoDB
- Delete original uploads from S3 (security)
"""

from __future__ import annotations

import json
import math
import os
import time
import traceback
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMP_ROOT = PROJECT_ROOT / "temp"


def _env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    val = os.environ.get(name) or default or ""
    if required and not val:
        raise RuntimeError(f"Missing env {name}")
    return val


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _pk_team(team_id: str) -> str:
    return f"TEAM#{team_id}"


def _sk_job(job_id: str) -> str:
    return f"JOB#{job_id}"


def _sk_file(file_id: str) -> str:
    return f"FILE#{file_id}"


def _safe_filename(name: str) -> str:
    # Keep it simple and filesystem-safe.
    cleaned = "".join(c if c.isalnum() or c in ("-", "_", ".", " ") else "_" for c in (name or "file"))
    cleaned = cleaned.strip().strip(".")
    return cleaned[:160] or "file"


def _ddb_sanitize(value: Any) -> Any:
    """
    DynamoDB (boto3) does not accept Python float types.
    Recursively convert floats to Decimal and ensure maps/lists are serializable.
    """

    if value is None:
        return None
    if isinstance(value, (str, bool, int, Decimal)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        # Use string to avoid binary float issues (e.g., 0.1).
        return Decimal(str(value))
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            out[str(k)] = _ddb_sanitize(v)
        return out
    if isinstance(value, (list, tuple)):
        return [_ddb_sanitize(v) for v in value]
    return str(value)


class AwsCtx:
    def __init__(self) -> None:
        self.region = _env("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION"), required=True)
        self.ddb_table = _env("MERRY_DDB_TABLE", required=True)
        self.bucket = _env("MERRY_S3_BUCKET", required=True)
        self.queue_url = _env("MERRY_SQS_QUEUE_URL", required=True)
        self.delete_inputs = (_env("MERRY_DELETE_INPUTS", "true").lower() != "false")

        self._ddb = boto3.resource("dynamodb", region_name=self.region).Table(self.ddb_table)
        self._s3 = boto3.client("s3", region_name=self.region)
        self._sqs = boto3.client("sqs", region_name=self.region)

    @property
    def ddb(self):
        return self._ddb

    @property
    def s3(self):
        return self._s3

    @property
    def sqs(self):
        return self._sqs


def ddb_get_item(ctx: AwsCtx, pk: str, sk: str) -> Optional[Dict[str, Any]]:
    resp = ctx.ddb.get_item(Key={"pk": pk, "sk": sk})
    return resp.get("Item")


def ddb_update_job(
    ctx: AwsCtx,
    team_id: str,
    job_id: str,
    *,
    status: Optional[str] = None,
    error: Optional[str] = None,
    artifacts: Optional[List[Dict[str, Any]]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    usage: Optional[Dict[str, Any]] = None,
) -> None:
    pk = _pk_team(team_id)
    sk = _sk_job(job_id)

    exprs = []
    names: Dict[str, str] = {"#updated_at": "updated_at"}
    values: Dict[str, Any] = {":updated_at": _now_iso()}

    exprs.append("#updated_at = :updated_at")
    if status is not None:
        names["#status"] = "status"
        values[":status"] = status
        exprs.append("#status = :status")
    if error is not None:
        names["#error"] = "error"
        values[":error"] = error
        exprs.append("#error = :error")
    if artifacts is not None:
        names["#artifacts"] = "artifacts"
        values[":artifacts"] = _ddb_sanitize(artifacts)
        exprs.append("#artifacts = :artifacts")
    if metrics is not None:
        names["#metrics"] = "metrics"
        values[":metrics"] = _ddb_sanitize(metrics)
        exprs.append("#metrics = :metrics")
    if usage is not None:
        names["#usage"] = "usage"
        values[":usage"] = _ddb_sanitize(usage)
        exprs.append("#usage = :usage")

    # Final guard: ensure *all* ExpressionAttributeValues contain no Python floats.
    # This protects against any future fields added without explicit sanitization.
    values = _ddb_sanitize(values)

    ctx.ddb.update_item(
        Key={"pk": pk, "sk": sk},
        UpdateExpression="SET " + ", ".join(exprs),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def ddb_mark_file_deleted(ctx: AwsCtx, team_id: str, file_id: str) -> None:
    pk = _pk_team(team_id)
    sk = _sk_file(file_id)
    values = _ddb_sanitize({":deleted": "deleted", ":deleted_at": _now_iso()})
    ctx.ddb.update_item(
        Key={"pk": pk, "sk": sk},
        UpdateExpression="SET #status = :deleted, deleted_at = :deleted_at",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues=values,
    )


def s3_download(ctx: AwsCtx, bucket: str, key: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ctx.s3.download_file(bucket, key, str(dest))


def s3_upload(ctx: AwsCtx, bucket: str, key: str, src: Path, content_type: str) -> int:
    ctx.s3.upload_file(
        str(src),
        bucket,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return int(src.stat().st_size)


def s3_delete(ctx: AwsCtx, bucket: str, key: str) -> None:
    ctx.s3.delete_object(Bucket=bucket, Key=key)


def _job_temp_dir(team_id: str, job_id: str) -> Path:
    # Keep under repo temp/ to satisfy existing security validators.
    p = TEMP_ROOT / team_id / "jobs" / job_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _handle_exit_projection(input_path: Path, params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    from agent.tools.extraction_tools import execute_analyze_and_generate_projection

    def _to_int(v: Any) -> Optional[int]:
        if v is None:
            return None
        try:
            if isinstance(v, Decimal):
                return int(v)
            if isinstance(v, bool):
                return None
            if isinstance(v, (int,)):
                return int(v)
            if isinstance(v, float):
                if not math.isfinite(v):
                    return None
                return int(v)
            if isinstance(v, str) and v.strip():
                return int(float(v.strip()))
        except Exception:
            return None
        return None

    target_year = _to_int(params.get("targetYear") or params.get("target_year")) or 2030
    per_multiples = params.get("perMultiples") or params.get("per_multiples") or params.get("perMultiples")
    if not isinstance(per_multiples, list) or not per_multiples:
        per_multiples = [10, 20, 30]
    per = [float(x) for x in per_multiples]

    result = execute_analyze_and_generate_projection(
        excel_path=str(input_path),
        target_year=target_year,
        per_multiples=per,
        company_name=str(params.get("companyName") or params.get("company_name") or "").strip() or None,
        output_filename=f"exit_projection_{target_year}_{int(time.time())}.xlsx",
        investment_year=_to_int(params.get("investmentYear") or params.get("investment_year")),
        investment_amount=_to_int(params.get("investmentAmount") or params.get("investment_amount")),
        price_per_share=_to_int(params.get("pricePerShare") or params.get("price_per_share")),
        shares=_to_int(params.get("shares")),
        total_shares=_to_int(params.get("totalShares") or params.get("total_shares")),
        net_income=_to_int(params.get("netIncomeTargetYear") or params.get("net_income_target_year") or params.get("net_income")),
    )
    if not result.get("success"):
        raise RuntimeError(result.get("error") or "Exit projection failed")

    output_path = Path(str(result.get("output_file") or "")).resolve()
    if not output_path.exists():
        raise RuntimeError("Exit projection output missing")

    artifacts = [
        {
            "artifactId": "exit_projection_xlsx",
            "label": "Exit 프로젝션 (XLSX)",
            "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "localPath": str(output_path),
        }
    ]
    metrics = {"projection_summary": result.get("projection_summary"), "assumptions": result.get("assumptions")}
    return artifacts, metrics


def _handle_diagnosis(input_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    from agent.tools.diagnosis_tools import execute_analyze_company_diagnosis_sheet

    result = execute_analyze_company_diagnosis_sheet(str(input_path))
    if not result.get("success"):
        raise RuntimeError(result.get("error") or "Diagnosis analysis failed")

    out_path = input_path.parent / "diagnosis_result.json"
    _write_json(out_path, result)
    artifacts = [
        {
            "artifactId": "diagnosis_json",
            "label": "기업진단 분석 결과 (JSON)",
            "contentType": "application/json",
            "localPath": str(out_path),
        }
    ]
    metrics = {"page": None}
    return artifacts, metrics


def _handle_pdf_evidence(input_path: Path, params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    from agent.tools.underwriter_tools import execute_extract_pdf_market_evidence

    max_pages = int(params.get("maxPages") or 30)
    max_results = int(params.get("maxResults") or 20)
    result = execute_extract_pdf_market_evidence(
        pdf_path=str(input_path),
        max_pages=max_pages,
        max_results=max_results,
        keywords=None,
    )
    if not result.get("success"):
        raise RuntimeError(result.get("error") or "PDF evidence extraction failed")

    out_path = input_path.parent / "pdf_evidence.json"
    _write_json(out_path, result)
    artifacts = [
        {
            "artifactId": "pdf_evidence_json",
            "label": "PDF 근거 추출 결과 (JSON)",
            "contentType": "application/json",
            "localPath": str(out_path),
        }
    ]
    metrics = {"pages_read": result.get("pages_read"), "evidence_count": result.get("evidence_count")}
    return artifacts, metrics


def _handle_pdf_parse(input_path: Path, params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    from agent.tools.pdf_tools import execute_read_pdf_as_text

    max_pages = int(params.get("maxPages") or 30)
    output_mode = str(params.get("outputMode") or params.get("output_mode") or "structured").strip()
    if output_mode not in ("text_only", "structured", "tables_only"):
        output_mode = "structured"

    result = execute_read_pdf_as_text(
        pdf_path=str(input_path),
        max_pages=max_pages,
        output_mode=output_mode,
        extract_financial_tables=True,
    )
    if not result.get("success"):
        raise RuntimeError(result.get("error") or "PDF parse failed")

    out_path = input_path.parent / "pdf_parse.json"
    _write_json(out_path, result)
    artifacts = [
        {
            "artifactId": "pdf_parse_json",
            "label": "PDF 파싱 결과 (JSON)",
            "contentType": "application/json",
            "localPath": str(out_path),
        }
    ]

    metrics: Dict[str, Any] = {
        "doc_type": result.get("doc_type"),
        "pages_read": result.get("pages_read"),
        "total_pages": result.get("total_pages"),
        "processing_method": result.get("processing_method"),
        "processing_time_seconds": result.get("processing_time_seconds"),
        "output_mode": output_mode,
    }

    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    model = result.get("model") if isinstance(result.get("model"), str) else ""
    provider = result.get("provider") if isinstance(result.get("provider"), str) else ""
    if usage or model or provider:
        llm = {**usage}
        if model:
            llm["model"] = model
        if provider:
            llm["provider"] = provider
        metrics["llm"] = llm

    return artifacts, metrics


def _handle_contract_review_single(input_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    raise NotImplementedError("Use _handle_contract_review instead")


def _handle_contract_review(
    input_paths: List[Path], params: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Contract review job.

    - Supports 1 or 2 documents:
      - [0] Term Sheet
      - [1] Investment agreement (optional)
    - Keeps the existing extraction/compare logic in shared.contract_review.
    - OCR is OFF by default (can be enabled later via params).
    """

    from shared.contract_review import (
        build_review_opinion,
        compare_fields,
        detect_clauses,
        extract_fields,
        load_document,
    )

    raw_mode = params.get("ocrMode") or params.get("ocr_mode") or "off"
    ocr_mode = str(raw_mode).strip().lower() if raw_mode is not None else "off"
    if ocr_mode not in ("off", "auto", "force"):
        ocr_mode = "off"

    def _parse(path: Path, doc_type: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        loaded = load_document(Path(path), ocr_mode=ocr_mode, api_key="")
        segments = loaded.get("segments", [])
        fields = extract_fields(segments)
        clauses = detect_clauses(segments, doc_type, loaded.get("segment_scores", {}))
        doc: Dict[str, Any] = {
            "name": path.name,
            "doc_type": doc_type,
            "fields": fields,
            "clauses": clauses,
            "page_count": loaded.get("page_count", 0),
            "ocr_used": loaded.get("ocr_used", False),
            "ocr_error": loaded.get("ocr_error", ""),
            "ocr_engine": loaded.get("ocr_engine", ""),
            "priority_segments": loaded.get("priority_segments", []),
        }
        return doc, loaded

    term_doc: Optional[Dict[str, Any]] = None
    invest_doc: Optional[Dict[str, Any]] = None
    term_loaded: Dict[str, Any] = {}
    invest_loaded: Dict[str, Any] = {}

    if input_paths:
        term_doc, term_loaded = _parse(input_paths[0], "term_sheet")
    if len(input_paths) >= 2:
        invest_doc, invest_loaded = _parse(input_paths[1], "investment_agreement")

    comparisons: List[Dict[str, Any]] = []
    if term_doc and invest_doc:
        comparisons = compare_fields(term_doc.get("fields", {}), invest_doc.get("fields", {}))

    opinion = build_review_opinion(term_doc, invest_doc, comparisons)
    out: Dict[str, Any] = {
        "term_sheet": term_doc,
        "investment_agreement": invest_doc,
        "comparisons": comparisons,
        "opinion": opinion,
        "ocr_mode": ocr_mode,
    }

    out_path = input_paths[0].parent / "contract_review.json"
    _write_json(out_path, out)

    artifacts = [
        {
            "artifactId": "contract_review_json",
            "label": "계약서 검토 결과 (JSON)",
            "contentType": "application/json",
            "localPath": str(out_path),
        }
    ]
    metrics = {
        "term_sheet_pages": term_loaded.get("page_count", 0) if term_loaded else 0,
        "investment_pages": invest_loaded.get("page_count", 0) if invest_loaded else 0,
        "comparison_count": len(comparisons),
        "ocr_mode": ocr_mode,
    }
    return artifacts, metrics


def process_job(ctx: AwsCtx, team_id: str, job_id: str) -> None:
    started = time.time()
    started_at = _now_iso()
    ddb_update_job(ctx, team_id, job_id, status="running", metrics={"started_at": started_at})

    job = ddb_get_item(ctx, _pk_team(team_id), _sk_job(job_id)) or {}
    job_type = str(job.get("type") or "")
    params = job.get("params") if isinstance(job.get("params"), dict) else {}
    file_ids = job.get("input_file_ids") if isinstance(job.get("input_file_ids"), list) else []
    file_ids = [str(x) for x in file_ids if x]
    if not file_ids:
        raise RuntimeError("Job has no inputs")

    job_dir = _job_temp_dir(team_id, job_id)
    input_dir = job_dir / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)

    # Download all inputs.
    file_rows: List[Dict[str, Any]] = []
    local_inputs: List[Path] = []
    for file_id in file_ids:
        row = ddb_get_item(ctx, _pk_team(team_id), _sk_file(file_id))
        if not row:
            raise RuntimeError(f"Missing file metadata: {file_id}")
        file_rows.append(row)

        key = str(row.get("s3_key") or "")
        bucket = str(row.get("s3_bucket") or ctx.bucket)
        original = str(row.get("original_name") or file_id)
        ext = Path(key).suffix or Path(original).suffix
        dest = input_dir / f"{file_id}{ext}"
        s3_download(ctx, bucket, key, dest)
        local_inputs.append(dest)

    artifacts: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {"started_at": started_at}

    # Dispatch.
    if job_type == "exit_projection":
        artifacts, extra = _handle_exit_projection(local_inputs[0], params)
        metrics.update(extra)
    elif job_type == "diagnosis_analysis":
        artifacts, extra = _handle_diagnosis(local_inputs[0])
        metrics.update(extra)
    elif job_type == "pdf_evidence":
        artifacts, extra = _handle_pdf_evidence(local_inputs[0], params)
        metrics.update(extra)
    elif job_type == "pdf_parse":
        artifacts, extra = _handle_pdf_parse(local_inputs[0], params)
        metrics.update(extra)
    elif job_type == "contract_review":
        artifacts, extra = _handle_contract_review(local_inputs[:2], params)
        metrics.update(extra)
    else:
        raise RuntimeError(f"Unsupported job type: {job_type}")

    # Upload artifacts.
    uploaded: List[Dict[str, Any]] = []
    total_out = 0
    for a in artifacts:
        local_path = Path(str(a.get("localPath") or ""))
        if not local_path.exists():
            continue
        artifact_id = str(a.get("artifactId") or _safe_filename(local_path.name))
        label = str(a.get("label") or local_path.name)
        content_type = str(a.get("contentType") or "application/octet-stream")
        dest_key = f"artifacts/{team_id}/{job_id}/{artifact_id}{local_path.suffix}"
        size = s3_upload(ctx, ctx.bucket, dest_key, local_path, content_type)
        total_out += size
        uploaded.append(
            {
                "artifactId": artifact_id,
                "label": label,
                "contentType": content_type,
                "s3Bucket": ctx.bucket,
                "s3Key": dest_key,
                "sizeBytes": size,
            }
        )

    # Delete originals after processing (security).
    deleted_inputs = []
    if ctx.delete_inputs:
        for row in file_rows:
            bucket = str(row.get("s3_bucket") or ctx.bucket)
            key = str(row.get("s3_key") or "")
            file_id = str(row.get("file_id") or "")
            if not key or not file_id:
                continue
            try:
                s3_delete(ctx, bucket, key)
                ddb_mark_file_deleted(ctx, team_id, file_id)
                deleted_inputs.append(file_id)
            except Exception:
                # Best-effort. Lifecycle rule can still clean up.
                pass

    ended_at = _now_iso()
    duration_ms = int((time.time() - started) * 1000)
    metrics.update(
        {
            "ended_at": ended_at,
            "duration_ms": duration_ms,
            "artifacts_bytes": total_out,
            "deleted_inputs": deleted_inputs,
        }
    )

    usage = metrics.get("llm") if isinstance(metrics.get("llm"), dict) else None
    ddb_update_job(
        ctx,
        team_id,
        job_id,
        status="succeeded",
        error="",
        artifacts=uploaded,
        metrics=metrics,
        usage=usage,
    )


def worker_loop() -> None:
    ctx = AwsCtx()
    print(f"[worker] region={ctx.region} table={ctx.ddb_table} bucket={ctx.bucket}")

    while True:
        resp = ctx.sqs.receive_message(
            QueueUrl=ctx.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=900,
        )
        msgs = resp.get("Messages") or []
        if not msgs:
            continue

        msg = msgs[0]
        receipt = msg.get("ReceiptHandle")
        body_raw = msg.get("Body") or ""

        try:
            payload = json.loads(body_raw)
            team_id = str(payload.get("teamId") or "")
            job_id = str(payload.get("jobId") or "")
            if not team_id or not job_id:
                raise ValueError("Missing teamId/jobId")

            try:
                process_job(ctx, team_id, job_id)
            except Exception as exc:
                ended_at = _now_iso()
                err_text = f"{type(exc).__name__}: {exc}"
                ddb_update_job(
                    ctx,
                    team_id,
                    job_id,
                    status="failed",
                    error=err_text,
                    metrics={
                        "ended_at": ended_at,
                        "traceback": traceback.format_exc(limit=20),
                    },
                )
        except Exception:
            # Bad message; drop it.
            pass
        finally:
            if receipt:
                ctx.sqs.delete_message(QueueUrl=ctx.queue_url, ReceiptHandle=receipt)


if __name__ == "__main__":
    worker_loop()
