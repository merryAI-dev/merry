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
from datetime import date, datetime, timezone
from functools import lru_cache

from ralph.utils.korean_text import normalize_date, normalize_text, parse_korean_number


_MAX_DOC_CHARS = 8000  # 토큰 절약: 최대 8000자
_DEFAULT_EVIDENCE = "문서에서 확인 불가"
_COMPANY_KEYWORDS = ("법인명", "회사명", "기업명", "상호", "상호명")
_ESTABLISHMENT_KEYWORDS = ("개업연월일", "설립일", "설립연월일", "창업일", "창업연월일", "법인설립일")
_REVENUE_KEYWORDS = ("매출액", "매출")
_AMOUNT_UNITS = ("천만원", "백만원", "만원", "억원", "억", "원")
_COMPANY_PREFIXES = (
    "주식회사",
    "유한회사",
    "합자회사",
    "합명회사",
    "재단법인",
    "사단법인",
    "농업회사법인",
    "영농조합법인",
    "사회적협동조합",
    "협동조합",
)
_COMPANY_INVALID_TOKENS = (
    "종된사업장",
    "사업장",
    "말소사항",
    "자료",
    "명부",
    "증명",
    "사본",
    "원본",
)
_COMPANY_SENTENCE_ENDINGS = ("반영", "포함", "기재", "확인", "표시", "제출", "제공")
_COMPARATORS = {
    "미만": "lt",
    "이하": "lte",
    "이내": "lte",
    "이상": "gte",
    "초과": "gt",
}
_COMPARATOR_LABELS = {
    "lt": "미만",
    "lte": "이하",
    "gte": "이상",
    "gt": "초과",
}
_AMOUNT_MULTIPLIERS = {
    "원": 1,
    "만원": 10_000,
    "백만원": 1_000_000,
    "천만원": 10_000_000,
    "억": 100_000_000,
    "억원": 100_000_000,
}
_COMPANY_NEGATIVE_TOKENS = ("없음", "없습니다", "미기재", "해당 없음", "해당없음", "unknown", "n/a")


def _normalize_requested_conditions(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


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
    name = normalize_text(str(value))
    name = re.sub(r"\s+", " ", name).strip().strip(":：")
    name = name.strip("\"'“”‘’[](){}<>")
    if not name or name.lower() == "null":
        return None
    return name


def _company_group_name(value: object) -> str | None:
    name = _normalize_company_name(value)
    if not name:
        return None

    display = name
    display = display.replace("㈜", "")
    display = re.sub(r"\(\s*주\s*\)", "", display)
    display = re.sub(r"\(\s*유\s*\)", "", display)
    display = re.sub(r"（\s*주\s*）", "", display)
    display = re.sub(r"（\s*유\s*）", "", display)
    for prefix in _COMPANY_PREFIXES:
        display = re.sub(rf"^{re.escape(prefix)}\s*", "", display)
        display = re.sub(rf"\s*{re.escape(prefix)}$", "", display)
    display = re.sub(r"\s+", " ", display).strip(" -_.,:;")
    return display or name


def _company_group_key(value: object) -> str | None:
    group_name = _company_group_name(value)
    if not group_name:
        return None
    key = re.sub(r"[^0-9A-Za-z가-힣]+", "", group_name).lower()
    return key or None


def _apply_company_identity(facts: dict, company_name: object | None = None) -> dict:
    merged = dict(facts or {})
    effective_name = _normalize_company_name(company_name) or _normalize_company_name(merged.get("company_name"))
    merged["company_name"] = effective_name
    merged["company_group_name"] = _company_group_name(effective_name) if effective_name else None
    merged["company_group_key"] = _company_group_key(effective_name) if effective_name else None
    return merged


def _is_missing_company_marker(value: object) -> bool:
    name = _normalize_company_name(value)
    if not name:
        return True
    lowered = name.lower()
    compact = re.sub(r"\s+", "", lowered)
    return any(token in lowered or token.replace(" ", "") in compact for token in _COMPANY_NEGATIVE_TOKENS)


def _is_plausible_company_name(value: object) -> bool:
    name = _normalize_company_name(value)
    if not name or _is_missing_company_marker(name):
        return False
    group_name = _company_group_name(name) or ""
    if not group_name or not re.search(r"[A-Za-z0-9가-힣]", group_name):
        return False
    if any(token in group_name for token in _COMPANY_INVALID_TOKENS):
        return False
    if len(group_name) > 30:
        return False
    if (
        len(re.sub(r"[^가-힣]", "", group_name)) >= 8
        and " " not in name
        and not any(prefix in name for prefix in _COMPANY_PREFIXES)
        and any(group_name.endswith(ending) for ending in _COMPANY_SENTENCE_ENDINGS)
    ):
        return False
    return True


def _parse_amount_value(number_text: str, unit: str | None) -> int | None:
    numeric = number_text.replace(",", "").strip()
    if not numeric:
        return None
    multiplier = _AMOUNT_MULTIPLIERS.get(unit or "", 1)
    if not unit and len(re.sub(r"\D", "", numeric)) < 7:
        return None
    try:
        return int(float(numeric) * multiplier)
    except (ValueError, OverflowError):
        return None


def _format_amount_krw(value: int) -> str:
    if abs(value) >= 100_000_000:
        return f"{value / 100_000_000:.1f}억원"
    if abs(value) >= 10_000:
        return f"{value / 10_000:.1f}만원"
    return f"{value:,}원"


def _coerce_year(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _extract_company_name_from_text(text: str) -> str | None:
    for keyword in _COMPANY_KEYWORDS:
        pattern = rf"{keyword}\s*[:：]?\s*([^\n()]+)"
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = match.group(1).strip()
        candidate = re.split(r"\s{2,}|[|/]", candidate)[0].strip()
        candidate = candidate.rstrip(":：")
        candidate = _normalize_company_name(candidate)
        if candidate and len(candidate) <= 80 and _is_plausible_company_name(candidate):
            return candidate

    legal_form_pattern = re.compile(
        r"((?:주식회사|유한회사)\s*[A-Za-z0-9가-힣][A-Za-z0-9가-힣&.,·ㆍ\-\s]{1,40}|"
        r"[A-Za-z0-9가-힣][A-Za-z0-9가-힣&.,·ㆍ\-\s]{1,40}\s*(?:주식회사|유한회사)|"
        r"(?:㈜|\(\s*주\s*\)|（\s*주\s*）)\s*[A-Za-z0-9가-힣][A-Za-z0-9가-힣&.,·ㆍ\-\s]{1,40})"
    )
    for line in text.splitlines()[:20]:
        normalized_line = normalize_text(line).strip()
        if not normalized_line:
            continue
        match = legal_form_pattern.search(normalized_line)
        if not match:
            continue
        candidate = _normalize_company_name(match.group(1))
        if candidate and _is_plausible_company_name(candidate) and _company_group_key(candidate):
            return candidate
    return None


def _extract_establishment_date(text: str) -> str | None:
    for keyword in _ESTABLISHMENT_KEYWORDS:
        pattern = (
            rf"{keyword}\s*[:：]?\s*"
            r"([0-9]{4}\s*년\s*[0-9]{1,2}\s*월\s*[0-9]{1,2}\s*일?|"
            r"[0-9]{4}[.\-/][0-9]{1,2}[.\-/][0-9]{1,2})"
        )
        match = re.search(pattern, text)
        if match:
            normalized = normalize_date(match.group(1))
            if normalized:
                return normalized

    for line in text.splitlines():
        if not any(keyword in line for keyword in _ESTABLISHMENT_KEYWORDS):
            continue
        normalized = normalize_date(line)
        if normalized:
            return normalized
    return None


def _extract_revenue_candidates(text: str) -> list[dict]:
    candidates: list[dict] = []
    amount_pattern = re.compile(
        rf"([0-9][0-9,]*(?:\.\d+)?)\s*({'|'.join(_AMOUNT_UNITS)})?"
    )

    for line in text.splitlines():
        normalized_line = line.strip()
        if not normalized_line or not any(keyword in normalized_line for keyword in _REVENUE_KEYWORDS):
            continue
        year_match = re.search(r"(20\d{2})", normalized_line)
        year = _coerce_year(year_match.group(1) if year_match else None)
        for match in amount_pattern.finditer(normalized_line):
            amount = _parse_amount_value(match.group(1), match.group(2))
            if amount is None:
                continue
            snippet = normalized_line[:160]
            candidates.append({
                "amount": amount,
                "display": _format_amount_krw(amount),
                "year": year,
                "snippet": snippet,
            })

    deduped: list[dict] = []
    seen: set[tuple[int, int | None, str]] = set()
    for candidate in candidates:
        key = (candidate["amount"], candidate.get("year"), candidate["snippet"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped[:8]


def extract_condition_facts(
    text: str,
    reference_date: date | None = None,
) -> dict:
    normalized = normalize_text(text)
    ref = reference_date or _today_utc()
    facts = {
        "reference_date": ref.isoformat(),
        "company_name": _extract_company_name_from_text(normalized),
        "company_group_name": None,
        "company_group_key": None,
        "establishment_date": None,
        "business_age_years": None,
        "revenue_candidates": _extract_revenue_candidates(normalized),
    }

    establishment_date = _extract_establishment_date(normalized)
    if establishment_date:
        facts["establishment_date"] = establishment_date
        try:
            start = date.fromisoformat(establishment_date)
            facts["business_age_years"] = round(max((ref - start).days, 0) / 365.2425, 2)
        except ValueError:
            facts["establishment_date"] = None
            facts["business_age_years"] = None
    return _apply_company_identity(facts)


def _compare_numeric(observed: float, threshold: float, operator: str) -> bool:
    if operator == "lt":
        return observed < threshold
    if operator == "lte":
        return observed <= threshold
    if operator == "gte":
        return observed >= threshold
    if operator == "gt":
        return observed > threshold
    return False


def _pick_revenue_candidate(candidates: list[dict]) -> dict | None:
    if not candidates:
        return None
    with_year = [candidate for candidate in candidates if isinstance(candidate.get("year"), int)]
    if with_year:
        return sorted(with_year, key=lambda item: (int(item["year"]), int(item["amount"])), reverse=True)[0]
    if len(candidates) == 1:
        return candidates[0]
    unique_amounts = {int(candidate["amount"]) for candidate in candidates}
    if len(unique_amounts) == 1:
        return candidates[0]
    return None


@lru_cache(maxsize=512)
def _compile_condition_rule(condition: str) -> dict | None:
    normalized = " ".join(condition.split())
    if not normalized:
        return None

    age_match = re.search(r"(\d+(?:\.\d+)?)\s*년\s*(미만|이하|이내|이상|초과)", normalized)
    if age_match and any(keyword in normalized for keyword in ("창업", "설립", "업력", "개업")):
        return {
            "type": "business_age_years",
            "threshold": float(age_match.group(1)),
            "operator": _COMPARATORS[age_match.group(2)],
        }

    amount_match = re.search(
        rf"([0-9][0-9,]*(?:\.\d+)?)\s*({'|'.join(_AMOUNT_UNITS)})\s*(미만|이하|이내|이상|초과)",
        normalized,
    )
    if amount_match and any(keyword in normalized for keyword in _REVENUE_KEYWORDS):
        threshold = _parse_amount_value(amount_match.group(1), amount_match.group(2))
        if threshold is not None:
            return {
                "type": "revenue_amount",
                "threshold": threshold,
                "operator": _COMPARATORS[amount_match.group(3)],
            }
    return None


def _evaluate_rule_condition(condition: str, rule: dict | None, facts: dict) -> dict | None:
    if not rule:
        return None

    if rule["type"] == "business_age_years":
        establishment_date = facts.get("establishment_date")
        age_years = facts.get("business_age_years")
        if not establishment_date or not isinstance(age_years, (int, float)):
            return None
        threshold = float(rule["threshold"])
        operator = str(rule["operator"])
        matched = _compare_numeric(float(age_years), threshold, operator)
        evidence = (
            f"설립/개업일 {establishment_date}, 기준일 {facts.get('reference_date')} 기준 "
            f"업력 {float(age_years):.2f}년으로 {threshold:g}년 {_COMPARATOR_LABELS[operator]} 조건을 "
            f"{'충족' if matched else '미충족'}합니다."
        )
        return {
            "condition": condition,
            "result": matched,
            "evidence": evidence,
            "source": "rule",
            "rule_type": "business_age_years",
            "operator": operator,
            "threshold_value": threshold,
            "observed_value": round(float(age_years), 2),
        }

    if rule["type"] == "revenue_amount":
        candidate = _pick_revenue_candidate(
            facts.get("revenue_candidates") if isinstance(facts.get("revenue_candidates"), list) else [],
        )
        if not candidate:
            return None
        observed = int(candidate["amount"])
        threshold = int(rule["threshold"])
        operator = str(rule["operator"])
        matched = _compare_numeric(observed, threshold, operator)
        year_prefix = f"{candidate['year']}년 " if candidate.get("year") else ""
        evidence = (
            f"{year_prefix}매출 후보 {candidate['display']} ({candidate['snippet']})로 "
            f"{_format_amount_krw(threshold)} {_COMPARATOR_LABELS[operator]} 조건을 "
            f"{'충족' if matched else '미충족'}합니다."
        )
        return {
            "condition": condition,
            "result": matched,
            "evidence": evidence,
            "source": "rule",
            "rule_type": "revenue_amount",
            "operator": operator,
            "threshold_value": threshold,
            "observed_value": observed,
        }

    return None


def _evaluate_rule_conditions(
    text: str,
    requested_conditions: list[str],
    *,
    reference_date: date | None = None,
    facts: dict | None = None,
) -> tuple[dict[int, dict], dict]:
    extracted_facts = facts if isinstance(facts, dict) else extract_condition_facts(text, reference_date)
    results: dict[int, dict] = {}
    for index, condition in enumerate(requested_conditions):
        rule = _compile_condition_rule(condition)
        evaluated = _evaluate_rule_condition(condition, rule, extracted_facts)
        if evaluated is not None:
            results[index] = evaluated
    return results, extracted_facts


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
    result["company_group_name"] = _company_group_name(result["company_name"])
    result["company_group_key"] = _company_group_key(result["company_name"])
    result["conditions"] = _normalize_conditions_output(requested_conditions, payload.get("conditions"))
    if "raw_response" in payload:
        result["raw_response"] = payload["raw_response"]
    return result


def check_conditions_nova(
    text: str,
    conditions: list[str],
    model_id: str,
    region: str,
    facts: dict | None = None,
) -> dict:
    """
    Nova Pro (텍스트 전용)로 각 조건의 충족 여부를 판단.
    기업명도 함께 추출.
    """
    conditions = _normalize_requested_conditions(list(conditions))
    if not conditions:
        raise ValueError("conditions 파라미터가 비어 있습니다")

    rule_results, extracted_facts = _evaluate_rule_conditions(text, conditions, facts=facts)
    unresolved_pairs = [
        (index, condition)
        for index, condition in enumerate(conditions)
        if index not in rule_results
    ]

    def _attach_usage(result: dict, input_tokens: int, output_tokens: int) -> dict:
        result["_usage"] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        return result

    def _merge_conditions(model_payload: dict | None) -> dict:
        llm_conditions = []
        llm_company_name = None
        parse_warning = None
        raw_response = None
        if model_payload:
            llm_conditions = model_payload.get("conditions") or []
            llm_company_name = _normalize_company_name(model_payload.get("company_name"))
            parse_warning = model_payload.get("parse_warning")
            raw_response = model_payload.get("raw_response")

        merged_conditions: list[dict] = []
        llm_index = 0
        for idx, condition in enumerate(conditions):
            if idx in rule_results:
                merged_conditions.append(rule_results[idx])
                continue
            if llm_index < len(llm_conditions) and isinstance(llm_conditions[llm_index], dict):
                item = dict(llm_conditions[llm_index])
            else:
                item = {
                    "condition": condition,
                    "result": False,
                    "evidence": _DEFAULT_EVIDENCE,
                }
            item["condition"] = condition
            item.setdefault("result", False)
            item.setdefault("evidence", _DEFAULT_EVIDENCE)
            item["source"] = "llm"
            merged_conditions.append(item)
            llm_index += 1

        summary = {
            "total": len(conditions),
            "rule_count": len(rule_results),
            "llm_count": len(unresolved_pairs),
            "llm_skipped": len(unresolved_pairs) == 0,
        }
        company_name = llm_company_name or extracted_facts.get("company_name")
        enriched_facts = _apply_company_identity(extracted_facts, company_name)
        result = {
            "company_name": enriched_facts.get("company_name"),
            "company_group_name": enriched_facts.get("company_group_name"),
            "company_group_key": enriched_facts.get("company_group_key"),
            "conditions": merged_conditions,
            "condition_summary": summary,
            "detected_facts": enriched_facts,
        }
        if parse_warning:
            result["parse_warning"] = parse_warning
        if raw_response:
            result["raw_response"] = raw_response
        return result

    if not unresolved_pairs:
        return _attach_usage(_merge_conditions(None), 0, 0)

    import boto3

    unresolved_conditions = [condition for _, condition in unresolved_pairs]
    cond_list = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(unresolved_conditions))
    doc_text = text[:_MAX_DOC_CHARS]

    facts_lines: list[str] = []
    if extracted_facts.get("company_name"):
        facts_lines.append(f"- 기업명 후보: {extracted_facts['company_name']}")
    if extracted_facts.get("establishment_date"):
        facts_lines.append(
            f"- 설립/개업일: {extracted_facts['establishment_date']} (업력 {extracted_facts.get('business_age_years')}년)"
        )
    revenue_candidates = extracted_facts.get("revenue_candidates")
    if isinstance(revenue_candidates, list):
        for candidate in revenue_candidates[:3]:
            if not isinstance(candidate, dict):
                continue
            snippet = str(candidate.get("snippet") or "")
            year = candidate.get("year")
            prefix = f"{year}년 " if isinstance(year, int) else ""
            facts_lines.append(f"- {prefix}매출 후보: {candidate.get('display')} / {snippet}")
    facts_block = "\n".join(facts_lines) or "- 별도 구조화 팩트 없음"

    prompt = f"""\
다음 문서 내용을 읽고 각 조건의 충족 여부를 판단하세요.

=== 판단 조건 ===
{cond_list}

=== 구조화 팩트 (참고) ===
{facts_block}

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
    parsed = _parse_model_output(raw, unresolved_conditions)
    return _attach_usage(_merge_conditions(parsed), _usage["input_tokens"], _usage["output_tokens"])


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
