from __future__ import annotations


class LLMError(RuntimeError):
    """Raised when the LLM cannot generate a response (e.g. API failure, missing config)."""
