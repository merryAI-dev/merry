"""VC Investment Agent SDK.

Keep this module lightweight.

The worker imports modules under `agent.tools.*`. Importing heavy agent classes
eagerly here causes unnecessary dependency coupling (and breaks minimal worker
images). We provide lazy attribute access for backward compatibility.
"""

from __future__ import annotations

from typing import Any

__version__ = "0.3.0"  # Single Agent Architecture

__all__ = [
    "VCAgent",
    "ConversationalVCAgent",
    "InteractiveCriticAgent",
    "register_tools",
]


def __getattr__(name: str) -> Any:  # pragma: no cover
    if name in ("VCAgent", "ConversationalVCAgent"):
        from .vc_agent import VCAgent

        return VCAgent
    if name == "InteractiveCriticAgent":
        from .interactive_critic_agent import InteractiveCriticAgent

        return InteractiveCriticAgent
    if name == "register_tools":
        from .tools import register_tools

        return register_tools
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

