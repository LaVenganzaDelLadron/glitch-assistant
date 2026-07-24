"""Conversation history backed by an in-memory list and JSON file persistence."""

from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_HISTORY_DIR = Path.home() / ".glitch-assistant"
_HISTORY_FILE = _HISTORY_DIR / "history.json"
_MAX_HISTORY = 100  # maximum number of exchanges to keep


def _ensure_storage() -> None:
    """Create the history directory and file if they don't exist."""
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    if not _HISTORY_FILE.exists():
        _HISTORY_FILE.write_text("[]", encoding="utf-8")


def load() -> list[dict[str, str]]:
    """Load conversation history from the JSON file.

    Returns:
        A list of message dicts with ``role`` and ``content`` keys.
    """
    _ensure_storage()
    try:
        data = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            # Convert legacy flat format [user, assistant] → dict format
            converted: list[dict[str, str]] = []
            for entry in data:
                if isinstance(entry, list) and len(entry) == 2:
                    converted.append({"role": "user", "content": entry[0]})
                    converted.append({"role": "assistant", "content": entry[1]})
                elif isinstance(entry, dict):
                    converted.append(entry)
            return converted
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load history: %s", exc)
    return []


def save(user_input: str, assistant_response: str) -> None:
    """Append a user/assistant exchange to the history file.

    Args:
        user_input: The user's message.
        assistant_response: The assistant's reply.
    """
    history = load()
    history.append({"role": "user", "content": user_input})
    history.append({"role": "assistant", "content": assistant_response})

    # Trim to keep the most recent exchanges
    if len(history) > _MAX_HISTORY * 2:
        history = history[-(_MAX_HISTORY * 2):]

    _ensure_storage()
    try:
        _HISTORY_FILE.write_text(
            json.dumps(history, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error("Failed to save history: %s", exc)


def clear() -> None:
    """Erase all stored conversation history."""
    _ensure_storage()
    _HISTORY_FILE.write_text("[]", encoding="utf-8")
    logger.info("Conversation history cleared.")
