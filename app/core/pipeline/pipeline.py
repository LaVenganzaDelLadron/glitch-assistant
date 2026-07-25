"""Main pipeline — orchestrates input parsing, intent detection, tool use,
LLM generation, memory (with context management), and output formatting.
"""

from __future__ import annotations
import logging
from typing import Any

from app.core.pipeline.input import parser
from app.core.pipeline.memory import memory as memory_module
from app.core.pipeline.reasoning import thinker
from app.core.pipeline.output import formatter
from app.core.ai import groq
from app.core.pipeline.context import ContextManager
from app.core.config.settings import get_settings

logger = logging.getLogger(__name__)

# Global context manager instance (lazy-initialised).
_context_manager: ContextManager | None = None


def _get_context_manager() -> ContextManager:
    """Return a singleton :class:`ContextManager` configured from settings.

    Returns:
        A configured ContextManager instance.
    """
    global _context_manager
    if _context_manager is None:
        settings = get_settings()
        _context_manager = ContextManager(
            max_context_tokens=settings.max_context_tokens,
            max_history_messages=settings.max_history_messages,
            max_tool_output_chars=settings.max_tool_output_chars,
        )
        logger.debug(
            "Global ContextManager initialized (max_tokens=%d, max_history=%d)",
            settings.max_context_tokens,
            settings.max_history_messages,
        )
    return _context_manager


def run(user_input: str) -> str:
    """Process a user input through the full assistant pipeline.

    Steps:
        1. Parse / clean the input.
        2. Load conversation history from memory.
        3. Decide whether a tool should handle the input.
        4. If a tool is selected, execute it and capture the result.
        5. **ContextManager** prepares the context (trim, summarise, compress,
           estimate tokens).
        6. Send the prepared context to the LLM.
        7. Save the exchange to memory.
        8. Periodically prune history.
        9. Format and return the final response.

    Args:
        user_input: Raw text from the user.

    Returns:
        The assistant's formatted response string.
    """
    try:
        cleaned = parser.parse(user_input)

        # Load conversation history from memory
        history = memory_module.load()

        context_manager = _get_context_manager()

        # Log context metrics before processing
        logger.info(
            "Input: %d chars | History: %d messages | "
            "Estimated tokens (history): %d",
            len(cleaned),
            len(history),
            context_manager.estimate_tokens(history),
        )

        decision = thinker.decide(cleaned)

        tool_result: str | None = None
        if decision.use_tool and decision.tool:
            logger.info("Executing tool for: %.60s", cleaned)
            try:
                tool_result = decision.tool(cleaned)
                logger.info("Tool returned: %.200s...", tool_result)
            except Exception as exc:
                logger.exception("Tool execution failed")
                tool_result = f"Error: Tool execution failed — {exc}"

        # Prepare context — trim, summarise, compress, estimate
        prepared_messages = context_manager.prepare_context(
            messages=history,
            tool_output=tool_result,
            user_message=cleaned,
        )

        logger.info(
            "Context prepared: %d messages, estimated %d tokens",
            len(prepared_messages),
            context_manager.estimate_tokens(prepared_messages),
        )

        response = groq.generate(
            cleaned,
            history,
            tool_result,
            context_manager=context_manager,
        )

        # Save exchange to memory
        memory_module.save(cleaned, response)

        # Periodically prune history if it grows too large
        if memory_module.get_history_size() > 200:
            removed = memory_module.prune(keep_count=50)
            logger.info("Periodic history pruning: removed %d messages", removed)

        return formatter.format(response)

    except Exception as exc:
        logger.exception("Pipeline error")
        return f"I encountered an error: {exc}"
