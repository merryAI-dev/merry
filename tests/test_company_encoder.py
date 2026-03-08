"""Tests for company alias encoder helpers."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ralph.company_encoder import build_company_alias_map, company_alias_similarity, should_merge_company_alias


def test_should_merge_company_alias_matches_truncated_prefix() -> None:
    assert should_merge_company_alias("스트레", "스트레스솔루션") is True
    assert company_alias_similarity("스트레", "스트레스솔루션") >= 0.78


def test_should_merge_company_alias_rejects_different_companies() -> None:
    assert should_merge_company_alias("메리", "스트레스솔루션") is False


def test_build_company_alias_map_prefers_larger_canonical_group() -> None:
    alias_map, stats = build_company_alias_map([
        {"company_group_key": "스트레", "company_group_name": "스트레", "file_count": 3},
        {"company_group_key": "스트레스솔루션", "company_group_name": "스트레스솔루션", "file_count": 8},
        {"company_group_key": "메리", "company_group_name": "메리", "file_count": 2},
    ])

    assert alias_map["스트레"]["company_group_key"] == "스트레스솔루션"
    assert alias_map["스트레"]["company_group_name"] == "스트레스솔루션"
    assert alias_map["스트레스솔루션"]["company_group_key"] == "스트레스솔루션"
    assert alias_map["메리"]["company_group_key"] == "메리"
    assert stats["merged_group_count"] == 1
