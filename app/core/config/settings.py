from __future__ import annotations
import os
from dataclasses import dataclass
from typing import cast
from dotenv import load_dotenv
from app.core.config.configuration_error import ConfigurationError


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    base_url: str
    timeout: float

def get_settings() -> Settings:
    """Load and validate the Groq settings from the environment."""
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ConfigurationError("GROQ_API_KEY is required. Add it to your environment or .env file.")

    timeout_value = cast(str, os.getenv("GROQ_TIMEOUT"))
    try:
        timeout = float(timeout_value)
    except ValueError as error:
        raise ConfigurationError("GROQ_TIMEOUT must be a number of seconds.") from error
    if timeout <= 0:
        raise ConfigurationError("GROQ_TIMEOUT must be greater than zero.")

    return Settings(api_key=api_key, model=cast(str, os.getenv("GROQ_MODEL")), base_url=cast(str, os.getenv("GROQ_BASE_URL")), timeout=timeout)
