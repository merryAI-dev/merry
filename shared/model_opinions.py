"""Multi-model opinion gathering (Claude, Gemini, Codex/OpenAI)."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Dict, List

from anthropic import Anthropic


DEFAULT_CLAUDE_MODEL = "claude-opus-4-5-20251101"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def _build_opinion_prompt(user_message: str, evidence: str) -> str:
    return f"""당신은 VC 투자심사 리뷰어입니다.
아래 근거를 바탕으로 투자 의견을 5~7개 불릿으로 요약하세요.
- 근거가 없는 내용은 추측하지 말고 "확인 필요"로 표시
- 과장/단정 금지
- 한국어로 작성

[사용자 요청]
{user_message}

[근거]
{evidence}
"""


def _call_claude(api_key: str, prompt: str, model: str) -> Dict[str, object]:
    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=700,
            system="You are a cautious VC reviewer. Return concise bullet points in Korean.",
            messages=[{"role": "user", "content": prompt}],
        )
        text_parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
        text = "\n".join(text_parts).strip()
        return {"success": True, "content": text, "model": model}
    except Exception as exc:
        return {"success": False, "error": str(exc), "model": model}


def _call_openai(api_key: str, prompt: str, model: str) -> Dict[str, object]:
    try:
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a cautious VC reviewer. Return concise bullet points in Korean."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 700,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        choices = body.get("choices", [])
        if not choices:
            return {"success": False, "error": "No choices returned", "model": model}
        text = choices[0].get("message", {}).get("content", "").strip()
        return {"success": True, "content": text, "model": model}
    except Exception as exc:
        return {"success": False, "error": str(exc), "model": model}


def gather_model_opinions(
    user_message: str,
    evidence: str,
    claude_api_key: str,
) -> List[Dict[str, object]]:
    prompt = _build_opinion_prompt(user_message, evidence)

    claude_model = os.getenv("CLAUDE_OPINION_MODEL", DEFAULT_CLAUDE_MODEL)
    openai_model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)

    results: List[Dict[str, object]] = []

    if claude_api_key:
        result = _call_claude(claude_api_key, prompt, claude_model)
        result["provider"] = "claude"
        results.append(result)
    else:
        results.append({"provider": "claude", "success": False, "error": "Claude API key missing", "model": claude_model})

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        result = _call_openai(openai_key, prompt, openai_model)
        result["provider"] = "codex"
        results.append(result)
    else:
        results.append({"provider": "codex", "success": False, "error": "OpenAI API key missing", "model": openai_model})

    return results
