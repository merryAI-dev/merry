"""
Worker pipeline smoke tests (no real AWS).

These tests validate that:
- DynamoDB item shapes match what the Next.js API writes (pk/sk + key fields)
- The worker orchestrates: download -> analyze -> upload artifact -> update job -> delete originals

We intentionally use in-memory fakes instead of moto/localstack to keep the loop fast and deterministic.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from worker.main import process_job  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class FakeDdbTable:
    def __init__(self) -> None:
        self.items: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def get_item(self, Key: Dict[str, Any]) -> Dict[str, Any]:
        item = self.items.get((Key["pk"], Key["sk"]))
        return {"Item": item} if item else {}

    def update_item(
        self,
        *,
        Key: Dict[str, Any],
        UpdateExpression: str,
        ExpressionAttributeNames: Dict[str, str] | None = None,
        ExpressionAttributeValues: Dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> None:
        pk = Key["pk"]
        sk = Key["sk"]
        item = dict(self.items.get((pk, sk), {"pk": pk, "sk": sk}))

        names = ExpressionAttributeNames or {}
        values = ExpressionAttributeValues or {}

        expr = (UpdateExpression or "").strip()
        assert expr.startswith("SET "), f"Unsupported UpdateExpression: {expr}"
        assigns = [p.strip() for p in expr[len("SET ") :].split(",") if p.strip()]

        for assign in assigns:
            lhs, rhs = [s.strip() for s in assign.split("=", 1)]
            if lhs.startswith("#"):
                lhs = names[lhs]
            if rhs.startswith(":"):
                item[lhs] = values[rhs]
            else:
                # Not expected in our worker update expressions.
                item[lhs] = rhs

        self.items[(pk, sk)] = item

    def put(self, item: Dict[str, Any]) -> None:
        self.items[(item["pk"], item["sk"])] = dict(item)


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: Dict[Tuple[str, str], bytes] = {}

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        data = self.objects[(bucket, key)]
        p = Path(filename)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def upload_file(self, filename: str, bucket: str, key: str, ExtraArgs: Dict[str, Any] | None = None) -> None:  # noqa: N803
        _ = ExtraArgs
        self.objects[(bucket, key)] = Path(filename).read_bytes()

    def delete_object(self, *, Bucket: str, Key: str) -> None:  # noqa: N803
        self.objects.pop((Bucket, Key), None)


class FakeCtx:
    def __init__(self, *, bucket: str, delete_inputs: bool) -> None:
        self.bucket = bucket
        self.delete_inputs = delete_inputs
        self._ddb = FakeDdbTable()
        self._s3 = FakeS3Client()

    @property
    def ddb(self) -> FakeDdbTable:
        return self._ddb

    @property
    def s3(self) -> FakeS3Client:
        return self._s3

    @property
    def sqs(self):
        raise RuntimeError("SQS not used in these unit tests")


def _pk_team(team_id: str) -> str:
    return f"TEAM#{team_id}"


def _sk_job(job_id: str) -> str:
    return f"JOB#{job_id}"


def _sk_file(file_id: str) -> str:
    return f"FILE#{file_id}"


def put_file(ctx: FakeCtx, *, team_id: str, file_id: str, bucket: str, key: str, original_name: str) -> None:
    ctx.ddb.put(
        {
            "pk": _pk_team(team_id),
            "sk": _sk_file(file_id),
            "entity": "file",
            "file_id": file_id,
            "team_id": team_id,
            "status": "uploaded",
            "original_name": original_name,
            "content_type": "application/octet-stream",
            "size_bytes": 0,
            "s3_bucket": bucket,
            "s3_key": key,
            "created_by": "tester",
            "created_at": "2026-02-09T00:00:00Z",
            "uploaded_at": "2026-02-09T00:00:00Z",
            "deleted_at": "",
        }
    )


def put_job(
    ctx: FakeCtx,
    *,
    team_id: str,
    job_id: str,
    job_type: str,
    file_ids: list[str],
    params: Dict[str, Any] | None = None,
) -> None:
    ctx.ddb.put(
        {
            "pk": _pk_team(team_id),
            "sk": _sk_job(job_id),
            "entity": "job",
            "job_id": job_id,
            "team_id": team_id,
            "type": job_type,
            "status": "queued",
            "title": "test",
            "created_by": "tester",
            "created_at": "2026-02-09T00:00:00Z",
            "updated_at": "2026-02-09T00:00:00Z",
            "input_file_ids": file_ids,
            "params": params or {},
            "error": "",
            "artifacts": [],
            "metrics": {},
            "usage": {},
        }
    )


def make_docx_bytes(lines: list[str]) -> bytes:
    from docx import Document

    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_pdf_bytes(text: str) -> bytes:
    import fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    # Prefer in-memory write (no filesystem dependency).
    if hasattr(doc, "tobytes"):
        data = doc.tobytes()
    else:
        data = doc.write()  # type: ignore[attr-defined]
    doc.close()
    return data


def cleanup_job_dir(team_id: str, job_id: str) -> None:
    p = PROJECT_ROOT / "temp" / team_id / "jobs" / job_id
    shutil.rmtree(p, ignore_errors=True)


@pytest.fixture(autouse=True)
def _cleanup():
    # Ensure tests don't accumulate temp files across repeated runs.
    yield


def test_contract_review_two_docs_updates_job_and_deletes_inputs():
    team_id = "team_1"
    job_id = "job_contract_2"
    bucket = "merry-test"

    ctx = FakeCtx(bucket=bucket, delete_inputs=True)

    term_id = "file_term"
    inv_id = "file_inv"
    term_key = f"uploads/{team_id}/{term_id}.docx"
    inv_key = f"uploads/{team_id}/{inv_id}.docx"

    ctx.s3.objects[(bucket, term_key)] = make_docx_bytes(["투자금액: 5억", "Pre-Money: 50억"])
    ctx.s3.objects[(bucket, inv_key)] = make_docx_bytes(["투자금액: 6억", "Pre-Money: 50억"])

    put_file(ctx, team_id=team_id, file_id=term_id, bucket=bucket, key=term_key, original_name="term.docx")
    put_file(ctx, team_id=team_id, file_id=inv_id, bucket=bucket, key=inv_key, original_name="investment.docx")
    put_job(ctx, team_id=team_id, job_id=job_id, job_type="contract_review", file_ids=[term_id, inv_id], params={})

    try:
        process_job(ctx, team_id, job_id)
        job = ctx.ddb.get_item(Key={"pk": _pk_team(team_id), "sk": _sk_job(job_id)})["Item"]
        assert job["status"] == "succeeded"
        assert isinstance(job.get("artifacts"), list) and len(job["artifacts"]) == 1

        artifact = job["artifacts"][0]
        assert artifact["artifactId"] == "contract_review_json"
        assert artifact["s3Bucket"] == bucket
        assert artifact["s3Key"].startswith(f"artifacts/{team_id}/{job_id}/contract_review_json")

        # Artifact content should include both docs + comparisons.
        payload = json.loads(ctx.s3.objects[(bucket, artifact["s3Key"])].decode("utf-8"))
        assert payload["term_sheet"]["doc_type"] == "term_sheet"
        assert payload["investment_agreement"]["doc_type"] == "investment_agreement"
        assert isinstance(payload["comparisons"], list) and len(payload["comparisons"]) > 0

        # Originals are deleted.
        assert (bucket, term_key) not in ctx.s3.objects
        assert (bucket, inv_key) not in ctx.s3.objects

        f1 = ctx.ddb.get_item(Key={"pk": _pk_team(team_id), "sk": _sk_file(term_id)})["Item"]
        f2 = ctx.ddb.get_item(Key={"pk": _pk_team(team_id), "sk": _sk_file(inv_id)})["Item"]
        assert f1["status"] == "deleted"
        assert f2["status"] == "deleted"
        assert f1.get("deleted_at")
        assert f2.get("deleted_at")
    finally:
        cleanup_job_dir(team_id, job_id)


def test_contract_review_single_doc_succeeds_and_has_no_comparisons():
    team_id = "team_1"
    job_id = "job_contract_1"
    bucket = "merry-test"
    ctx = FakeCtx(bucket=bucket, delete_inputs=False)

    term_id = "file_term_single"
    term_key = f"uploads/{team_id}/{term_id}.docx"
    ctx.s3.objects[(bucket, term_key)] = make_docx_bytes(["투자금액: 5억", "준거법: 대한민국"])

    put_file(ctx, team_id=team_id, file_id=term_id, bucket=bucket, key=term_key, original_name="term.docx")
    put_job(ctx, team_id=team_id, job_id=job_id, job_type="contract_review", file_ids=[term_id], params={})

    try:
        process_job(ctx, team_id, job_id)
        job = ctx.ddb.get_item(Key={"pk": _pk_team(team_id), "sk": _sk_job(job_id)})["Item"]
        assert job["status"] == "succeeded"
        artifact = job["artifacts"][0]
        payload = json.loads(ctx.s3.objects[(bucket, artifact["s3Key"])].decode("utf-8"))
        assert payload["term_sheet"] is not None
        assert payload["investment_agreement"] is None
        assert payload["comparisons"] == []

        # Originals preserved.
        assert (bucket, term_key) in ctx.s3.objects
        f1 = ctx.ddb.get_item(Key={"pk": _pk_team(team_id), "sk": _sk_file(term_id)})["Item"]
        assert f1["status"] == "uploaded"
    finally:
        cleanup_job_dir(team_id, job_id)


def test_pdf_evidence_succeeds_and_emits_json_artifact():
    team_id = "team_1"
    job_id = "job_pdf_evidence"
    bucket = "merry-test"
    ctx = FakeCtx(bucket=bucket, delete_inputs=True)

    file_id = "file_pdf"
    key = f"uploads/{team_id}/{file_id}.pdf"
    ctx.s3.objects[(bucket, key)] = make_pdf_bytes("CAGR 10% TAM 1000")

    put_file(ctx, team_id=team_id, file_id=file_id, bucket=bucket, key=key, original_name="evidence.pdf")
    put_job(ctx, team_id=team_id, job_id=job_id, job_type="pdf_evidence", file_ids=[file_id], params={"maxPages": 3, "maxResults": 5})

    try:
        process_job(ctx, team_id, job_id)
        job = ctx.ddb.get_item(Key={"pk": _pk_team(team_id), "sk": _sk_job(job_id)})["Item"]
        assert job["status"] == "succeeded"
        assert job["artifacts"][0]["artifactId"] == "pdf_evidence_json"
        payload = json.loads(ctx.s3.objects[(bucket, job["artifacts"][0]["s3Key"])].decode("utf-8"))
        assert payload.get("success") is True
        assert payload.get("evidence_count", 0) >= 1

        # Originals deleted.
        assert (bucket, key) not in ctx.s3.objects
        f = ctx.ddb.get_item(Key={"pk": _pk_team(team_id), "sk": _sk_file(file_id)})["Item"]
        assert f["status"] == "deleted"
    finally:
        cleanup_job_dir(team_id, job_id)


def test_delete_inputs_flag_false_preserves_uploads():
    team_id = "team_1"
    job_id = "job_pdf_keep"
    bucket = "merry-test"
    ctx = FakeCtx(bucket=bucket, delete_inputs=False)

    file_id = "file_pdf_keep"
    key = f"uploads/{team_id}/{file_id}.pdf"
    ctx.s3.objects[(bucket, key)] = make_pdf_bytes("CAGR 12% TAM 42")

    put_file(ctx, team_id=team_id, file_id=file_id, bucket=bucket, key=key, original_name="keep.pdf")
    put_job(ctx, team_id=team_id, job_id=job_id, job_type="pdf_evidence", file_ids=[file_id], params={"maxPages": 2, "maxResults": 3})

    try:
        process_job(ctx, team_id, job_id)
        assert (bucket, key) in ctx.s3.objects
        f = ctx.ddb.get_item(Key={"pk": _pk_team(team_id), "sk": _sk_file(file_id)})["Item"]
        assert f["status"] == "uploaded"
    finally:
        cleanup_job_dir(team_id, job_id)
