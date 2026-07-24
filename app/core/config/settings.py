from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from app.core.config.configuration_error import ConfigurationError

_DEFAULT_MODEL = "openai/gpt-oss-20b"
_DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
_DEFAULT_TIMEOUT = 60.0


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    api_key: str
    model: str
    base_url: str
    timeout: float


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

    return Settings(
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout=timeout,
    )
