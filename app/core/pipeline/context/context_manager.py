"""Context manager — orchestrates token estimation, history trimming,
summarization, output compression, and retry logic for the LLM pipeline.

This is the main entry point for all context management operations.
Usage::

    manager = ContextManager()
    safe_messages = manager.prepare_context(
        messages=history,
        system_prompt=system_prompt,
        tool_output=tool_result,
        user_message=user_input,
    )
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.pipeline.context.token_estimator import TokenEstimator
from app.core.pipeline.context.output_compressor import OutputCompressor
from app.core.pipeline.context.history_summarizer import HistorySummarizer

logger = logging.getLogger(__name__)

# Default context limits.
_DEFAULT_MAX_CONTEXT_TOKENS = 6000
_DEFAULT_MAX_HISTORY_MESSAGES = 20
_DEFAULT_RESERVE_RESPONSE_TOKENS = 1000  # Reserve room for the model's reply.


class ContextManager:
    """Intelligently manages conversation context to prevent token overflow.

    The manager:
    1. Trims history to the most recent N exchanges.
    2. Summarizes older history into a compact memory block.
    3. Compresses tool outputs.
    4. Estimates token usage and trims further if over budget.
    5. Provides retry logic for 413 errors.
    """

    def __init__(
        self,
        max_context_tokens: int = _DEFAULT_MAX_CONTEXT_TOKENS,
        max_history_messages: int = _DEFAULT_MAX_HISTORY_MESSAGES,
        max_tool_output_chars: int = 3000,
        max_file_list_items: int = 50,
        max_output_lines: int = 100,
        reserve_response_tokens: int = _DEFAULT_RESERVE_RESPONSE_TOKENS,
        llm_client: Any = None,
        llm_model: str = "",
    ) -> None:
        """Initialize the context manager.

        Args:
            max_context_tokens: Soft limit for total tokens sent to the LLM.
            max_history_messages: Max user+assistant exchanges to keep.
            max_tool_output_chars: Max characters for any tool output.
            max_file_list_items: Max items in a compressed file listing.
            max_output_lines: Max lines in a compressed command output.
            reserve_response_tokens: Tokens to reserve for the model's reply.
            llm_client: Optional LLM client for LLM‑powered summarization.
            llm_model: Model ID for LLM‑powered summarization.
        """
        self._max_context_tokens = max_context_tokens
        self._max_history_messages = max_history_messages
        self._reserve_response_tokens = reserve_response_tokens
        self._max_tool_output_chars = max_tool_output_chars

        self._estimator = TokenEstimator()
        self._compressor = OutputCompressor(
            max_output_chars=max_tool_output_chars,
            max_file_list_items=max_file_list_items,
            max_output_lines=max_output_lines,
        )
        self._summarizer = HistorySummarizer(
            llm_client=llm_client,
            model=llm_model,
        )

        logger.debug(
            "ContextManager initialized (max_tokens=%d, max_history=%d, reserve=%d)",
            max_context_tokens,
            max_history_messages,
            reserve_response_tokens,
        )

    def prepare_context(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        tool_output: str | None = None,
        user_message: str | None = None,
    ) -> list[dict[str, str]]:
        """Prepare the final message list for an LLM request.

        Applies trimming, summarization, compression, and token estimation
        in sequence. Logs all decisions for debugging.

        Args:
            messages: The conversation history (list of role/content dicts).
            system_prompt: Optional system prompt to prepend.
            tool_output: Optional tool result to include.
            user_message: The current user message to append.

        Returns:
            A list of messages ready to send to the LLM.
        """
        result = list(messages)

        # Step 1: Trim history
        result = self._trim_history(result)

        # Step 2: Summarize old history if needed
        result = self._summarize_old_history(result)

        # Step 3: Compress any tool outputs in existing messages
        result = self._compress_messages(result)

        # Step 4: Build the full message list
        full_messages: list[dict[str, str]] = []

        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})

        full_messages.extend(result)

        if tool_output:
            compressed_tool = self._compressor.compress_tool_output(tool_output)
            full_messages.append({
                "role": "system",
                "content": f"The user invoked a tool and received this result:\n{compressed_tool}",
            })

        if user_message:
            full_messages.append({"role": "user", "content": user_message})

        # Step 5: Estimate tokens and trim if needed
        full_messages = self._trim_to_fit(full_messages)

        return full_messages

    def _trim_history(
        self,
        messages: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Keep only the most recent exchanges, preserving the system prompt.

        Args:
            messages: Full message list.

        Returns:
            Trimmed message list.
        """
        if len(messages) <= self._max_history_messages * 2:
            return messages

        removed = len(messages) - self._max_history_messages * 2
        trimmed = messages[-(self._max_history_messages * 2):]

        logger.info(
            "Trimmed history: removed %d oldest messages (kept last %d)",
            removed,
            len(trimmed),
        )
        return trimmed

    def _summarize_old_history(
        self,
        messages: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Replace older messages with a summary if history is too long.

        Keeps a summary at the start of the list followed by recent messages.

        Args:
            messages: Currently trimmed message list.

        Returns:
            Messages with optional summary prepended.
        """
        if not self._summarizer.should_summarize(messages):
            return messages

        # Determine split point: keep last N exchanges, summarize the rest
        keep_count = self._max_history_messages
        if len(messages) <= keep_count * 2:
            return messages

        split = -(keep_count * 2)
        old_part = messages[:split]
        recent_part = messages[split:]

        summary = self._summarizer.summarize(old_part)

        summarized_messages: list[dict[str, str]] = [
            {"role": "system", "content": f"## Conversation Memory\n\n{summary}"},
        ]
        summarized_messages.extend(recent_part)

        logger.info(
            "Summarized %d old messages → memory block (%d chars)",
            len(old_part),
            len(summary),
        )
        return summarized_messages

    def _compress_messages(
        self,
        messages: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Compress tool outputs and large contents within messages.

        Args:
            messages: Message list to scan and compress.

        Returns:
            Messages with compressed content.
        """
        compressed = []
        for msg in messages:
            content = msg.get("content", "")
            if content and len(content) > self._max_tool_output_chars:
                # Check if this looks like a tool output or file content
                if self._looks_like_tool_output(content):
                    content = self._compressor.compress_tool_output(content)
                elif self._looks_like_file_content(content):
                    content = self._compressor.compress_string(content)
            compressed.append({"role": msg.get("role", "user"), "content": content})
        return compressed

    def _trim_to_fit(
        self,
        messages: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Trim messages until estimated tokens fit within the budget.

        Iteratively removes the oldest non‑system messages until the
        estimated token count is within the configured limit (minus
        reserved response tokens).

        Args:
            messages: The full message list.

        Returns:
            Messages trimmed to fit the token budget.
        """
        available_tokens = self._max_context_tokens - self._reserve_response_tokens
        if available_tokens <= 0:
            logger.warning(
                "Reserve response tokens (%d) exceeds max context (%d) — using 10%% reserve",
                self._reserve_response_tokens,
                self._max_context_tokens,
            )
            available_tokens = int(self._max_context_tokens * 0.9)

        # First estimate
        estimated = self._estimator.estimate_messages_tokens(messages)
        logger.info(
            "Estimated tokens: %d (limit: %d, reserve: %d, available: %d)",
            estimated,
            self._max_context_tokens,
            self._reserve_response_tokens,
            available_tokens,
        )

        if estimated <= available_tokens:
            return messages

        # Remove oldest non‑system messages until we fit
        trimmed_messages = list(messages)
        removed_count = 0
        while trimmed_messages and estimated > available_tokens:
            # Find the first non-system message to remove
            removed = False
            for i, msg in enumerate(trimmed_messages):
                if msg.get("role") != "system" and i > 0:  # Keep first system message
                    trimmed_messages.pop(i)
                    removed_count += 1
                    removed = True
                    break

            if not removed:
                # Only system messages left — force remove oldest
                if len(trimmed_messages) > 1:
                    trimmed_messages.pop(1)
                    removed_count += 1
                else:
                    break

            estimated = self._estimator.estimate_messages_tokens(trimmed_messages)

        logger.info(
            "Removed %d messages to fit token budget. Final estimate: %d tokens",
            removed_count,
            estimated,
        )
        return trimmed_messages

    def compress_tool_result(self, tool_result: str) -> str:
        """Compress a tool result string for inclusion in context.

        Args:
            tool_result: Raw tool output.

        Returns:
            Compressed tool output string.
        """
        return self._compressor.compress_tool_output(tool_result)

    def compress_file_list(self, files: list[dict[str, Any]]) -> str:
        """Compress a file list for inclusion in context.

        Args:
            files: List of file metadata dicts.

        Returns:
            Compressed file list string.
        """
        return self._compressor.compress_file_list(files)

    def estimate_tokens(self, messages: list[dict[str, str]]) -> int:
        """Estimate tokens for a list of messages.

        Args:
            messages: Message dicts.

        Returns:
            Estimated token count.
        """
        return self._estimator.estimate_messages_tokens(messages)

    def estimate_string_tokens(self, text: str) -> int:
        """Estimate tokens for a single string.

        Args:
            text: Input text.

        Returns:
            Estimated token count.
        """
        return self._estimator.estimate_string_tokens(text)

    def handle_token_limit_error(
        self,
        messages: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Handle a 413 / token limit error by aggressively reducing context.

        This is called as a retry mechanism when the API returns a token
        limit error. It:
        1. Halves the max context tokens.
        2. Trims more aggressively.
        3. Compresses tool outputs further.

        Args:
            messages: The messages that caused the error.

        Returns:
            Aggressively trimmed messages for retry.
        """
        logger.warning("Handling token limit error — aggressively reducing context")

        # Temporarily reduce limits
        original_max = self._max_context_tokens
        self._max_context_tokens = int(original_max * 0.6)
        self._reserve_response_tokens = int(self._reserve_response_tokens * 1.5)

        # Force more aggressive trimming
        trimmed = self._trim_to_fit(messages)

        # Reset limits
        self._max_context_tokens = original_max

        logger.info(
            "Token limit recovery: reduced from %d to %d messages, target %d tokens",
            len(messages),
            len(trimmed),
            int(original_max * 0.6),
        )
        return trimmed

    @staticmethod
    def _looks_like_tool_output(content: str) -> bool:
        """Heuristic check if content looks like a tool/command output.

        Args:
            content: The message content.

        Returns:
            ``True`` if it appears to be tool output.
        """
        indicators = [
            "Exit code:",
            "stdout:",
            "stderr:",
            "Command result:",
            "File contents:",
            "--- ",  # file separator
            "[TRUNCATED]",
            "finished with exit code",
        ]
        return any(indicator in content for indicator in indicators)

    @staticmethod
    def _looks_like_file_content(content: str) -> bool:
        """Heuristic check if content looks like file contents.

        Args:
            content: The message content.

        Returns:
            ``True`` if it appears to be file content.
        """
        # Long code blocks or structured data
        lines = content.split("\n")
        if len(lines) > 200:
            return True

        # Binary-like or base64 content
        if len(content) > 5000 and content.count("\n") < 10:
            return True

        return False

