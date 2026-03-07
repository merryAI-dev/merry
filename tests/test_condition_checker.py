"""Unit tests for Ralph condition-checker output normalization."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ralph.condition_checker import (
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
