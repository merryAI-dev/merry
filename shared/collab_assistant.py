"""
Collaboration assistant using Claude for team insights.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from anthropic import Anthropic


DEFAULT_MODEL = "claude-opus-4-5-20251101"


def _extract_json(text: str) -> Dict[str, object]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON 블록을 찾을 수 없습니다.")
    return json.loads(text[start : end + 1])


def build_collab_brief(
    api_key: str,
    tasks: List[Dict[str, str]],
    docs: List[Dict[str, str]],
    events: List[Dict[str, str]],
    recent_comments: List[Dict[str, str]],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 900,
) -> Dict[str, object]:
    if not api_key:
        raise ValueError("API 키가 필요합니다.")

    system_prompt = (
        "You are a collaboration COO for a VC team. "
        "Return JSON only. Write in Korean. "
        "Provide concise, action-oriented guidance."
    )

    payload = {
        "tasks": tasks,
        "docs": docs,
        "events": events,
        "comments": recent_comments,
    }

    user_prompt = f"""
팀 데이터:
{json.dumps(payload, ensure_ascii=False)}

Output JSON schema:
{{
  "today_focus": ["..."],
  "task_risks": ["..."],
  "doc_gaps": ["..."],
  "required_docs": ["..."],
  "next_actions": ["..."],
  "questions": ["..."]
}}
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
