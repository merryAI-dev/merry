"""VC Investment Agent SDK"""

from .vc_agent import VCAgent
from .interactive_critic_agent import InteractiveCriticAgent
from .tools import register_tools

# Backward compatibility
ConversationalVCAgent = VCAgent

__version__ = "0.3.0"  # Single Agent Architecture
__all__ = ["VCAgent", "ConversationalVCAgent", "InteractiveCriticAgent", "register_tools"]
