"""
Fan-out E2E integration tests.

Validates the full fan-out lifecycle using in-memory fakes:
1. Job creation with N tasks
2. Per-file processing via process_fanout_task
3. Atomic counter increments (processed_count)
4. Assembly (CSV + JSON generation)
5. Token usage aggregation
6. Mixed success/failure scenarios

No real AWS dependencies — uses in-memory fake DDB/S3.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from worker.main import (  # noqa: E402
    process_fanout_task,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── Fake DynamoDB Table (supports fan-out operations) ──

class _ConditionalCheckFailed(Exception):
    pass


class _FakeMeta:
    class client:
        class exceptions:
            ConditionalCheckFailedException = _ConditionalCheckFailed


class FakeDdbTable:
    """In-memory DDB table supporting SET, ADD, conditional writes, and queries."""

    meta = _FakeMeta()

    def __init__(self) -> None:
        self.items: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def get_item(self, Key: Dict[str, Any], **kw: Any) -> Dict[str, Any]:
        item = self.items.get((Key["pk"], Key["sk"]))
        return {"Item": dict(item)} if item else {}

    def put_item(self, Item: Dict[str, Any], **kw: Any) -> None:
        self.items[(Item["pk"], Item["sk"])] = dict(Item)

    def put(self, item: Dict[str, Any]) -> None:
        self.items[(item["pk"], item["sk"])] = dict(item)

    def update_item(self, *, Key: Dict[str, Any], **kw: Any) -> None:
        pk, sk = Key["pk"], Key["sk"]
        names = kw.get("ExpressionAttributeNames", {})
        values = kw.get("ExpressionAttributeValues", {})
        cond = kw.get("ConditionExpression", "")

        # Evaluate condition.
        item = self.items.get((pk, sk))
        if cond and not self._eval_condition(item, cond, names, values):
            raise _ConditionalCheckFailed("Condition failed")

        item = dict(item) if item else {"pk": pk, "sk": sk}
        expr = kw.get("UpdateExpression", "")
        self._apply_expr(item, expr, names, values)
        self.items[(pk, sk)] = item

    def query(self, **kw: Any) -> Dict[str, Any]:
        values = kw.get("ExpressionAttributeValues", {})
        pk_val = values.get(":pk", "")
        # Support begins_with for sk.
        prefix = values.get(":prefix", values.get(":sk_prefix", None))
        sk_eq = values.get(":sk", None)

        items = []
        for (k_pk, k_sk), item in self.items.items():
            if pk_val and k_pk != pk_val:
                continue
            if sk_eq and k_sk != sk_eq:
                continue
            if prefix and not k_sk.startswith(prefix):
                continue
            items.append(dict(item))

        limit = kw.get("Limit")
        if limit:
            items = items[:limit]
        return {"Items": items}

    # ── Internal helpers ──

    def _eval_condition(
        self, item: Optional[Dict], cond: str, names: Dict, values: Dict,
    ) -> bool:
        if item is None:
            if "attribute_not_exists" in cond:
                return True
            return False

        def _resolve_field(ref: str) -> str:
            return names.get(ref, ref)

        def _resolve_val(ref: str) -> Any:
            return values.get(ref, ref)

        # Handle AND.
        if " AND " in cond:
            parts = cond.split(" AND ")
            return all(self._eval_condition(item, p.strip(), names, values) for p in parts)

        # Handle OR.
        if " OR " in cond:
            parts = cond.split(" OR ")
            return any(self._eval_condition(item, p.strip(), names, values) for p in parts)

        # Handle IN: #status IN (:a, :b).
        m = re.match(r"(\S+)\s+IN\s*\(([^)]+)\)", cond.strip())
        if m:
            field = _resolve_field(m.group(1))
            val_refs = [v.strip() for v in m.group(2).split(",")]
            actual = item.get(field, "")
            return actual in [_resolve_val(vr) for vr in val_refs]

        # Handle equality: #field = :val.
        m = re.match(r"(\S+)\s*=\s*(\S+)", cond.strip())
        if m:
            field = _resolve_field(m.group(1))
            expected = _resolve_val(m.group(2))
            return item.get(field) == expected

        # Handle comparison: #field < :val.
        m = re.match(r"(\S+)\s*<\s*(\S+)", cond.strip())
        if m:
            field = _resolve_field(m.group(1))
            threshold = _resolve_val(m.group(2))
            return str(item.get(field, "")) < str(threshold)

        # Fallback: attribute_not_exists.
        if "attribute_not_exists" in cond:
            return True
        return True

    def _apply_expr(
        self, item: Dict, expr: str, names: Dict, values: Dict,
    ) -> None:
        """Parse and apply SET and ADD clauses."""
        # Split into SET/ADD blocks.
        set_match = re.search(r"SET\s+(.*?)(?=\s+ADD\s|$)", expr, re.DOTALL)
        add_match = re.search(r"ADD\s+(.*?)(?=\s+SET\s|$)", expr, re.DOTALL)

        if set_match:
            assigns = [a.strip() for a in set_match.group(1).split(",") if a.strip()]
            for assign in assigns:
                parts = assign.split("=", 1)
                if len(parts) != 2:
                    continue
                lhs = names.get(parts[0].strip(), parts[0].strip())
                rhs_ref = parts[1].strip()
                item[lhs] = values.get(rhs_ref, rhs_ref)

        if add_match:
            tokens = [t.strip() for t in add_match.group(1).split(",") if t.strip()]
            for token in tokens:
                parts = token.split()
                if len(parts) != 2:
                    continue
                field = names.get(parts[0], parts[0])
                delta = values.get(parts[1], 0)
                if isinstance(delta, Decimal):
                    delta = int(delta)
                current = item.get(field, 0)
                if isinstance(current, Decimal):
                    current = int(current)
                item[field] = current + delta


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: Dict[Tuple[str, str], bytes] = {}

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        data = self.objects.get((bucket, key))
        if data is None:
            raise FileNotFoundError(f"s3://{bucket}/{key}")
        p = Path(filename)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def upload_file(self, filename: str, bucket: str, key: str, ExtraArgs: Any = None) -> None:
        self.objects[(bucket, key)] = Path(filename).read_bytes()

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.objects.pop((Bucket, Key), None)


class FakeDdbClient:
    """Fake low-level DDB client for transact_write_items."""

    def __init__(self, table: FakeDdbTable) -> None:
        self._table = table

    def transact_write_items(self, **kwargs: Any) -> None:
        for item in kwargs.get("TransactItems", []):
            if "Update" in item:
                upd = item["Update"]
                pk = upd["Key"]["pk"]["S"]
                sk = upd["Key"]["sk"]["S"]
                expr = upd.get("UpdateExpression", "")
                ean = upd.get("ExpressionAttributeNames", {})
                eav_raw = upd.get("ExpressionAttributeValues", {})
                # Convert wire format.
                eav: Dict[str, Any] = {}
                for k, v in eav_raw.items():
                    if "S" in v:
                        eav[k] = v["S"]
                    elif "N" in v:
                        eav[k] = int(v["N"])
                    else:
                        eav[k] = str(v)
                self._table.update_item(
                    Key={"pk": pk, "sk": sk},
                    UpdateExpression=expr,
                    ExpressionAttributeNames=ean,
                    ExpressionAttributeValues=eav,
                )


class FakeCtx:
    def __init__(self, *, bucket: str = "test-bucket", delete_inputs: bool = False) -> None:
        self.bucket = bucket
        self.delete_inputs = delete_inputs
        self.region = "us-east-1"
        self.ddb_table = "test-table"
        self._ddb = FakeDdbTable()
        self._s3 = FakeS3Client()
        self._ddb_client = FakeDdbClient(self._ddb)

    @property
    def ddb(self) -> FakeDdbTable:
        return self._ddb

    @property
    def s3(self) -> FakeS3Client:
        return self._s3

    @property
    def ddb_client(self) -> FakeDdbClient:
        return self._ddb_client


# ── Helpers ──

def _pk(t: str) -> str:
    return f"TEAM#{t}"


def make_pdf_bytes(text: str) -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes() if hasattr(doc, "tobytes") else doc.write()
    doc.close()
    return data


def setup_fanout_job(
    ctx: FakeCtx,
    team_id: str,
    job_id: str,
    file_ids: List[str],
    conditions: List[str],
    *,
    pdf_texts: Optional[Dict[str, str]] = None,
) -> None:
    """Set up a complete fan-out job: JOB + FILE + TASK records + S3 PDFs."""
    ctx.ddb.put({
        "pk": f"TEAM#{team_id}#JOBS", "sk": f"CREATED#2026-03-01T00:00:00Z#JOB#{job_id}",
        "entity": "job_index", "job_id": job_id, "team_id": team_id,
        "type": "condition_check", "status": "running",
        "fanout": True, "fanout_status": "running",
        "title": "테스트", "created_at": "2026-03-01T00:00:00Z",
        "created_by": "tester",
    })

    ctx.ddb.put({
        "pk": _pk(team_id), "sk": f"JOB#{job_id}",
        "entity": "job", "job_id": job_id, "team_id": team_id,
        "type": "condition_check", "status": "running",
        "title": "테스트", "created_by": "tester",
        "created_at": "2026-03-01T00:00:00Z",
        "updated_at": "2026-03-01T00:00:00Z",
        "input_file_ids": file_ids,
        "params": {"conditions": conditions},
        "error": "", "artifacts": [], "metrics": {},
        "fanout": True, "total_tasks": len(file_ids),
        "processed_count": 0, "failed_count": 0,
        "fanout_status": "running",
    })

    for i, fid in enumerate(file_ids):
        s3_key = f"uploads/{team_id}/{fid}.pdf"
        text = (pdf_texts or {}).get(fid, f"Document {i}")
        ctx.s3.objects[(ctx.bucket, s3_key)] = make_pdf_bytes(text)

        ctx.ddb.put({
            "pk": _pk(team_id), "sk": f"FILE#{fid}",
            "entity": "file", "file_id": fid, "team_id": team_id,
            "status": "uploaded", "original_name": f"doc_{i}.pdf",
            "s3_bucket": ctx.bucket, "s3_key": s3_key,
        })

        task_id = f"{i:03d}"
        ctx.ddb.put({
            "pk": _pk(team_id), "sk": f"TASK#{job_id}#{task_id}",
            "entity": "task", "job_id": job_id, "task_id": task_id,
            "team_id": team_id, "task_index": i, "status": "pending",
            "file_id": fid, "created_at": "2026-03-01T00:00:00Z",
        })
        # Also create task index record.
        ctx.ddb.put({
            "pk": f"TEAM#{team_id}#TASKS#{job_id}",
            "sk": f"TASK#{task_id}",
            "entity": "task_index", "status": "pending",
        })


def get_job(ctx: FakeCtx, team_id: str, job_id: str) -> Dict[str, Any]:
    return ctx.ddb.get_item(Key={"pk": _pk(team_id), "sk": f"JOB#{job_id}"}).get("Item", {})


def get_task_result(ctx: FakeCtx, team_id: str, job_id: str, task_id: str) -> Dict[str, Any]:
    raw = ctx.ddb.items[(_pk(team_id), f"TASK#{job_id}#{task_id}")]["result"]
    return json.loads(raw) if isinstance(raw, str) else raw


def cleanup(team_id: str, job_id: str) -> None:
    p = PROJECT_ROOT / "temp" / team_id / "jobs" / job_id
    shutil.rmtree(p, ignore_errors=True)


# ── Mock Bedrock ──

def _mock_check_nova(text: str, conditions: list, model_id: str, region: str, facts=None) -> dict:
    """Fake check_conditions_nova returning deterministic results + usage."""
    return {
        "company_name": "테스트기업",
        "conditions": [
            {"condition": c, "result": True, "evidence": f"mock: {c}"}
            for c in conditions
        ],
        "_usage": {"input_tokens": 500, "output_tokens": 200},
    }


def _mock_call_nova_visual(images, model_id, region, prompt, max_tokens=1200) -> dict:
    """Fake call_nova_visual returning deterministic results + usage."""
    return {
        "readable_text": "Mocked VLM text extraction.",
        "_usage": {"input_tokens": 300, "output_tokens": 100},
    }


def _mock_check_nova_warning(text: str, conditions: list, model_id: str, region: str, facts=None) -> dict:
    return {
        "company_name": "경고기업",
        "conditions": [
            {"condition": c, "result": True, "evidence": f"warning: {c}"}
            for c in conditions
        ],
        "parse_warning": "JSON 응답 일부를 복구했습니다.",
        "raw_response": "{bad json",
        "_usage": {"input_tokens": 500, "output_tokens": 200},
    }


def _mock_check_nova_summary(text: str, conditions: list, model_id: str, region: str, facts=None) -> dict:
    rule_count = 1 if conditions else 0
    llm_count = max(len(conditions) - rule_count, 0)
    return {
        "company_name": "테스트기업",
        "conditions": [
            {
                "condition": c,
                "result": True,
                "evidence": f"summary: {c}",
                "source": "rule" if i < rule_count else "llm",
            }
            for i, c in enumerate(conditions)
        ],
        "condition_summary": {
            "total": len(conditions),
            "rule_count": rule_count,
            "llm_count": llm_count,
            "llm_skipped": llm_count == 0,
        },
        "detected_facts": {
            "company_name": "테스트기업",
        },
        "_usage": {"input_tokens": 500, "output_tokens": 200},
    }


# ── Tests ──

@pytest.fixture(autouse=True)
def _env():
    os.environ["MERRY_LAMBDA_ASSEMBLY"] = "false"
    os.environ["MERRY_CB_MIN_SAMPLES"] = "999"  # Disable circuit breaker.
    os.environ["MERRY_WEBHOOK_URL"] = ""  # No webhook.
    yield


class TestFanoutHappyPath:
    """3 files all succeed → assembly produces CSV + JSON with token usage."""

    def test_three_files_succeed(self):
        team, job = "t1", "j_happy"
        fids = ["f1", "f2", "f3"]
        conds = ["매출 10억 이상", "직원 50인 이상"]
        ctx = FakeCtx()
        setup_fanout_job(ctx, team, job, fids, conds)

        with patch("ralph.condition_checker.check_conditions_nova", _mock_check_nova), \
             patch("ralph.playground_parser.call_nova_visual", _mock_call_nova_visual):
            for i, fid in enumerate(fids):
                process_fanout_task(ctx, team, job, f"{i:03d}", fid)

        j = get_job(ctx, team, job)
        assert j["status"] == "succeeded"
        assert j["fanout_status"] == "succeeded"
        assert int(j.get("processed_count", 0)) == 3
        assert int(j.get("failed_count", 0)) == 0
        job_index = ctx.ddb.items[(f"TEAM#{team}#JOBS", f"CREATED#2026-03-01T00:00:00Z#JOB#{job}")]
        assert job_index["status"] == "succeeded"
        assert job_index["fanout_status"] == "succeeded"

        # Artifacts: XLSX + CSV + JSON.
        arts = j.get("artifacts", [])
        assert len(arts) == 3
        ids = {a["artifactId"] for a in arts}
        assert "condition_check_xlsx" in ids
        assert "condition_check_csv" in ids
        assert "condition_check_json" in ids

        # CSV content.
        csv_art = next(a for a in arts if "csv" in a["artifactId"])
        csv_bytes = ctx.s3.objects[(ctx.bucket, csv_art["s3Key"])]
        rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
        assert len(rows) == 3
        for row in rows:
            assert row.get("company_name") == "테스트기업"

        # JSON content.
        json_art = next(a for a in arts if "json" in a["artifactId"])
        data = json.loads(ctx.s3.objects[(ctx.bucket, json_art["s3Key"])].decode("utf-8"))
        assert data["total"] == 3
        assert data["conditions"] == conds

        # Token usage in metrics — should be > 0.
        tu = j.get("metrics", {}).get("token_usage", {})
        assert int(tu.get("input_tokens", 0)) > 0
        assert int(tu.get("output_tokens", 0)) > 0
        total = int(tu.get("total_tokens", 0))
        assert total == int(tu["input_tokens"]) + int(tu["output_tokens"])

        cleanup(team, job)


class TestFanoutPartialFailure:
    """One file fails → job still succeeds, failed_count=1."""

    def test_one_file_missing(self):
        team, job = "t2", "j_partial"
        fids = ["ok1", "missing", "ok2"]
        ctx = FakeCtx()
        setup_fanout_job(ctx, team, job, fids, ["조건A"])

        # Remove S3 object for "missing".
        ctx.s3.objects.pop((ctx.bucket, f"uploads/{team}/missing.pdf"), None)

        with patch("ralph.condition_checker.check_conditions_nova", _mock_check_nova), \
             patch("ralph.playground_parser.call_nova_visual", _mock_call_nova_visual):
            for i, fid in enumerate(fids):
                process_fanout_task(ctx, team, job, f"{i:03d}", fid)

        j = get_job(ctx, team, job)
        assert j["status"] == "succeeded"
        assert int(j.get("processed_count", 0)) == 3
        assert int(j.get("failed_count", 0)) >= 1

        cleanup(team, job)


class TestFanoutIdempotency:
    """Processing the same task twice: second call is skipped, counter=1."""

    def test_duplicate_skipped(self):
        team, job = "t3", "j_idem"
        ctx = FakeCtx()
        setup_fanout_job(ctx, team, job, ["fd"], ["조건X"])

        with patch("ralph.condition_checker.check_conditions_nova", _mock_check_nova), \
             patch("ralph.playground_parser.call_nova_visual", _mock_call_nova_visual):
            process_fanout_task(ctx, team, job, "000", "fd")
            process_fanout_task(ctx, team, job, "000", "fd")

        j = get_job(ctx, team, job)
        assert int(j.get("processed_count", 0)) == 1

        cleanup(team, job)


class TestFanoutTokenAggregation:
    """Token usage per-task aggregated into job metrics."""

    def test_tokens_summed(self):
        team, job = "t4", "j_tok"
        ctx = FakeCtx()
        setup_fanout_job(ctx, team, job, ["a", "b"], ["C1"])

        with patch("ralph.condition_checker.check_conditions_nova", _mock_check_nova):
            for i, fid in enumerate(["a", "b"]):
                process_fanout_task(ctx, team, job, f"{i:03d}", fid)

        j = get_job(ctx, team, job)
        tu = j.get("metrics", {}).get("token_usage", {})
        # Each task has check_conditions usage (500+200) + possibly VLM usage (300+100).
        assert int(tu.get("input_tokens", 0)) > 0
        assert int(tu.get("output_tokens", 0)) > 0
        total = int(tu.get("total_tokens", 0))
        assert total == int(tu["input_tokens"]) + int(tu["output_tokens"])
        # With 2 tasks, total should be at least 2 * (500+200) = 1400.
        assert total >= 1400

        cleanup(team, job)


class TestFanoutParseWarnings:
    """Recovered checker responses should remain visible in artifacts and metrics."""

    def test_warning_propagates_to_artifacts_and_metrics(self):
        team, job = "t_warning", "j_warning"
        ctx = FakeCtx()
        setup_fanout_job(ctx, team, job, ["warn"], ["조건A"])

        with patch("ralph.condition_checker.check_conditions_nova", _mock_check_nova_warning):
            process_fanout_task(ctx, team, job, "000", "warn")

        j = get_job(ctx, team, job)
        assert int(j.get("metrics", {}).get("warning_count", 0)) == 1

        arts = j.get("artifacts", [])
        csv_art = next(a for a in arts if a["artifactId"] == "condition_check_csv")
        csv_rows = list(csv.DictReader(io.StringIO(
            ctx.s3.objects[(ctx.bucket, csv_art["s3Key"])].decode("utf-8-sig"),
        )))
        assert csv_rows[0]["warning"] == "JSON 응답 일부를 복구했습니다."

        json_art = next(a for a in arts if a["artifactId"] == "condition_check_json")
        data = json.loads(ctx.s3.objects[(ctx.bucket, json_art["s3Key"])].decode("utf-8"))
        assert data["warning_count"] == 1
        assert data["results"][0]["parse_warning"] == "JSON 응답 일부를 복구했습니다."
        assert data["results"][0]["raw_response"] == "{bad json"

        cleanup(team, job)


class TestCancelledJobSkipped:
    """Task skipped when job is already failed/cancelled."""

    def test_skip_when_failed(self):
        team, job = "t5", "j_cancel"
        ctx = FakeCtx()
        setup_fanout_job(ctx, team, job, ["skip_me"], ["C1"])

        # Mark job as failed before task runs.
        ctx.ddb.items[(_pk(team), f"JOB#{job}")]["status"] = "failed"

        with patch("ralph.condition_checker.check_conditions_nova", _mock_check_nova), \
             patch("ralph.playground_parser.call_nova_visual", _mock_call_nova_visual):
            process_fanout_task(ctx, team, job, "000", "skip_me")

        j = get_job(ctx, team, job)
        assert int(j.get("processed_count", 0)) == 0

        cleanup(team, job)


class TestFanoutParseCacheReuse:
    """Same file content across jobs should reuse parse cache even when conditions differ."""

    def test_parse_cache_reused_for_same_content(self):
        team = "t_parse_cache"
        ctx = FakeCtx()
        pdf_text = "개업연월일 2024년 03월 01일\n2025년 매출액 8억원\n"

        setup_fanout_job(
            ctx, team, "job_a", ["file_a"], ["창업 3년 미만"],
            pdf_texts={"file_a": pdf_text},
        )
        setup_fanout_job(
            ctx, team, "job_b", ["file_b"], ["매출 10억 미만"],
            pdf_texts={"file_b": pdf_text},
        )
        ctx.s3.objects[(ctx.bucket, f"uploads/{team}/file_b.pdf")] = ctx.s3.objects[(ctx.bucket, f"uploads/{team}/file_a.pdf")]

        with patch("ralph.condition_checker.check_conditions_nova", _mock_check_nova_summary):
            process_fanout_task(ctx, team, "job_a", "000", "file_a")
            process_fanout_task(ctx, team, "job_b", "000", "file_b")

        job_b = get_job(ctx, team, "job_b")
        result = get_task_result(ctx, team, "job_b", "000")
        assert result["cache"]["parse_hit"] is True
        assert result["cache"]["result_hit"] is False
        assert int(job_b["metrics"]["parse_cache_hits"]) == 1

        cleanup(team, "job_a")
        cleanup(team, "job_b")


class TestFanoutResultCacheReuse:
    """Same file content + same conditions should reuse the full condition-check result."""

    def test_result_cache_reused_for_same_request(self):
        team = "t_result_cache"
        ctx = FakeCtx()
        pdf_text = "개업연월일 2024년 03월 01일\n2025년 매출액 8억원\n"

        setup_fanout_job(
            ctx, team, "job_c", ["file_c"], ["창업 3년 미만"],
            pdf_texts={"file_c": pdf_text},
        )
        setup_fanout_job(
            ctx, team, "job_d", ["file_d"], ["창업 3년 미만"],
            pdf_texts={"file_d": pdf_text},
        )
        ctx.s3.objects[(ctx.bucket, f"uploads/{team}/file_d.pdf")] = ctx.s3.objects[(ctx.bucket, f"uploads/{team}/file_c.pdf")]

        with patch("ralph.condition_checker.check_conditions_nova", _mock_check_nova_summary):
            process_fanout_task(ctx, team, "job_c", "000", "file_c")
            process_fanout_task(ctx, team, "job_d", "000", "file_d")

        job_d = get_job(ctx, team, "job_d")
        result = get_task_result(ctx, team, "job_d", "000")
        assert result["cache"]["result_hit"] is True
        assert int(result["token_usage"]["total_tokens"]) == 0
        assert int(job_d["metrics"]["result_cache_hits"]) == 1
        assert int(job_d["metrics"]["saved_total_tokens"]) > 0

        cleanup(team, "job_c")
        cleanup(team, "job_d")


class TestFanoutRuleSummaryMetrics:
    """Rule-engine summaries should aggregate into job metrics and artifacts."""

    def test_rule_and_llm_counts_are_aggregated(self):
        team, job = "t_rule_metrics", "j_rule_metrics"
        ctx = FakeCtx()
        setup_fanout_job(ctx, team, job, ["rule_a", "rule_b"], ["창업 3년 미만", "매출 성장률 10% 이상"])

        with patch("ralph.condition_checker.check_conditions_nova", _mock_check_nova_summary):
            process_fanout_task(ctx, team, job, "000", "rule_a")
            process_fanout_task(ctx, team, job, "001", "rule_b")

        j = get_job(ctx, team, job)
        assert int(j["metrics"]["rule_condition_count"]) == 2
        assert int(j["metrics"]["llm_condition_count"]) == 2

        csv_art = next(a for a in j["artifacts"] if a["artifactId"] == "condition_check_csv")
        csv_rows = list(csv.DictReader(io.StringIO(
            ctx.s3.objects[(ctx.bucket, csv_art["s3Key"])].decode("utf-8-sig"),
        )))
        assert csv_rows[0]["rule_conditions"] == "1"
        assert csv_rows[0]["llm_conditions"] == "1"

        cleanup(team, job)


class TestFanoutScale:
    """Large fan-out batches should finish with visible cache savings."""

    def test_800_files_complete_with_result_cache_observability(self):
        team, job = "t_scale", "j_scale_800"
        ctx = FakeCtx()
        conditions = ["업력 3년 미만", "매출 10억 미만"]
        unique_docs = 8
        repeats_per_doc = 100
        total_files = unique_docs * repeats_per_doc
        file_ids = [f"scale_{i:03d}" for i in range(total_files)]
        pdf_texts = {
            fid: (
                f"개업연월일 2024년 03월 01일\n"
                f"2025년 매출액 {((i % unique_docs) + 1)}억원\n"
                f"GROUP {i % unique_docs}\n"
            )
            for i, fid in enumerate(file_ids)
        }

        original_make_pdf_bytes = make_pdf_bytes
        pdf_cache: Dict[str, bytes] = {}

        def cached_make_pdf_bytes(text: str) -> bytes:
            if text not in pdf_cache:
                pdf_cache[text] = original_make_pdf_bytes(text)
            return pdf_cache[text]

        with patch(f"{__name__}.make_pdf_bytes", cached_make_pdf_bytes):
            setup_fanout_job(ctx, team, job, file_ids, conditions, pdf_texts=pdf_texts)

        with patch("ralph.condition_checker.check_conditions_nova", _mock_check_nova_summary):
            for i, fid in enumerate(file_ids):
                process_fanout_task(ctx, team, job, f"{i:03d}", fid)

        j = get_job(ctx, team, job)
        metrics = j.get("metrics", {})
        assert j["status"] == "succeeded"
        assert j["fanout_status"] == "succeeded"
        assert int(j.get("processed_count", 0)) == total_files
        assert int(j.get("failed_count", 0)) == 0
        assert int(metrics["result_cache_hits"]) == total_files - unique_docs
        assert int(metrics["parse_cache_hits"]) == 0
        assert int(metrics["saved_total_tokens"]) > 0
        assert int(metrics["rule_condition_count"]) == total_files
        assert int(metrics["llm_condition_count"]) == total_files

        csv_art = next(a for a in j["artifacts"] if a["artifactId"] == "condition_check_csv")
        csv_rows = list(csv.DictReader(io.StringIO(
            ctx.s3.objects[(ctx.bucket, csv_art["s3Key"])].decode("utf-8-sig"),
        )))
        assert len(csv_rows) == total_files
        assert sum(1 for row in csv_rows if row["cache"] == "result") == total_files - unique_docs
        assert sum(1 for row in csv_rows if row["cache"] == "") == unique_docs

        cleanup(team, job)
