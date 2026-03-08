"""Tests for scripts.condition_fanout_probe."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import fitz

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.condition_fanout_probe import analyze_dataset, write_probe_outputs


def _make_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    path.write_bytes(doc.tobytes() if hasattr(doc, "tobytes") else doc.write())
    doc.close()


def test_analyze_dataset_summarizes_duplicates_groups_and_rule_coverage(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    pdf_a = dataset_dir / "a.pdf"
    pdf_b = dataset_dir / "b.pdf"
    pdf_c = dataset_dir / "c.pdf"
    pdf_d = dataset_dir / "d.pdf"

    _make_pdf(pdf_a, "A")
    _make_pdf(pdf_b, "B")
    _make_pdf(pdf_c, "C")
    pdf_d.write_bytes(pdf_a.read_bytes())

    text_map = {
        "a": "법인명: 주식회사 테스트랩\n개업연월일: 2024년 03월 01일\n2025년 매출액 8억원\n",
        "b": "회사명: ㈜ 테스트랩\n개업연월일: 2024년 03월 01일\n2025년 매출액 8억원\n",
        "c": "회사명: 미기재\n",
        "d": "법인명: 주식회사 테스트랩\n개업연월일: 2024년 03월 01일\n2025년 매출액 8억원\n",
    }

    def _fake_extract_text(pdf_path: str):
        stem = Path(pdf_path).stem
        return text_map[stem], 1, []

    with patch("scripts.condition_fanout_probe.extract_text", side_effect=_fake_extract_text):
        result = analyze_dataset(
            [pdf_a, pdf_b, pdf_c, pdf_d],
            dataset_dir=dataset_dir,
            conditions=["업력 3년 미만", "매출 10억 미만"],
        )

    summary = result["summary"]
    assert summary["total_files"] == 4
    assert summary["unique_file_digests"] == 3
    assert summary["duplicate_files"] == 1
    assert summary["estimated_result_cache_hits"] == 1
    assert summary["recognized_company_files"] == 3
    assert summary["unrecognized_company_files"] == 1
    assert summary["company_group_count"] == 1
    assert summary["rule_only_files"] == 3
    assert summary["top_company_groups"][0]["company_group_name"] == "테스트랩"
    assert summary["top_company_groups"][0]["file_count"] == 3


def test_write_probe_outputs_creates_summary_and_records(tmp_path: Path) -> None:
    output_dir = tmp_path / "probe"
    result = {
        "summary": {
            "total_files": 1,
            "analyzed_files": 1,
            "error_files": 0,
            "unique_file_digests": 1,
            "duplicate_files": 0,
            "estimated_result_cache_hits": 0,
            "estimated_result_cache_rate": 0.0,
            "recognized_company_files": 1,
            "unrecognized_company_files": 0,
            "company_group_count": 1,
            "rule_only_files": 1,
            "rule_coverage_rate": 1.0,
            "unresolved_condition_rate": 0.0,
            "avg_text_chars": 42.0,
            "top_company_groups": [],
        },
        "records": [{
            "relative_path": "sample.pdf",
            "digest": "abc",
            "pages": 1,
            "text_chars": 42,
            "company_name": "테스트랩",
            "company_group_name": "테스트랩",
            "company_group_key": "테스트랩",
            "rule_count": 2,
            "unresolved_count": 0,
            "unresolved_conditions": [],
            "error": "",
        }],
    }

    outputs = write_probe_outputs(result, output_dir=output_dir)
    assert Path(outputs["summary_json"]).exists()
    assert Path(outputs["records_csv"]).exists()
