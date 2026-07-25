"""AI agent module (deprecated — analysis is now handled by analysis.analyzer).

The iterative AI agent has been replaced by a modular pipeline where Python
owns all command execution. This module is kept for backward compatibility.
"""

from ai.agent import AIAgent, AgentError

__all__ = [
    "AIAgent",
    "AgentError",
]

