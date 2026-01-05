"""Structured streaming output types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

AgentOutputType = Literal["text", "tool_start", "tool_result", "tool_error", "info"]


@dataclass
class AgentOutput:
    """Structured streaming event."""

    type: AgentOutputType
    content: str
    data: Optional[Dict[str, Any]] = None
