"""Validated application configuration loaded from environment variables."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ConfigurationError(ValueError):
    """Raised when the application configuration is invalid."""


@dataclass(frozen=True)
class ApiKeyConfig:
    """A configured credential and its safe-to-log slot number."""

    slot: int
    key: str


@dataclass(frozen=True)
class Settings:
    api_keys: tuple[ApiKeyConfig, ...]
    model: str
    base_url: str
    timeout: float
    max_context_tokens: int
    max_history_messages: int
    max_tool_output_chars: int
    max_file_size: int
    max_file_list_items: int
    max_output_lines: int
    reserve_response_tokens: int
    max_api_attempts: int
    rate_limit_cooldown_seconds: float
    temporary_failure_cooldown_seconds: float

    @property
    def api_key(self) -> str:
        """Compatibility accessor for legacy code; new code must use ``api_keys``."""
        return self.api_keys[0].key

    @property
    def reserve_response_tokes(self) -> int:
        """Compatibility accessor for the former misspelled setting name."""
        return self.reserve_response_tokens


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} must be set.")
    return value


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer.") from error
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero.")
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a number.") from error
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero.")
    return value


def _positive_int_with_legacy_name(name: str, legacy_name: str, default: int) -> int:
    """Read ``name``, falling back to one legacy environment variable name."""
    if os.getenv(name) is not None:
        return _positive_int(name, default)
    return _positive_int(legacy_name, default)


def _load_api_keys() -> tuple[ApiKeyConfig, ...]:
    keys = tuple(
        ApiKeyConfig(slot=slot, key=value)
        for slot in range(1, 6)
        if (value := os.getenv(f"GROQ_API_KEY{slot}", "").strip())
    )
    if not keys:
        raise ConfigurationError(
            "At least one of GROQ_API_KEY1 through GROQ_API_KEY5 must be set."
        )
    configured_slots = {key.slot for key in keys}
    missing_slots = [str(slot) for slot in range(1, 6) if slot not in configured_slots]
    if missing_slots:
        logger.warning("Groq API key slots not configured: %s", ", ".join(missing_slots))
    return keys


def get_settings() -> Settings:
    """Return immutable, validated settings. One to five key slots are supported."""
    return Settings(
        api_keys=_load_api_keys(),
        model=_required("GROQ_MODEL"),
        base_url=_required("GROQ_BASE_URL"),
        timeout=_positive_float("GROQ_TIMEOUT", 60.0),
        max_context_tokens=_positive_int("DEFAULT_MAX_CONTEXT_TOKENS", 6000),
        max_history_messages=_positive_int("DEFAULT_MAX_HISTORY_MESSAGES", 20),
        max_tool_output_chars=_positive_int("DEFAULT_MAX_TOOL_OUTPUT_CHARS", 3000),
        max_file_size=_positive_int("DEFAULT_MAX_FILE_SIZE", 10000),
        max_file_list_items=_positive_int_with_legacy_name(
            "DEFAULT_MAX_FILE_LIST_ITEMS", "DEFAULT_MAX_LIST_ITEMS", 50
        ),
        max_output_lines=_positive_int("DEFAULT_MAX_OUTPUT_LINES", 100),
        reserve_response_tokens=_positive_int("DEFAULT_RESERVE_RESPONSE_TOKENS", 1000),
        max_api_attempts=_positive_int("GROQ_MAX_API_ATTEMPTS", 5),
        rate_limit_cooldown_seconds=_positive_float("GROQ_RATE_LIMIT_COOLDOWN_SECONDS", 60.0),
        temporary_failure_cooldown_seconds=_positive_float(
            "GROQ_TEMPORARY_FAILURE_COOLDOWN_SECONDS", 5.0
        ),
    )
