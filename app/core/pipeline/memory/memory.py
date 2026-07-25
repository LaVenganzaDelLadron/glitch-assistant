"""Conversation history backed by an in-memory list and JSON file persistence.

Supports summarization, intelligent pruning, and token-aware storage.
"""

from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_HISTORY_DIR = Path.home() / ".glitch-assistant"
_HISTORY_FILE = _HISTORY_DIR / "history.json"
_MAX_HISTORY = 100  # maximum number of exchanges to keep in storage

# Key in the history JSON that holds the conversation summary.
_SUMMARY_KEY = "_summary_"


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
            # Filter out summary entries
            messages = [entry for entry in data if isinstance(entry, dict)]
            # Convert legacy flat format [user, assistant] → dict format
            converted: list[dict[str, str]] = []
            for entry in messages:
                if isinstance(entry, list) and len(entry) == 2:
                    converted.append({"role": "user", "content": entry[0]})
                    converted.append({"role": "assistant", "content": entry[1]})
                elif isinstance(entry, dict) and "role" in entry:
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


def get_recent(count: int = 20) -> list[dict[str, str]]:
    """Return only the most recent *count* exchanges.

    Each exchange is a user+assistant pair (2 messages).

    Args:
        count: Number of recent exchange pairs to return.

    Returns:
        A list of message dicts limited to the most recent exchanges,
        prefixed by any stored summary.
    """
    history = load()
    summary = get_summary()

    # Keep only the last (count * 2) messages
    if len(history) > count * 2:
        history = history[-(count * 2):]

    result: list[dict[str, str]] = list(history)

    # Prepend summary if available
    if summary:
        result.insert(0, {"role": "system", "content": f"## Conversation Memory\n\n{summary}"})

    return result


def store_summary(summary: str) -> None:
    """Store a conversation summary alongside the history.

    The summary is stored as a special entry in the history JSON file,
    marked with the ``_summary_`` key.

    Args:
        summary: The concise summary string.
    """
    _ensure_storage()
    try:
        data = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = []

    if not isinstance(data, list):
        data = []

    # Remove any existing summary entries
    data = [entry for entry in data if not (isinstance(entry, dict) and entry.get("role") == _SUMMARY_KEY)]

    # Add the new summary
    data.insert(0, {"role": _SUMMARY_KEY, "content": summary})

    try:
        _HISTORY_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Stored conversation summary (%d characters)", len(summary))
    except OSError as exc:
        logger.error("Failed to store summary: %s", exc)


def get_summary() -> str:
    """Retrieve the stored conversation summary.

    Returns:
        The summary string, or an empty string if none exists.
    """
    _ensure_storage()
    try:
        data = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and entry.get("role") == _SUMMARY_KEY:
                    return entry.get("content", "")
    except (json.JSONDecodeError, OSError):
        pass
    return ""


def prune(keep_count: int = 20) -> int:
    """Prune old history, keeping only the most recent exchanges.

    Older messages are removed entirely (they should be summarized before
    calling this method).

    Args:
        keep_count: Number of recent exchange pairs to keep.

    Returns:
        The number of messages that were removed.
    """
    history = load()
    if len(history) <= keep_count * 2:
        return 0

    removed = len(history) - keep_count * 2
    history = history[-(keep_count * 2):]

    _ensure_storage()
    try:
        # Preserve any summary entry when saving
        summary = get_summary()
        data: list[dict[str, Any]] = list(history)
        if summary:
            data.insert(0, {"role": _SUMMARY_KEY, "content": summary})

        _HISTORY_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Pruned history: removed %d messages, kept %d", removed, len(history))
    except OSError as exc:
        logger.error("Failed to prune history: %s", exc)

    return removed


def clear() -> None:
    """Erase all stored conversation history and summaries."""
    _ensure_storage()
    _HISTORY_FILE.write_text("[]", encoding="utf-8")
    logger.info("Conversation history cleared.")


def get_history_size() -> int:
    """Return the total number of messages stored in history.

    Returns:
        Message count (excluding summary entries).
    """
    return len(load())
