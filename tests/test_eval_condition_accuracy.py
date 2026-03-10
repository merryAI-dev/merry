"""Tests for scripts.eval_condition_accuracy."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.eval_condition_accuracy import evaluate_goldset, load_goldset_manifest


def test_load_goldset_manifest_reads_jsonl(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "\n".join([
            '{"record_id":"r1","filename":"doc_1.pdf","policy_id":"under_3y","policy_text":"업력 3년 미만","expected_result":true,"review_status":"confirmed"}',
            '{"record_id":"r2","filename":"doc_2.pdf","policy_id":"sales_under_1b","policy_text":"매출 10억 미만","expected_result":false,"review_status":"confirmed"}',
        ]),
        encoding="utf-8",
    )

    records = load_goldset_manifest(manifest)
    assert len(records) == 2
    assert records[0].record_id == "r1"
    assert records[1].expected_result is False


def test_evaluate_goldset_computes_precision_recall_and_missing() -> None:
    goldset = load_goldset_manifest_from_lines([
        {
            "record_id": "r1",
            "filename": "doc_1.pdf",
            "policy_id": "under_3y",
            "policy_text": "업력 3년 미만",
            "expected_result": True,
            "expected_evidence": ["2024년 03월 01일"],
            "review_status": "confirmed",
        },
        {
            "record_id": "r2",
            "filename": "doc_2.pdf",
            "policy_id": "sales_under_1b",
            "policy_text": "매출 10억 미만",
            "expected_result": False,
            "review_status": "confirmed",
        },
        {
            "record_id": "r3",
            "filename": "doc_3.pdf",
            "policy_id": "sales_under_1b",
            "policy_text": "매출 10억 미만",
            "expected_result": True,
            "review_status": "confirmed",
        },
    ])

    report = evaluate_goldset(goldset, {
        "results": [
            {
                "filename": "doc_1.pdf",
                "company_group_key": "alpha",
                "conditions": [
                    {"condition": "업력 3년 미만", "result": True, "evidence": "개업연월일 2024년 03월 01일"},
                ],
            },
            {
                "filename": "doc_2.pdf",
                "company_group_key": "alpha",
                "conditions": [
                    {"condition": "매출 10억 미만", "result": True, "evidence": "매출액 12억원"},
                ],
            },
        ],
    })

    assert report["summary"]["tp"] == 1
    assert report["summary"]["fp"] == 1
    assert report["summary"]["missing"] == 1
    assert report["summary"]["precision"] == 0.5
    assert report["summary"]["recall"] == 0.5
    assert report["summary"]["evidence_hit_rate"] == 0.3333
    assert len(report["errors"]["false_positives"]) == 1
    assert len(report["errors"]["missing"]) == 1


def load_goldset_manifest_from_lines(records: list[dict]) -> list:
    path = Path("/tmp/test_eval_condition_accuracy_manifest.jsonl")
    path.write_text("\n".join(json_line(record) for record in records), encoding="utf-8")
    return load_goldset_manifest(path)


def json_line(record: dict) -> str:
    import json
    return json.dumps(record, ensure_ascii=False)
