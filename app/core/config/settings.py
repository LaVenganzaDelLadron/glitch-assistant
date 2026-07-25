from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from app.core.config.configuration_error import ConfigurationError

_DEFAULT_MODEL = "openai/gpt-oss-20b"
_DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
_DEFAULT_TIMEOUT = 60.0

# ---- Context management defaults ----
_DEFAULT_MAX_CONTEXT_TOKENS = 6000
_DEFAULT_MAX_HISTORY_MESSAGES = 20
_DEFAULT_MAX_TOOL_OUTPUT_CHARS = 3000
_DEFAULT_MAX_FILE_SIZE = 10000
_DEFAULT_MAX_FILE_LIST_ITEMS = 50
_DEFAULT_MAX_OUTPUT_LINES = 100
_DEFAULT_RESERVE_RESPONSE_TOKENS = 1000


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables.

    Includes both LLM connection settings and context management limits
    to prevent token overflow.
    """

    # LLM connection
    api_key: str
    model: str
    base_url: str
    timeout: float

    # Context management limits
    max_context_tokens: int = _DEFAULT_MAX_CONTEXT_TOKENS
    max_history_messages: int = _DEFAULT_MAX_HISTORY_MESSAGES
    max_tool_output_chars: int = _DEFAULT_MAX_TOOL_OUTPUT_CHARS
    max_file_size: int = _DEFAULT_MAX_FILE_SIZE
    max_file_list_items: int = _DEFAULT_MAX_FILE_LIST_ITEMS
    max_output_lines: int = _DEFAULT_MAX_OUTPUT_LINES
    reserve_response_tokens: int = _DEFAULT_RESERVE_RESPONSE_TOKENS


def get_settings() -> Settings:
    """Load and validate the Groq settings from the environment.

    Returns:
        A frozen Settings dataclass populated with validated configuration.

    Raises:
        ConfigurationError: If required settings are missing or invalid.
    """
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ConfigurationError(
                "GROQ_API_KEY is required. Add it to your environment or .env file."
            )

    raw_timeout = os.getenv("GROQ_TIMEOUT")
    if raw_timeout is None:
        timeout = _DEFAULT_TIMEOUT
    else:
        try:
            timeout = float(raw_timeout)
        except ValueError as error:
            raise ConfigurationError(
                    "GROQ_TIMEOUT must be a number of seconds."
                ) from error
        if timeout <= 0:
            raise ConfigurationError("GROQ_TIMEOUT must be greater than zero.")

    model = os.getenv("GROQ_MODEL") or _DEFAULT_MODEL
    base_url = os.getenv("GROQ_BASE_URL") or _DEFAULT_BASE_URL

    # Load context management settings from environment with defaults
    max_context_tokens = int(
        os.getenv("MAX_CONTEXT_TOKENS", str(_DEFAULT_MAX_CONTEXT_TOKENS))
    )
    max_history_messages = int(
        os.getenv("MAX_HISTORY_MESSAGES", str(_DEFAULT_MAX_HISTORY_MESSAGES))
    )
    max_tool_output_chars = int(
        os.getenv("MAX_TOOL_OUTPUT_CHARS", str(_DEFAULT_MAX_TOOL_OUTPUT_CHARS))
    )
    max_file_size = int(
        os.getenv("MAX_FILE_SIZE", str(_DEFAULT_MAX_FILE_SIZE))
    )
    max_file_list_items = int(
        os.getenv("MAX_FILE_LIST_ITEMS", str(_DEFAULT_MAX_FILE_LIST_ITEMS))
    )
    max_output_lines = int(
        os.getenv("MAX_OUTPUT_LINES", str(_DEFAULT_MAX_OUTPUT_LINES))
    )
    reserve_response_tokens = int(
        os.getenv("RESERVE_RESPONSE_TOKENS", str(_DEFAULT_RESERVE_RESPONSE_TOKENS))
    )

    return Settings(
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout=timeout,
        max_context_tokens=max_context_tokens,
        max_history_messages=max_history_messages,
        max_tool_output_chars=max_tool_output_chars,
        max_file_size=max_file_size,
        max_file_list_items=max_file_list_items,
        max_output_lines=max_output_lines,
        reserve_response_tokens=reserve_response_tokens,
    )
