"""Structured streaming output types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

AgentOutputType = Literal[
    "text",
    "tool_start",
    "tool_result",
    "tool_error",
    "info",
    # Teaming 관련 타입
    "checkpoint_required",  # Level 2: 사전 승인 필요
    "review_required",      # Level 3: 사후 검토 필요
    "checkpoint_resolved",  # Checkpoint 해결됨
]


@dataclass
class AgentOutput:
    """Structured streaming event."""

    type: AgentOutputType
    content: str
    data: Optional[Dict[str, Any]] = None
