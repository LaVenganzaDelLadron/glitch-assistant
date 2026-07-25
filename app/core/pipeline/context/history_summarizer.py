"""Conversation history summarization — condenses old exchanges into compact
memory summaries to keep context within token budgets.

Provides:
    - :class:`HistorySummarizer` — detects when summarization is needed and
      produces concise memory summaries using either the LLM or heuristic
      extraction.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Default threshold: number of exchanges (user+assistant pairs) before summarizing.
_DEFAULT_SUMMARIZE_THRESHOLD = 20

# Max characters for a summary string.
_DEFAULT_MAX_SUMMARY_CHARS = 500


class HistorySummarizer:
    """Summarizes old conversation history into compact memory blocks.

    Can operate in two modes:
    1. **LLM mode** — uses the configured LLM client to produce a natural
       language summary.
    2. **Heuristic mode** — extracts key topics and decisions using simple
       text analysis (useful when the LLM is unavailable or too expensive).
    """

    def __init__(
        self,
        summarize_threshold: int = _DEFAULT_SUMMARIZE_THRESHOLD,
        max_summary_chars: int = _DEFAULT_MAX_SUMMARY_CHARS,
        llm_client: Any = None,
        model: str = "",
    ) -> None:
        """Initialize the summarizer.

        Args:
            summarize_threshold: Number of exchanges before summarization triggers.
            max_summary_chars: Maximum characters for a generated summary.
            llm_client: Optional LLM client (e.g. an ``OpenAI`` instance) for
                        LLM‑powered summarization.
            model: Model identifier for LLM summarization.
        """
        self._summarize_threshold = summarize_threshold
        self._max_summary_chars = max_summary_chars
        self._llm_client = llm_client
        self._model = model
        logger.debug(
            "HistorySummarizer initialized (threshold=%d, max_chars=%d)",
            summarize_threshold,
            max_summary_chars,
        )

    @property
    def summarize_threshold(self) -> int:
        """Return the current summarization threshold."""
        return self._summarize_threshold

    def should_summarize(self, history: list[dict[str, str]]) -> bool:
        """Check if the history has grown enough to warrant summarization.

        Args:
            history: The full conversation history.

        Returns:
            ``True`` if the number of exchanges exceeds the threshold.
        """
        exchange_count = self._count_exchanges(history)
        needs = exchange_count > self._summarize_threshold
        if needs:
            logger.info(
                "History summarization recommended: %d exchanges (threshold: %d)",
                exchange_count,
                self._summarize_threshold,
            )
        return needs

    def summarize(
        self,
        history: list[dict[str, str]],
        max_chars: int | None = None,
    ) -> str:
        """Summarize a list of conversation messages into a compact string.

        If an LLM client is available, uses it for high‑quality summarization.
        Otherwise falls back to heuristic keyword extraction.

        Args:
            history: List of message dicts to summarize.
            max_chars: Maximum characters for the summary.

        Returns:
            A concise summary string.
        """
        limit = max_chars or self._max_summary_chars

        if not history:
            return ""

        if self._llm_client is not None and self._model:
            return self._llm_summarize(history, limit)

        return self._heuristic_summarize(history, limit)

    def _llm_summarize(
        self,
        history: list[dict[str, str]],
        max_chars: int,
    ) -> str:
        """Use the LLM to produce a summary of the conversation history.

        Args:
            history: Messages to summarize.
            max_chars: Maximum characters for the summary.

        Returns:
            A concise summary string.
        """
        # Build a compact representation of the history for summarization
        history_text = self._format_history_for_summary(history)

        summary_prompt = (
            "Summarize the following conversation into a concise memory that "
            "captures the user's goal, key decisions, and current state. "
            f"Keep it under {max_chars} characters.\n\n"
            f"Conversation:\n{history_text}\n\n"
            "Memory:"
        )

        try:
            response = self._llm_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a memory summarizer. Produce a concise, "
                            "informative summary of the conversation that "
                            "captures what the user is working on, what has "
                            "been done, and what remains."
                        ),
                    },
                    {"role": "user", "content": summary_prompt},
                ],
                model=self._model,
                temperature=0.2,
                max_tokens=300,
            )
            summary = response.choices[0].message.content.strip()
            if len(summary) > max_chars:
                summary = summary[:max_chars] + "..."
            logger.info(
                "LLM summary generated (%d characters)", len(summary)
            )
            return summary
        except Exception as exc:
            logger.warning(
                "LLM summarization failed, falling back to heuristic: %s", exc
            )
            return self._heuristic_summarize(history, max_chars)

    def _heuristic_summarize(
        self,
        history: list[dict[str, str]],
        max_chars: int,
    ) -> str:
        """Produce a summary using simple keyword and topic extraction.

        Extracts common topics, key phrases, and structural information
        from the conversation without calling the LLM.

        Args:
            history: Messages to summarize.
            max_chars: Maximum characters for the summary.

        Returns:
            A summary string.
        """
        user_messages: list[str] = []
        assistant_messages: list[str] = []
        topics: set[str] = set()
        key_phrases: list[str] = []

        # Important keywords that indicate topics
        topic_keywords = {
            "python", "javascript", "typescript", "react", "node", "api",
            "database", "docker", "kubernetes", "aws", "git", "github",
            "testing", "deployment", "security", "performance", "bug",
            "feature", "refactor", "documentation", "error", "install",
            "config", "setup", "migration", "optimization",
        }

        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user" and content:
                user_messages.append(content)
                # Extract topics
                words = set(re.findall(r"[a-zA-Z]\w+", content.lower()))
                topics.update(words & topic_keywords)

                # Extract potential key phrases (noun phrases)
                for match in re.finditer(
                    r"(?:the |a |an )?[A-Z]?[a-z]+ (?:is|was|has|needs|should|can|will) [^.]*\.",
                    content,
                ):
                    phrase = match.group(0).strip()
                    if len(phrase) > 20:
                        key_phrases.append(phrase)

            elif role == "assistant" and content:
                assistant_messages.append(content)

        # Build summary
        if not user_messages:
            return "No significant conversation history."

        # Determine primary topic from frequency
        topic_counts: dict[str, int] = {}
        for topic in topics:
            count = sum(
                content.lower().count(topic) for content in user_messages
            )
            topic_counts[topic] = count

        top_topics = sorted(topic_counts.items(), key=lambda x: -x[1])[:5]
        primary_focus = ", ".join(t for t, _ in top_topics) if top_topics else "general assistance"

        # Find the most recent user request
        last_user_msg = user_messages[-1][:150] if user_messages else ""

        # Count key items
        total_exchanges = len(user_messages)
        file_mentions = sum(
            1 for c in user_messages
            if re.search(r"file|code|script|function|class|module", c.lower())
        )
        error_mentions = sum(
            1 for c in user_messages
            if re.search(r"error|bug|issue|fail|problem", c.lower())
        )

        summary_parts: list[str] = []

        summary_parts.append(
            f"Conversation summary: The user is working on {primary_focus}."
        )

        if error_mentions > 2:
            summary_parts.append(
                f"Several ({error_mentions}) error‑related queries were discussed."
            )

        if file_mentions > 3:
            summary_parts.append(
                f"Topics included code/files ({file_mentions} mentions)."
            )

        summary_parts.append(
            f"Recent activity: {last_user_msg}"
        )

        summary = " | ".join(summary_parts)

        # Truncate if needed
        if len(summary) > max_chars:
            summary = summary[:max_chars].rsplit(" ", 1)[0] + "..."

        logger.info(
            "Heuristic summary generated (%d characters, %d exchanges, %d topics)",
            len(summary),
            total_exchanges,
            len(topics),
        )
        return summary

    @staticmethod
    def _format_history_for_summary(
        history: list[dict[str, str]],
    ) -> str:
        """Format conversation history compactly for LLM summarization.

        Args:
            history: Message dicts.

        Returns:
            A compact formatted string.
        """
        lines: list[str] = []
        for msg in history[-40:]:  # Only use recent messages
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # Truncate long messages
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)

    @staticmethod
    def _count_exchanges(history: list[dict[str, str]]) -> int:
        """Count the number of user+assistant exchange pairs.

        Args:
            history: Message dicts.

        Returns:
            Number of exchange pairs.
        """
        user_count = sum(1 for m in history if m.get("role") == "user")
        return user_count

