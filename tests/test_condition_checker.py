"""Unit tests for Ralph condition-checker output normalization."""
import os
import sys
from datetime import date
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ralph.condition_checker import (
    _evaluate_rule_conditions,
    extract_condition_facts,
    _normalize_requested_conditions,
    _parse_model_output,
    check_conditions_nova,
)


def test_parse_model_output_recovers_unescaped_newlines():
    raw = (
        '{"company_name":"ACME","conditions":['
        '{"condition":"조건A","result":true,"evidence":"첫 줄\n둘째 줄"}'
        "]}"
    )

    result = _parse_model_output(raw, ["조건A"])

    assert result["company_name"] == "ACME"
    assert result["conditions"] == [
        {"condition": "조건A", "result": True, "evidence": "첫 줄\n둘째 줄"}
    ]


def test_parse_model_output_preserves_requested_order_and_fills_missing():
    raw = """
```json
{
  "company_name": "테스트 주식회사",
  "conditions": [
    {"condition": "조건B", "result": "true", "evidence": "두 번째 조건 근거"},
    {"condition": "조건A", "result": 0, "evidence": "첫 번째 조건 미충족"}
  ]
}
```
"""

    result = _parse_model_output(raw, ["조건A", "조건B", "조건C"])

    assert result["company_name"] == "테스트 주식회사"
    assert result["conditions"] == [
        {"condition": "조건A", "result": False, "evidence": "첫 번째 조건 미충족"},
        {"condition": "조건B", "result": True, "evidence": "두 번째 조건 근거"},
        {"condition": "조건C", "result": False, "evidence": "문서에서 확인 불가"},
    ]


def test_parse_model_output_returns_defaults_on_non_json_response():
    result = _parse_model_output("분석 결과를 텍스트로 설명합니다.", ["조건A", "조건B"])

    assert result["company_name"] is None
    assert result["parse_warning"] == "JSON_PARSE_FAILED"
    assert result["conditions"] == [
        {"condition": "조건A", "result": False, "evidence": "문서에서 확인 불가"},
        {"condition": "조건B", "result": False, "evidence": "문서에서 확인 불가"},
    ]


def test_normalize_requested_conditions_filters_blank_values():
    assert _normalize_requested_conditions(["조건A", "  ", "", 3]) == ["조건A", "3"]


def test_check_conditions_nova_rejects_empty_conditions_without_calling_bedrock():
    try:
        check_conditions_nova("sample text", ["", "  "], "model", "region")
    except ValueError as exc:
        assert str(exc) == "conditions 파라미터가 비어 있습니다"
    else:
        raise AssertionError("ValueError was not raised")


def test_extract_condition_facts_parses_establishment_and_revenue_candidates():
    text = """
법인명: 테스트 주식회사
개업연월일: 2024년 03월 01일
2025년 매출액 8억원
"""

    facts = extract_condition_facts(text, reference_date=date(2026, 3, 7))

    assert facts["company_name"] == "테스트 주식회사"
    assert facts["company_group_name"] == "테스트"
    assert facts["company_group_key"] == "테스트"
    assert facts["establishment_date"] == "2024-03-01"
    assert facts["business_age_years"] is not None
    assert facts["business_age_years"] < 3
    assert facts["revenue_candidates"][0]["amount"] == 800_000_000


def test_extract_condition_facts_groups_company_name_variants():
    facts = extract_condition_facts("회사명: ㈜ 테스트랩", reference_date=date(2026, 3, 7))

    assert facts["company_name"] == "㈜ 테스트랩"
    assert facts["company_group_name"] == "테스트랩"
    assert facts["company_group_key"] == "테스트랩"


def test_extract_condition_facts_ignores_missing_company_markers():
    facts = extract_condition_facts("문서 본문에 회사명이 없습니다.", reference_date=date(2026, 3, 7))

    assert facts["company_name"] is None
    assert facts["company_group_name"] is None
    assert facts["company_group_key"] is None


def test_evaluate_rule_conditions_resolves_business_age_and_revenue_rules():
    text = """
상호명 테스트기업
설립일: 2024-03-01
2025년 매출액 8억원
"""

    rule_results, facts = _evaluate_rule_conditions(
        text,
        ["창업 3년 미만", "매출 10억 미만"],
        reference_date=date(2026, 3, 7),
    )

    assert facts["establishment_date"] == "2024-03-01"
    assert rule_results[0]["result"] is True
    assert rule_results[0]["source"] == "rule"
    assert rule_results[1]["result"] is True
    assert rule_results[1]["source"] == "rule"
    assert "8.0억원" in rule_results[1]["evidence"]


def test_check_conditions_nova_skips_bedrock_when_rules_cover_all_conditions():
    text = """
법인명: 테스트 주식회사
개업연월일: 2024년 03월 01일
2025년 매출액 8억원
"""

    with patch("boto3.client", side_effect=AssertionError("Bedrock should not be called")):
        result = check_conditions_nova(
            text,
            ["창업 3년 미만", "매출 10억 미만"],
            "model",
            "region",
            facts=extract_condition_facts(text, reference_date=date(2026, 3, 7)),
        )

    assert result["company_name"] == "테스트 주식회사"
    assert result["company_group_name"] == "테스트"
    assert result["company_group_key"] == "테스트"
    assert result["condition_summary"]["rule_count"] == 2
    assert result["condition_summary"]["llm_count"] == 0
    assert result["_usage"]["input_tokens"] == 0
    assert result["_usage"]["output_tokens"] == 0
    assert all(item["source"] == "rule" for item in result["conditions"])


def test_check_conditions_nova_merges_rule_and_llm_results_in_original_order():
    text = """
회사명: 하이브리드 기업
설립일: 2024-03-01
"""

    class _FakeBedrock:
        def converse(self, **kwargs):
            assert "매출 성장률 10% 이상" in kwargs["messages"][0]["content"][0]["text"]
            return {
                "output": {
                    "message": {
                        "content": [
                            {
                                "text": """
{
  "company_name": "하이브리드 기업",
  "conditions": [
    {"condition": "매출 성장률 10% 이상", "result": false, "evidence": "문서에서 성장률 수치를 찾지 못했습니다."}
  ]
}
""",
                            }
                        ]
                    }
                },
                "usage": {"inputTokens": 123, "outputTokens": 45},
            }

    with patch("boto3.client", return_value=_FakeBedrock()):
        result = check_conditions_nova(
            text,
            ["창업 3년 미만", "매출 성장률 10% 이상"],
            "model",
            "region",
            facts=extract_condition_facts(text, reference_date=date(2026, 3, 7)),
        )

    assert result["company_name"] == "하이브리드 기업"
    assert result["company_group_name"] == "하이브리드 기업"
    assert result["company_group_key"] == "하이브리드기업"
    assert [item["condition"] for item in result["conditions"]] == ["창업 3년 미만", "매출 성장률 10% 이상"]
    assert result["conditions"][0]["source"] == "rule"
    assert result["conditions"][1]["source"] == "llm"
    assert result["condition_summary"]["rule_count"] == 1
    assert result["condition_summary"]["llm_count"] == 1
    assert result["_usage"]["input_tokens"] == 123
    assert result["_usage"]["output_tokens"] == 45
