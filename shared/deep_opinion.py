"""
Deep opinion engine for investment review (Opus-only).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from anthropic import Anthropic


DEFAULT_MODEL = "claude-opus-4-5-20251101"


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


def _extract_json(text: str) -> Dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON 블록을 찾을 수 없습니다.")
    return json.loads(text[start : end + 1])


def generate_deep_investment_opinion(
    api_key: str,
    evidence_context: str,
    extra_context: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2200,
) -> Dict[str, Any]:
    if not api_key:
        raise ValueError("API 키가 필요합니다.")

    system_prompt = (
        "You are a senior investment reviewer. Use only provided evidence. "
        "If evidence is missing, mark the claim as UNVERIFIED. "
        "Return JSON only. Do not add any extra text."
    )

    user_prompt = f"""
Evidence snippets (E1..):
{evidence_context}

Additional context:
{extra_context or "none"}

Task:
Create a critical investment opinion using group-relative reasoning.
Include hallucination checks and impact analysis (carbon + IRIS+).

Output JSON schema:
{{
  "conclusion": {{
    "paragraphs": ["...","...","..."]  // 2-3 short paragraphs
  }},
  "core_case": {{
    "summary": "...",
    "points": [{{"point": "...", "evidence": ["E1","E2"]}}]
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

Constraints:
- Use evidence IDs whenever possible. If none, set evidence to [] and mark as UNVERIFIED in hallucination_check.
- Keep each list concise: 3-6 items max.
- Do not invent IRIS+ codes if unsure; use "IRIS+" as code and explain why.
"""

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
    return _extract_json(raw_text)
