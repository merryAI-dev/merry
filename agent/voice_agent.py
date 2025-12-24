"""
Voice Agent for daily check-ins and 1:1 conversations
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

from .memory import ChatMemory


class VoiceAgent:
    """Lightweight voice-first conversational agent."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-5-20251101",
        user_id: Optional[str] = None,
    ):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY가 필요합니다.")

        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.user_id = user_id or "anonymous"

        self.conversation_history: List[Dict[str, str]] = []
        self.memory = ChatMemory(storage_dir="chat_history/voice", user_id=self.user_id)

    def _build_system_prompt(self, mode: str, last_checkin: Optional[str]) -> str:
        last_checkin_text = last_checkin or "없음"

        base = f"""당신은 사람처럼 자연스럽게 대화하는 음성 에이전트입니다.

목표:
- 짧고 명확한 문장으로 말합니다.
- 사용자의 감정과 톤을 반영합니다.
- 대화 흐름을 끊지 않고 질문을 2~4개씩 나눠서 합니다.

어제 기록(저장된 로그 기반):
{last_checkin_text}
"""

        if mode == "1on1":
            return base + """
현재 모드: 1:1

진행 방식:
1) 안부 인사 후, 최근 상황을 짧게 묻습니다.
2) 관계/협업 관점에서 핵심 이슈를 2~4개 질문합니다.
3) 대화가 끝나면 요약을 제공합니다.

요약 형식:
- 어제 로그 요약
- 학습 포인트
- 감정 상태
- 다음 액션 (3개 이하)

주의:
- 과장하지 말고, 불확실하면 질문으로 확인합니다.
- 한국어로 답변합니다.
"""

        if mode == "checkin":
            return base + """
현재 모드: 데일리 체크인

진행 방식:
1) 짧게 인사하고 오늘 컨디션을 물어봅니다.
2) 어제 로그가 있으면 2~4개의 근거를 언급하며 "학습"과 "감정"을 HCI 관점으로 설명합니다.
3) 오늘 목표/우선순위를 2~4개 질문으로 확인합니다.
4) 마지막에 요약을 제공합니다.

요약 형식:
- 어제 로그 요약
- 학습 포인트
- 감정 상태
- 오늘 목표/우선순위
- 다음 액션 (3개 이하)

주의:
- 감정 표현은 HCI 관점(사회적 존재감, 공감)에서 짧게 설명합니다.
- 한국어로 답변합니다.
"""

        return base + """
현재 모드: 자유 대화

규칙:
- 한 번에 너무 길게 말하지 않습니다.
- 필요하면 질문으로 맥락을 확인합니다.
- 한국어로 답변합니다.
"""

    def chat_sync(self, user_message: str, mode: str, last_checkin: Optional[str]) -> str:
        if not user_message:
            return ""

        system_prompt = self._build_system_prompt(mode, last_checkin)

        # message history
        messages = list(self.conversation_history)
        messages.append({"role": "user", "content": user_message})

        response = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            max_tokens=1200,
            messages=messages,
        )

        assistant_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                assistant_text += block.text

        # update history + memory
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": assistant_text})
        self.memory.add_message(
            "user",
            user_message,
            {"channel": "voice", "mode": mode},
        )
        self.memory.add_message(
            "assistant",
            assistant_text,
            {"channel": "voice", "mode": mode},
        )

        return assistant_text.strip()

    def _recent_conversation_text(self, limit: int = 6) -> str:
        items = self.conversation_history[-limit:]
        lines = []
        for msg in items:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content:
                continue
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def summarize_checkin_sync(self, mode: str, context_text: str) -> Dict[str, Any]:
        """Summarize check-in context into a structured JSON payload."""
        conversation = self._recent_conversation_text(limit=8)
        context_text = context_text or "none"

        system_prompt = """You produce a concise JSON summary for a daily check-in.
Return JSON only. Do not include markdown or extra text.
Use Korean for all string values.

Required keys:
- mode (string)
- yesterday_summary (string)
- learnings (array of strings)
- emotion_state (string)
- emotion_rationale (string)
- today_priorities (array of strings)
- next_actions (array of strings)

If unknown, use empty string or empty array."""

        user_prompt = f"""Context:\n{context_text}\n\nConversation:\n{conversation}\n\nReturn JSON now."""

        response = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            max_tokens=400,
            messages=[{"role": "user", "content": user_prompt}],
        )

        assistant_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                assistant_text += block.text

        parsed = self._extract_json(assistant_text)
        if not isinstance(parsed, dict):
            return {
                "mode": mode,
                "yesterday_summary": "",
                "learnings": [],
                "emotion_state": "",
                "emotion_rationale": "",
                "today_priorities": [],
                "next_actions": [],
            }

        parsed.setdefault("mode", mode)
        parsed.setdefault("learnings", [])
        parsed.setdefault("today_priorities", [])
        parsed.setdefault("next_actions", [])
        return parsed
