"""LLM generation wrapper — sends prompts to the LLM with context management.

Handles token estimation, history trimming, output compression, and automatic
retry on token limit errors through the :class:`ContextManager`.
"""

from __future__ import annotations
import logging
from typing import Any
from app.core.ai.llm_error import LLMError
from app.core.config.configuration_error import ConfigurationError
from app.core.config.settings import get_settings
from app.core.pipeline.context.context_manager import ContextManager

logger = logging.getLogger(__name__)

# Maximum number of retries on token limit errors.
_MAX_RETRIES = 1


def generate(
    prompt: str,
    history: list[dict[str, str]],
    tool_result: str | None = None,
    context_manager: ContextManager | None = None,
) -> str:
    """Send a prompt with conversation history to the LLM and return the response.

    The function uses the provided ``context_manager`` (or creates a default one)
    to estimate tokens, trim history, compress tool output, and ensure the
    request stays within the configured token budget.  If the API returns a
    token limit error, it retries once with a smaller context.

    Args:
        prompt: The current user input.
        history: A list of previous message dicts (role/content pairs).
        tool_result: Optional result from a tool execution to include in context.
        context_manager: An optional :class:`ContextManager` instance.  If not
                         provided, one is created from settings.

    Returns:
        The model's response text, stripped of leading/trailing whitespace.

    Raises:
        LLMError: If configuration is invalid, the dependency is missing, or
                  the API call fails after all retries.
    """
    if not prompt or not prompt.strip():
        raise LLMError("Prompt cannot be empty.")

    try:
        settings = get_settings()
    except ConfigurationError as error:
        raise LLMError(str(error)) from error

    try:
        from openai import APIError, OpenAI
    except ImportError as error:
        raise LLMError("MISSING DEPENDENCY: RUN 'pip install -r requirements.txt'.") from error

    # Create a ContextManager if none was provided
    if context_manager is None:
        context_manager = ContextManager(
            max_context_tokens=settings.max_context_tokens,
            max_history_messages=settings.max_history_messages,
            max_tool_output_chars=settings.max_tool_output_chars,
        )

    client = OpenAI(
        api_key=settings.api_key,
        base_url=settings.base_url,
        timeout=settings.timeout,
    )

    # Prepare context through the ContextManager
    messages = context_manager.prepare_context(
        messages=history,
        tool_output=tool_result,
        user_message=prompt,
    )

    logger.info(
        "Sending %d messages to model %s (estimated tokens: %d, limit: %d)",
        len(messages),
        settings.model,
        context_manager.estimate_tokens(messages),
        settings.max_context_tokens,
    )

    # Primary request with retry support
    return _do_generate(client, settings.model, messages, context_manager)


def _do_generate(
    client: Any,
    model: str,
    messages: list[dict[str, str]],
    context_manager: ContextManager,
    retry_count: int = 0,
) -> str:
    """Execute the LLM generation with optional retry on token limit errors.

    Args:
        client: The OpenAI client instance.
        model: Model identifier string.
        messages: The prepared message list.
        context_manager: The ContextManager for retry logic.
        retry_count: Current retry attempt number.

    Returns:
        The model's response text.

    Raises:
        LLMError: If the API call fails after all retries.
    """
    from openai import APIError

    try:
        response = client.chat.completions.create(
            messages=messages,
            model=model,
        )
        reply = response.choices[0].message.content.strip()
        logger.debug("Received response: %.120s...", reply)
        return reply

    except APIError as error:
        error_msg = str(error).lower()

        # Check if this is a token limit error (HTTP 413 or "request too large")
        is_token_error = (
            "413" in error_msg
            or "request too large" in error_msg
            or "token" in error_msg
            or "too many tokens" in error_msg
            or "context length" in error_msg
        )

        if is_token_error and retry_count < _MAX_RETRIES:
            logger.warning(
                "Token limit error (attempt %d/%d). Reducing context and retrying...",
                retry_count + 1,
                _MAX_RETRIES + 1,
            )

            # Log the error details
            logger.debug("Token limit error details: %s", error)

            # Aggressively reduce context
            reduced_messages = context_manager.handle_token_limit_error(messages)

            logger.info(
                "Retrying with reduced context: %d messages (estimated %d tokens)",
                len(reduced_messages),
                context_manager.estimate_tokens(reduced_messages),
            )

            return _do_generate(
                client=client,
                model=model,
                messages=reduced_messages,
                context_manager=context_manager,
                retry_count=retry_count + 1,
            )

        raise LLMError(f"API REQUEST FAILED: {error}") from error
