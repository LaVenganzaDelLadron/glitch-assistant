"""Input parsing — cleans and normalises raw user input."""

from __future__ import annotations


def parse(user_input: str) -> str:
    """Strip extraneous whitespace from the user's input.

    Args:
        user_input: Raw text from the user.

    Returns:
        The trimmed input string.
    """
    return user_input.strip()
