"""Intent classification — decides whether a tool should handle the input.

Uses regex pattern matching to detect:
    - GitHub repository URLs (https://github.com/owner/repo)
    - Bare owner/repo identifiers
    - Math expressions (calculate, compute, etc.)
"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)

# Regex patterns for GitHub repository detection.
_GITHUB_URL_PATTERN = re.compile(
    r"(?:https?://(?:www\.)?github\.com/)?([a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+)"
)

# Math trigger keywords.
_MATH_TRIGGERS = ("calculate", "compute", "evaluate", "what is", "what's")

# Repository analysis trigger keywords.
_REPO_TRIGGERS = ("scan", "analyze", "recommendation", "suggestion", "vulnerability")


@dataclass
class Decision:
    """Represents the system's decision about how to handle user input."""

    use_tool: bool = False
    tool: Callable[..., str | None] | None = field(default=None)


def decide(text: str) -> Decision:
    """Classify user intent and return the appropriate Decision.

    Uses regex to detect GitHub repositories, plus keyword matching for
    math expressions and analysis requests.

    Args:
        text: The cleaned user input string.

    Returns:
        A Decision indicating whether a tool should be invoked.
    """
    try:
        lower = text.strip().lower()

        # Check for GitHub URL using regex (most specific first)
        if _GITHUB_URL_PATTERN.search(text):
            from app.core.pipeline.tools import github_tool
            logger.info("GitHub repository detected via regex: %.60s", text)
            return Decision(use_tool=True, tool=github_tool.analyze_repository)

        # Check for owner/repo pattern (e.g., "facebook/react")
        if "/" in text and not text.startswith("http"):
            # Words before slash should be short (owner name)
            parts = text.split()
            for part in parts:
                if "/" in part and not part.startswith("/") and not part.endswith("/"):
                    owner, repo = part.split("/", 1)
                    if len(owner) <= 39 and len(repo) <= 39:  # GitHub limits
                        if any(c.isalnum() for c in owner) and any(c.isalnum() for c in repo):
                            if any(trigger in lower for trigger in _REPO_TRIGGERS):
                                from app.core.pipeline.tools import github_tool
                                logger.info("Owner/repo pattern detected: %s", part)
                                return Decision(use_tool=True, tool=github_tool.analyze_repository)

        # Check for repository analysis keywords
        if any(trigger in lower for trigger in _REPO_TRIGGERS):
            from app.core.pipeline.tools import github_tool
            logger.info("Repository analysis keyword detected")
            return Decision(use_tool=True, tool=github_tool.analyze_repository)

        # Check for math expressions
        if any(trigger in lower for trigger in _MATH_TRIGGERS):
            from app.core.pipeline.tools import calculator
            logger.info("Math expression detected")
            return Decision(use_tool=True, tool=calculator.execute)

        return Decision(use_tool=False)

    except Exception as exc:
        logger.exception("Error during intent classification")
        return Decision(use_tool=False)

