"""
문서 조건 충족 여부 검사 (Nova Pro 텍스트 기반).

사용:
    python ralph/condition_checker.py <text_file>

환경변수:
    RALPH_CONDITIONS='["조건1", "조건2"]'  (JSON 배열)
    RALPH_VLM_NOVA_MODEL_ID  (기본: us.amazon.nova-pro-v1:0)
    RALPH_VLM_NOVA_REGION    (기본: us-east-1)

출력: JSON (stdout)
    {
        "ok": true,
        "company_name": "기업명 또는 null",
        "conditions": [
            {"condition": "조건 원문", "result": true, "evidence": "근거 텍스트"}
        ]
    }
"""
from __future__ import annotations

import json
import os
import re
import sys


_MAX_DOC_CHARS = 8000  # 토큰 절약: 최대 8000자


def check_conditions_nova(
    text: str,
    conditions: list[str],
    model_id: str,
    region: str,
) -> dict:
    """
    Nova Pro (텍스트 전용)로 각 조건의 충족 여부를 판단.
    기업명도 함께 추출.
    """
    import boto3

    cond_list = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(conditions))
    doc_text = text[:_MAX_DOC_CHARS]

    prompt = f"""\
다음 문서 내용을 읽고 각 조건의 충족 여부를 판단하세요.

=== 판단 조건 ===
{cond_list}

=== 문서 내용 ===
{doc_text}

=== 지시 ===
- 각 조건에 대해 충족(true) 또는 미충족(false)을 판단하세요
- 판단 근거가 되는 문서 내 구체적인 내용을 evidence로 인용하세요
- 문서에서 확인이 불가능한 경우 evidence를 "문서에서 확인 불가"로 표시하고 result는 false로 하세요
- 기업명(법인명 또는 상호)을 추출하세요 (없으면 null)

아래 JSON 형식으로만 응답하세요:
{{
  "company_name": "기업명 또는 null",
  "conditions": [
    {{"condition": "조건 원문", "result": true, "evidence": "근거 텍스트"}}
  ]
}}"""

    client = boto3.client("bedrock-runtime", region_name=region)
    resp = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 2000, "temperature": 0},
    )
    raw = resp["output"]["message"]["content"][0]["text"]

    # Extract token usage from Bedrock response.
    usage = resp.get("usage", {})
    _usage = {
        "input_tokens": usage.get("inputTokens", 0),
        "output_tokens": usage.get("outputTokens", 0),
    }

    # JSON 파싱 (3-pass)
    def _attach_usage(result: dict) -> dict:
        result["_usage"] = _usage
        return result

    try:
        return _attach_usage(json.loads(raw.strip()))
    except json.JSONDecodeError:
        pass
    m = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if m:
        try:
            return _attach_usage(json.loads(m.group(1)))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return _attach_usage(json.loads(m.group(0)))
        except json.JSONDecodeError:
            pass
    return _attach_usage({"company_name": None, "conditions": [], "raw_response": raw[:500]})


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "텍스트 파일 경로가 필요합니다"}))
        sys.exit(1)

    text_file = sys.argv[1]
    try:
        with open(text_file, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)

    conditions_raw = os.getenv("RALPH_CONDITIONS", "[]")
    try:
        conditions: list[str] = json.loads(conditions_raw)
    except json.JSONDecodeError:
        conditions = []

    if not conditions:
        print(json.dumps({"ok": False, "error": "RALPH_CONDITIONS가 비어 있습니다"}))
        sys.exit(1)

    model_id = os.getenv("RALPH_VLM_NOVA_MODEL_ID", "us.amazon.nova-pro-v1:0")
    region = os.getenv("RALPH_VLM_NOVA_REGION", "us-east-1")

    try:
        result = check_conditions_nova(text, conditions, model_id, region)
        result["ok"] = True
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    main()
