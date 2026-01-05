"""
Deep opinion engine for investment review (Opus-only).
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any, Dict, List, Optional

from anthropic import Anthropic


DEFAULT_MODEL = "claude-opus-4-5-20251101"
DEFAULT_LENSES = [
    "Bull",
    "Bear",
    "Market",
    "Competitive",
    "Unit Economics",
    "Execution",
    "Deal Terms",
    "Regulatory",
    "Exit",
    "Governance",
]


def build_evidence_context(evidence: Optional[Dict[str, Any]], max_items: int = 12) -> str:
    if not evidence:
        return "EVIDENCE: none"
    items = evidence.get("evidence") or []
    if not items:
        return "EVIDENCE: none"

    lines: List[str] = []
    for idx, item in enumerate(items[:max_items], 1):
        text = (item.get("text") or "").strip()
        if not text:
            continue
        page = item.get("page")
        numbers = item.get("numbers") or []
        nums_text = ", ".join(numbers[:3]) if numbers else ""
        page_text = f"p{page}" if page else "p?"
        suffix = f" ({page_text}{', nums: ' + nums_text if nums_text else ''})"
        lines.append(f"E{idx}: {text}{suffix}")

    return "\n".join(lines) if lines else "EVIDENCE: none"


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        stripped = stripped.strip("`").strip()
    return stripped


def _repair_json_string(raw_json: str) -> str:
    # Remove trailing commas before closing brackets/braces.
    cleaned = re.sub(r",\s*([}\]])", r"\1", raw_json)
    return cleaned.strip()


def _try_parse_json(raw_json: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(raw_json)
        if isinstance(parsed, dict):
            return parsed
        return None
    except json.JSONDecodeError:
        pass

    try:
        parsed = ast.literal_eval(raw_json)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


def _repair_json_with_claude(api_key: str, model: str, raw_json: str) -> Optional[str]:
    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            system="You fix invalid JSON. Return JSON only. No markdown.",
            max_tokens=1200,
            messages=[{"role": "user", "content": raw_json}],
        )
        text_blocks = []
        for block in response.content:
            if getattr(block, "type", "") == "text":
                text_blocks.append(block.text)
        return "\n".join(text_blocks).strip()
    except Exception:
        return None


def _extract_json(text: str, api_key: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
    cleaned = _strip_code_fences(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON 블록을 찾을 수 없습니다.")
    snippet = cleaned[start : end + 1].strip()

    parsed = _try_parse_json(snippet)
    if parsed is not None:
        return parsed

    repaired = _repair_json_string(snippet)
    parsed = _try_parse_json(repaired)
    if parsed is not None:
        return parsed

    if api_key and model:
        fixed = _repair_json_with_claude(api_key, model, snippet)
        if fixed:
            fixed = _repair_json_string(fixed)
            parsed = _try_parse_json(fixed)
            if parsed is not None:
                return parsed

    raise ValueError("JSON 파싱 실패: 모델 출력이 JSON 형식이 아닙니다.")


def _call_opus(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    model: str,
    max_tokens: int,
) -> Dict[str, Any]:
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        system=system_prompt,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text_blocks = []
    for block in response.content:
        if getattr(block, "type", "") == "text":
            text_blocks.append(block.text)
    raw_text = "\n".join(text_blocks).strip()
    return _extract_json(raw_text, api_key=api_key, model=model)


def generate_lens_group(
    api_key: str,
    evidence_context: str,
    extra_context: str = "",
    lenses: Optional[List[str]] = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1800,
) -> Dict[str, Any]:
    if not api_key:
        raise ValueError("API 키가 필요합니다.")

    lenses = lenses or DEFAULT_LENSES
    lens_text = ", ".join(lenses)
    system_prompt = (
        "You are a critical but constructive investment reviewer. Return JSON only. "
        "Write in Korean. Use evidence IDs when available. "
        "If evidence is missing, provide conditional analysis with assumptions and information requests. "
        "Avoid absolute statements like 'cannot evaluate' or 'HOLD'."
    )
    user_prompt = f"""
Evidence snippets (E1..):
{evidence_context}

Additional context:
{extra_context or "none"}

Lenses: {lens_text}

Task:
Draft independent opinions for each lens. Each lens must include a summary and 3-5 points with evidence IDs.

Output JSON schema:
{{
  "lenses": [
    {{
      "lens": "Bull",
      "summary": "...",
      "points": [{{"point": "...", "evidence": ["E1"]}}]
    }}
  ]
}}
"""
    return _call_opus(api_key, system_prompt, user_prompt, model, max_tokens)


def cross_examine_and_score(
    api_key: str,
    evidence_context: str,
    lens_outputs: Dict[str, Any],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1600,
) -> Dict[str, Any]:
    if not api_key:
        raise ValueError("API 키가 필요합니다.")

    system_prompt = (
        "You are a skeptical but balanced reviewer. Return JSON only. "
        "Write in Korean. Score lenses relative to each other and apply clipping for stability. "
        "If evidence is missing, keep scores near neutral (raw_score=3, normalized=0, clipped=0) "
        "and focus on data gaps rather than conclusions."
    )
    user_prompt = f"""
Evidence snippets (E1..):
{evidence_context}

Lens outputs:
{json.dumps(lens_outputs, ensure_ascii=False)}

Task:
1) Cross-examine lenses and note weak assumptions.
2) Score each lens (raw 1-5), normalize to -1..1, then clip to -0.5..0.5.
3) Select core lenses (top 2 clipped scores) and dissent lens (lowest).
4) Summarize top 5 risks with evidence IDs.

Output JSON schema:
{{
  "scores": [
    {{"lens": "...", "raw_score": 3, "normalized": 0.2, "clipped": 0.2, "rationale": "..."}}
  ],
  "selected_core": ["..."],
  "selected_dissent": ["..."],
  "top_risks": [
    {{"risk": "...", "severity": "high|medium|low", "verification": "...", "evidence": ["E1"]}}
  ],
  "criticisms": [
    {{"lens": "...", "critique": "..."}}
  ]
}}
"""
    return _call_opus(api_key, system_prompt, user_prompt, model, max_tokens)


def generate_hallucination_check(
    api_key: str,
    evidence_context: str,
    lens_outputs: Dict[str, Any],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1200,
) -> Dict[str, Any]:
    if not api_key:
        raise ValueError("API 키가 필요합니다.")

    system_prompt = (
        "You are a verifier. Return JSON only. "
        "Write in Korean. Flag claims without evidence or with numeric inconsistency. "
        "Phrase missing evidence as 'needs verification' rather than invalid."
    )
    user_prompt = f"""
Evidence snippets (E1..):
{evidence_context}

Lens outputs:
{json.dumps(lens_outputs, ensure_ascii=False)}

Task:
List unverified claims (missing evidence IDs), numeric conflicts, and evidence gaps.

Output JSON schema:
{{
  "unverified_claims": [{{"claim": "...", "reason": "no evidence", "lens": "..."}}],
  "numeric_conflicts": ["..."],
  "evidence_gaps": ["..."]
}}
"""
    return _call_opus(api_key, system_prompt, user_prompt, model, max_tokens)


def generate_impact_analysis(
    api_key: str,
    evidence_context: str,
    lens_outputs: Dict[str, Any],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1400,
) -> Dict[str, Any]:
    if not api_key:
        raise ValueError("API 키가 필요합니다.")

    system_prompt = (
        "You are an impact analyst. Return JSON only. "
        "Write in Korean. Use evidence IDs when available; otherwise note gaps. "
        "If evidence is missing, set pathways to ['unknown'] and focus on gaps."
    )
    user_prompt = f"""
Evidence snippets (E1..):
{evidence_context}

Lens outputs:
{json.dumps(lens_outputs, ensure_ascii=False)}

Task:
Provide impact analysis (carbon + IRIS+). Avoid inventing IRIS+ codes.

Output JSON schema:
{{
  "carbon": {{
    "pathways": ["감축|회피|격리|unknown"],
    "metrics": [{{"metric": "...", "method": "...", "evidence": ["E1"]}}],
    "gaps": ["..."]
  }},
  "iris_plus": [
    {{"code": "IRIS+", "name": "...", "why": "...", "measurement": "...", "evidence": ["E2"]}}
  ]
}}
"""
    return _call_opus(api_key, system_prompt, user_prompt, model, max_tokens)


def synthesize_deep_opinion(
    api_key: str,
    evidence_context: str,
    lens_outputs: Dict[str, Any],
    scoring: Dict[str, Any],
    hallucination: Dict[str, Any],
    impact: Dict[str, Any],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2000,
) -> Dict[str, Any]:
    if not api_key:
        raise ValueError("API 키가 필요합니다.")

    system_prompt = (
        "You are a senior investment reviewer. Return JSON only. "
        "Write in Korean. Use evidence IDs; keep output concise and structured. "
        "If evidence is missing, produce a constructive, conditional conclusion focused on 자료 보강 요청. "
        "Avoid absolute recommendations or all-caps directives."
    )
    user_prompt = f"""
Evidence snippets (E1..):
{evidence_context}

Lens outputs:
{json.dumps(lens_outputs, ensure_ascii=False)}

Scoring summary:
{json.dumps(scoring, ensure_ascii=False)}

Hallucination check:
{json.dumps(hallucination, ensure_ascii=False)}

Impact analysis:
{json.dumps(impact, ensure_ascii=False)}

Task:
Synthesize a final critical opinion. Include 2-3 paragraph conclusion.

Output JSON schema:
{{
  "conclusion": {{
    "paragraphs": ["...","..."]
  }},
  "core_case": {{
    "summary": "...",
    "points": [{{"point": "...", "evidence": ["E1"]}}]
  }},
  "dissent_case": {{
    "summary": "...",
    "points": [{{"point": "...", "evidence": ["E3"]}}]
  }},
  "top_risks": [
    {{"risk": "...", "severity": "high|medium|low", "verification": "...", "evidence": ["E1"]}}
  ],
  "hallucination_check": {{
    "unverified_claims": [{{"claim": "...", "reason": "no evidence"}}],
    "numeric_conflicts": ["..."],
    "evidence_gaps": ["..."]
  }},
  "impact_analysis": {{
    "carbon": {{
      "pathways": ["감축|회피|격리|unknown"],
      "metrics": [{{"metric": "...", "method": "...", "evidence": ["E2"]}}],
      "gaps": ["..."]
    }},
    "iris_plus": [
      {{"code": "IRIS+", "name": "...", "why": "...", "measurement": "...", "evidence": ["E1"]}}
    ]
  }},
  "data_gaps": ["..."],
  "deal_breakers": ["..."],
  "go_conditions": ["..."],
  "next_actions": [{{"action": "...", "priority": "P0|P1|P2"}}]
}}
"""
    return _call_opus(api_key, system_prompt, user_prompt, model, max_tokens)
