"""
Interactive Critic Agent (SDK-based).

Features:
- Multi-turn conversation with maintained history
- Multi-query internal workflow (evidence, opinion, critique)
- Critical review of explicit user feedback
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, AsyncIterator, Dict, List, Optional

from dotenv import load_dotenv

try:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock
    CLAUDE_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - runtime import guard
    CLAUDE_SDK_AVAILABLE = False

load_dotenv()

MAX_HISTORY_MESSAGES = 8
FEEDBACK_MARKERS = ("feedback:", "critique:", "review:", "fix:", "bug:")


class InteractiveCriticAgent:
    """SDK-based interactive agent with evidence, opinion, and critique output."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-opus-4-6",
        response_language: str = "Korean",
    ):
        if not CLAUDE_SDK_AVAILABLE:
            raise ImportError("claude_agent_sdk is required for InteractiveCriticAgent.")

        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY is required.")

        self.client = ClaudeSDKClient(
            options=ClaudeAgentOptions(
                model=model,
                setting_sources=["project"],
                allowed_tools=["Read", "Glob", "Grep"],
                permission_mode="acceptEdits",
            )
        )
        self.model = model
        self.response_language = response_language
        self.history: List[Dict[str, str]] = []
        self.connected = False
        self.context_text = ""

    async def connect(self) -> None:
        if not self.connected:
            await self.client.connect()
            self.connected = True

    async def close(self) -> None:
        if self.connected:
            await self.client.disconnect()
            self.connected = False

    def reset(self) -> None:
        self.history = []
        self.context_text = ""

    def set_context(self, context_text: str) -> None:
        self.context_text = context_text.strip()

    async def chat(self, user_message: str) -> AsyncIterator[str]:
        await self.connect()

        self.history.append({"role": "user", "content": user_message})
        self._trim_history()

        history_text = self._format_history()
        evidence = await self._query_json(self._build_evidence_prompt(history_text))
        opinion = await self._query_json(self._build_opinion_prompt(history_text, evidence))
        critique = None

        if self._looks_like_feedback(user_message):
            critique = await self._query_json(self._build_critique_prompt(history_text))

        response_text = self._render_response(evidence, opinion, critique)
        self.history.append({"role": "assistant", "content": response_text})
        self._trim_history()

        yield response_text

    def _trim_history(self) -> None:
        if len(self.history) > MAX_HISTORY_MESSAGES:
            self.history = self.history[-MAX_HISTORY_MESSAGES:]

    def _format_history(self) -> str:
        lines = []
        if self.context_text:
            lines.append(f"CONTEXT: {self.context_text}")
        for msg in self.history:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _looks_like_feedback(self, user_message: str) -> bool:
        text = user_message.strip().lower()
        return text.startswith(FEEDBACK_MARKERS)

    async def _query_text(self, prompt: str) -> str:
        await self.client.query(prompt)
        chunks: List[str] = []
        async for message in self.client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
        return "".join(chunks).strip()

    async def _query_json(self, prompt: str) -> Dict[str, Any]:
        text = await self._query_text(prompt)
        parsed = self._extract_json(text)
        if isinstance(parsed, dict):
            return parsed
        return {"raw": text}

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def _build_evidence_prompt(self, history_text: str) -> str:
        return f"""You are an analyst.
Extract evidence from the conversation only. Do not invent sources.
Use internal reasoning but do not reveal chain-of-thought.
Return JSON only. Do not include chain-of-thought.
Write in {self.response_language}.

Conversation:
{history_text}

Output JSON:
{{
  "evidence": [
    {{"statement": "...", "source": "user_input|assistant_response|tool_output"}}
  ],
  "assumptions": ["..."],
  "unknowns": ["..."]
}}
"""

    def _build_opinion_prompt(self, history_text: str, evidence: Dict[str, Any]) -> str:
        evidence_json = json.dumps(evidence, ensure_ascii=False, indent=2)
        return f"""You are a critical advisor.
Use the conversation and evidence to form an opinion and recommendation.
Include industry-specific cautions for industries mentioned.
Use internal reasoning but do not reveal chain-of-thought.
Return JSON only. Do not include chain-of-thought.
Write in {self.response_language}.

Conversation:
{history_text}

Evidence:
{evidence_json}

Output JSON:
{{
  "opinion": "...",
  "recommendation": "...",
  "pros": ["..."],
  "cons": ["..."],
  "risks": ["..."],
  "open_questions": ["..."],
  "industry_cautions": [
    {{"industry": "...", "cautions": ["..."]}}
  ]
}}
"""

    def _build_critique_prompt(self, history_text: str) -> str:
        return f"""You are a strict reviewer.
Critically evaluate the user's feedback. Be fair and precise.
Use internal reasoning but do not reveal chain-of-thought.
Return JSON only. Do not include chain-of-thought.
Write in {self.response_language}.

Conversation:
{history_text}

Output JSON:
{{
  "agree": ["..."],
  "concerns": ["..."],
  "needs_evidence": ["..."],
  "questions": ["..."]
}}
"""

    def _render_response(
        self,
        evidence: Dict[str, Any],
        opinion: Dict[str, Any],
        critique: Optional[Dict[str, Any]],
    ) -> str:
        lines: List[str] = []

        lines.append("### Evidence")
        for item in evidence.get("evidence", []):
            statement = item.get("statement")
            source = item.get("source")
            if statement:
                if source:
                    lines.append(f"- {statement} ({source})")
                else:
                    lines.append(f"- {statement}")
        for assumption in evidence.get("assumptions", []):
            lines.append(f"- Assumption: {assumption}")
        for unknown in evidence.get("unknowns", []):
            lines.append(f"- Unknown: {unknown}")

        lines.append("")
        lines.append("### Opinion")
        opinion_text = opinion.get("opinion")
        if opinion_text:
            lines.append(opinion_text)
        recommendation = opinion.get("recommendation")
        if recommendation:
            lines.append(f"- Recommendation: {recommendation}")
        for pro in opinion.get("pros", []):
            lines.append(f"- Pro: {pro}")
        for con in opinion.get("cons", []):
            lines.append(f"- Con: {con}")
        for risk in opinion.get("risks", []):
            lines.append(f"- Risk: {risk}")

        industry_cautions = opinion.get("industry_cautions", [])
        if industry_cautions:
            lines.append("")
            lines.append("### 유의점")
            for item in industry_cautions:
                if isinstance(item, dict):
                    industry = item.get("industry")
                    cautions = item.get("cautions", [])
                    if industry and cautions:
                        lines.append(f"- {industry}: " + "; ".join(cautions))
                    elif industry:
                        lines.append(f"- {industry}")
                    else:
                        for caution in cautions:
                            lines.append(f"- {caution}")
                elif isinstance(item, str):
                    lines.append(f"- {item}")

        open_questions = opinion.get("open_questions", [])
        if open_questions:
            lines.append("")
            lines.append("### Open Questions")
            for question in open_questions:
                lines.append(f"- {question}")

        if critique:
            lines.append("")
            lines.append("### Feedback Critique")
            for item in critique.get("agree", []):
                lines.append(f"- Agree: {item}")
            for item in critique.get("concerns", []):
                lines.append(f"- Concern: {item}")
            for item in critique.get("needs_evidence", []):
                lines.append(f"- Needs evidence: {item}")
            for item in critique.get("questions", []):
                lines.append(f"- Question: {item}")

        return "\n".join(lines).strip()
