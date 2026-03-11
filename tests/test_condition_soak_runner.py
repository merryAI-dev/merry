"""Tests for scripts.run_condition_soak."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.run_condition_soak import (
    AUTHJS_COOKIE,
    SECURE_AUTHJS_COOKIE,
    _default_authjs_cookie_name,
    _make_upload_session_id,
    _parse_env_lines,
    _stage_file_count,
    _summarize_metric_snapshot,
)


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


def test_parse_env_lines_strips_quotes_and_comments() -> None:
    env = _parse_env_lines(
        """
        # comment
        AUTH_TEAM_ID="mysc"
        AUTH_ALLOWED_DOMAIN='mysc.co.kr'
        PLAIN=value
        """
    )

    assert env == {
        "AUTH_TEAM_ID": "mysc",
        "AUTH_ALLOWED_DOMAIN": "mysc.co.kr",
        "PLAIN": "value",
    }


def test_default_authjs_cookie_name_depends_on_scheme() -> None:
    assert _default_authjs_cookie_name("https://mysc-merry-inv.vercel.app") == SECURE_AUTHJS_COOKIE
    assert _default_authjs_cookie_name("http://127.0.0.1:3100") == AUTHJS_COOKIE


def test_make_upload_session_id_stays_within_limit(tmp_path: Path) -> None:
    pdf = tmp_path / "2. MYSC_주주명부('25.10.16)_주식회사 스트레스솔루션.pdf"
    pdf.write_bytes(b"pdf")

    session_id = _make_upload_session_id(pdf)

    assert session_id.startswith("soak-")
    assert len(session_id) <= 64
