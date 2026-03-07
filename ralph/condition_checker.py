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
_DEFAULT_EVIDENCE = "문서에서 확인 불가"


def _normalize_requested_conditions(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _sanitize_json(raw: str) -> str:
    """
    LLM JSON 응답에서 문자열 내부 제어문자를 이스케이프하고
    잘못된 \\u 시퀀스를 제거한다.
    """
    ctrl = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}
    out: list[str] = []
    in_str = False
    i = 0

    while i < len(raw):
        ch = raw[i]
        if not in_str:
            out.append(ch)
            if ch == '"':
                in_str = True
            i += 1
            continue

        if ch == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt == "u":
                hex4 = raw[i + 2 : i + 6]
                if len(hex4) == 4 and all(c in "0123456789abcdefABCDEF" for c in hex4):
                    out.append(raw[i : i + 6])
                    i += 6
                else:
                    i += 2
            else:
                out.append(ch)
                out.append(nxt)
                i += 2
            continue

        if ch == '"':
            out.append(ch)
            in_str = False
            i += 1
            continue

        if ord(ch) < 32:
            out.append(ctrl.get(ch, f"\\u{ord(ch):04x}"))
            i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def _load_json_object(candidate: str) -> dict | None:
    try:
        parsed = json.loads(_sanitize_json(candidate.strip()))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _condition_key(value: object) -> str:
    return " ".join(str(value).split()).strip().lower()


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {"true", "1", "yes", "y", "충족", "예", "o", "✓", "pass"}
    return False


def _normalize_company_name(value: object) -> str | None:
    if value is None:
        return None
    name = str(value).strip()
    if not name or name.lower() == "null":
        return None
    return name


def _normalize_conditions_output(
    requested_conditions: list[str],
    raw_conditions: object,
) -> list[dict]:
    candidates = raw_conditions if isinstance(raw_conditions, list) else []
    available = [item for item in candidates if isinstance(item, dict)]
    claimed: set[int] = set()
    normalized: list[dict] = []

    for idx, requested in enumerate(requested_conditions):
        requested_key = _condition_key(requested)

        match_index = next(
            (
                i for i, item in enumerate(available)
                if i not in claimed and _condition_key(item.get("condition")) == requested_key
            ),
            None,
        )
        if match_index is None and idx < len(available):
            match_index = next((i for i in range(idx, len(available)) if i not in claimed), None)
        if match_index is None:
            match_index = next((i for i in range(len(available)) if i not in claimed), None)

        if match_index is None:
            normalized.append({
                "condition": requested,
                "result": False,
                "evidence": _DEFAULT_EVIDENCE,
            })
            continue

        claimed.add(match_index)
        item = available[match_index]
        evidence_raw = item.get("evidence")
        evidence = str(evidence_raw).strip() if evidence_raw is not None else ""
        normalized.append({
            "condition": requested,
            "result": _coerce_bool(item.get("result")),
            "evidence": evidence or _DEFAULT_EVIDENCE,
        })

    return normalized


def _parse_model_output(raw: str, requested_conditions: list[str]) -> dict:
    payload = _load_json_object(raw)
    if payload is None:
        fence = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        if fence:
            payload = _load_json_object(fence.group(1))
    if payload is None:
        block = re.search(r"\{.*\}", raw, re.DOTALL)
        if block:
            payload = _load_json_object(block.group(0))

    result = {
        "company_name": None,
        "conditions": _normalize_conditions_output(requested_conditions, None),
    }

    if payload is None:
        result["raw_response"] = raw[:500]
        result["parse_warning"] = "JSON_PARSE_FAILED"
        return result

    result["company_name"] = _normalize_company_name(payload.get("company_name"))
    result["conditions"] = _normalize_conditions_output(requested_conditions, payload.get("conditions"))
    if "raw_response" in payload:
        result["raw_response"] = payload["raw_response"]
    return result


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
    conditions = _normalize_requested_conditions(list(conditions))
    if not conditions:
        raise ValueError("conditions 파라미터가 비어 있습니다")

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

    return _attach_usage(_parse_model_output(raw, conditions))


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
        conditions = _normalize_requested_conditions(json.loads(conditions_raw))
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
