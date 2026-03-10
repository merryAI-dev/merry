"""Tests for scripts.run_condition_soak."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.run_condition_soak import _stage_file_count, _summarize_metric_snapshot


def test_stage_file_count_uses_stage_default() -> None:
    assert _stage_file_count("50", 0) == 50
    assert _stage_file_count("200", 0) == 200
    assert _stage_file_count("800", 0) == 800


def test_stage_file_count_prefers_limit_override() -> None:
    assert _stage_file_count("50", 12) == 12


def test_summarize_metric_snapshot_extracts_expected_keys() -> None:
    snapshot = _summarize_metric_snapshot({
        "metrics": {
            "total": 20,
            "company_alias_merge_count": "2",
            "company_alias_merged_files": "5",
            "result_cache_hits": 11,
        }
    })

    assert snapshot["total"] == 20
    assert snapshot["company_alias_merge_count"] == 2
    assert snapshot["company_alias_merged_files"] == 5
    assert snapshot["result_cache_hits"] == 11
    assert snapshot["parse_cache_hits"] == 0
