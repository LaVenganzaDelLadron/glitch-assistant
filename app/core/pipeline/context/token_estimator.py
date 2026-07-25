"""Token estimation utility — estimates token counts for messages and strings.

Provides a :class:`TokenEstimator` that estimates the number of tokens in
a message list or a plain string.  The estimator uses a simple character‑based
heuristic (chars / 4) when no actual tokenizer is available, which is
sufficient for pre‑flight budgeting.

Usage::

    estimator = TokenEstimator()
    tokens = estimator.estimate_tokens(messages)
    tokens = estimator.estimate_string_tokens("Hello, world!")
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default estimation factor: characters per token.
# For most LLMs (especially OpenAI-compatible APIs), a good rule of thumb
# is ~4 characters per token for English text.
_DEFAULT_CHARS_PER_TOKEN = 4.0

# Per‑message overhead (role, metadata, structural tokens).
_MESSAGE_OVERHEAD = 4  # ~4 tokens per message for {"role": "...", "content": "..."}


class TokenEstimator:
    """Estimates token usage of messages and strings.

    Uses a configurable characters‑per‑token ratio.  The default (4.0) works
    well for English and most programming languages.
    """

    def __init__(self, chars_per_token: float = _DEFAULT_CHARS_PER_TOKEN) -> None:
        """Initialize the estimator.

        Args:
            chars_per_token: Number of characters that count as one token.
                             Lower values = more conservative (safer) estimates.
        """
        self._chars_per_token = chars_per_token
        logger.debug("TokenEstimator initialized (%.2f chars/token)", chars_per_token)

    @property
    def chars_per_token(self) -> float:
        """Return the current characters‑per‑token ratio."""
        return self._chars_per_token

    def estimate_string_tokens(self, text: str | None) -> int:
        """Estimate the token count for a single string.

        Args:
            text: The string to estimate.  ``None`` and empty strings return 0.

        Returns:
            Estimated number of tokens.
        """
        if not text:
            return 0
        return max(1, int(len(text) / self._chars_per_token))

    def estimate_messages_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Estimate the total token count for a list of message dicts.

        Each message is assumed to have at least a ``role`` and ``content``
        key.  The estimate adds a small per‑message overhead to account for
        structural tokens.

        Args:
            messages: A list of message dicts (``{"role": str, "content": str}``).

        Returns:
            Estimated total number of tokens.
        """
        total = 0
        for msg in messages:
            # Count role tokens
            role = msg.get("role", "")
            total += self.estimate_string_tokens(role)

            # Count content tokens
            content = msg.get("content", "")
            total += self.estimate_string_tokens(content)

            # Count name / function_call if present
            name = msg.get("name", "")
            if name:
                total += self.estimate_string_tokens(name)

            function_call = msg.get("function_call")
            if function_call:
                if isinstance(function_call, dict):
                    total += self.estimate_string_tokens(str(function_call))
                else:
                    total += self.estimate_string_tokens(function_call)

            tool_calls = msg.get("tool_calls")
            if tool_calls:
                total += self.estimate_string_tokens(str(tool_calls))

            # Add structural overhead per message
            total += _MESSAGE_OVERHEAD

        logger.debug("Estimated %d tokens across %d messages", total, len(messages))
        return total

    def estimate_dict_tokens(self, data: dict[str, Any]) -> int:
        """Estimate the token count for a dictionary by converting to string.

        Useful for estimating structured data like tool results.

        Args:
            data: The dictionary to estimate.

        Returns:
            Estimated number of tokens.
        """
        return self.estimate_string_tokens(str(data))

