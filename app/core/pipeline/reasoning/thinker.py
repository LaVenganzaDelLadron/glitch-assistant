"""Intent classification — decides whether a tool should handle the input."""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    """Represents the system's decision about how to handle user input."""

    use_tool: bool = False
    tool: Callable[..., str | None] | None = field(default=None)


def decide(text: str) -> Decision:
    """Classify user intent and return the appropriate Decision.

    Currently supports:
        - Expressions containing ``calculate``, ``compute``, ``evaluate``,
          or ``what is``/``what's`` → calculator tool.

    Args:
        text: The cleaned user input string.

    Returns:
        A Decision indicating whether a tool should be invoked, and if so
        which callable to use.
    """
    try:
        lower = text.strip().lower()
        # Trigger on common math-related keywords anywhere in the text
        math_triggers = ("calculate", "compute", "evaluate", "what is", "what's")
        if any(trigger in lower for trigger in math_triggers):
            from app.core.pipeline.tools import calculator

            return Decision(use_tool=True, tool=calculator.execute)
        return Decision(use_tool=False)
    except Exception as exc:
        logger.exception("Error during intent classification")
        return Decision(use_tool=False)
