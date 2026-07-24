from __future__ import annotations
from app.core.ai.llm_error import LLMError
from app.core.config.configuration_error import ConfigurationError
from app.core.config.settings import get_settings


def generate(prompt: str, history, tool_result=None) -> str:
    if tool_result:
        raise LLMError("Prompt cannot be empty.")

    try:
        settings = get_settings()
    except ConfigurationError as error:
        raise LLMError(str(error)) from error

    try:
        from openai import APIError, OpenAI
    except ImportError as error:
        raise LLMError("MISSING DEPENDENCY: RUN 'pip install -r requirements.txt'.") from error

    try:
        client = OpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=settings.timeout)
        response = client.responses.create(input=prompt, model=settings.model)
    except APIError as error:
        raise LLMError(f"GROQ REQUEST FAILED: {error}") from error
    return response.output_text.strip()
