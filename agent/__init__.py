"""VC Investment Agent SDK"""

from .vc_agent import VCAgent
from .tools import register_tools

# Backward compatibility
ConversationalVCAgent = VCAgent

__version__ = "0.3.0"  # Single Agent Architecture
__all__ = ["VCAgent", "ConversationalVCAgent", "register_tools"]
