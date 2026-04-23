#!/usr/bin/env python3
"""Bridge Merry diagnosis chat turns for the web app."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.vc_agent import VCAgent  # noqa: E402


def _safe_role(value: Any) -> str:
    if value in ("user", "assistant", "system"):
        return str(value)
    return "user"


def _safe_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _summarize_analysis(analysis: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not isinstance(analysis, dict) or not analysis.get("success"):
        return None

    scores = analysis.get("scores") or {}
    score_cards: List[Dict[str, Any]] = []
    for category, info in scores.items():
        if not isinstance(info, dict):
            continue
        score_cards.append({
            "category": str(category),
            "score": info.get("score"),
            "yesRatePct": info.get("yes_rate_pct"),
            "weight": info.get("weight"),
            "yes": info.get("yes"),
            "no": info.get("no"),
            "total": info.get("total"),
        })

    gaps = analysis.get("checklist", {}).get("gaps", []) if isinstance(analysis.get("checklist"), dict) else []
    sample_gaps = []
    for gap in gaps[:5]:
        if not isinstance(gap, dict):
            continue
        sample_gaps.append({
            "module": gap.get("module"),
            "question": gap.get("question"),
            "detail": gap.get("detail"),
        })

    company_info = analysis.get("company_info") or {}
    company_name = company_info.get("company_name") if isinstance(company_info, dict) else None

    return {
        "companyName": company_name,
        "sheets": analysis.get("sheets") or [],
        "gapCount": len(gaps),
        "scoreCards": score_cards,
        "sampleGaps": sample_gaps,
    }


async def _run(payload: Dict[str, Any]) -> Dict[str, Any]:
    agent = VCAgent(
        model=_safe_text(payload.get("model")) or "claude-opus-4-6",
        user_id=_safe_text(payload.get("userId")) or "diagnosis_web",
        member_name=_safe_text(payload.get("memberName")) or None,
        team_id=_safe_text(payload.get("teamId")) or None,
    )

    source_file_path = _safe_text(payload.get("sourceFilePath"))
    if source_file_path:
        agent.memory.add_file_analysis(source_file_path)

    history = payload.get("history") or []
    seeded_history = []
    for item in history:
        if not isinstance(item, dict):
            continue
        seeded_history.append({
            "role": _safe_role(item.get("role")),
            "content": _safe_text(item.get("content")),
        })
    agent.conversation_history = seeded_history

    text_parts: List[str] = []
    async for event in agent.chat_events(_safe_text(payload.get("prompt")), mode="diagnosis"):
        if getattr(event, "type", "") == "text":
            text_parts.append(getattr(event, "content", ""))

    assistant_text = "".join(text_parts).strip()
    latest_analysis = agent.context.get("last_analysis")
    latest_generated_files = agent.memory.session_metadata.get("generated_files") or []
    latest_generated_file = latest_generated_files[-1] if latest_generated_files else None

    return {
        "ok": True,
        "assistant_text": assistant_text,
        "analysis_summary": _summarize_analysis(latest_analysis),
        "latest_generated_file": latest_generated_file,
    }


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        result = asyncio.run(_run(payload))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:  # pragma: no cover - exercised through node bridge
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
