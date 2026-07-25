from __future__ import annotations
import logging
from typing import Any
from app.core.ai.llm_error import LLMError
from app.core.config.configuration_error import ConfigurationError
from app.core.config.settings import get_settings

logger = logging.getLogger(__name__)


def generate(prompt: str, history: list[dict[str, str]], tool_result: str | None = None) -> str:
    """Send a prompt and conversation history to the language model.
    
    Args:
        prompt: The current user input.
        history: Previous conversation messages represented as role/content mappings.
        tool_result: Optional tool execution result to include in the conversation context.
    
    Returns:
        The model's response text with leading and trailing whitespace removed.
    
    Raises:
        LLMError: If the prompt is empty, configuration is invalid, the required
            dependency is unavailable, or the language model request fails.
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

    messages: list[dict[str, str]] = list(history)

    if tool_result:
        messages.append({
            "role": "system",
            "content": f"The user invoked a tool and received this result:\n{tool_result}",
        })

    messages.append({"role": "user", "content": prompt})

    print("Sending %d messages to model %s", len(messages), settings.model)

    try:
        client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.timeout,
        )
        response = client.chat.completions.create(
            messages=messages,
            model=settings.model,
        )
    except APIError as error:
        raise LLMError(f"GROQ REQUEST FAILED: {error}") from error

    reply = response.choices[0].message.content.strip()
    logger.debug("Received response: %.120s…", reply)
    return reply
