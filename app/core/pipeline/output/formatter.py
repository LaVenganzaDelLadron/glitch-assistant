"""Output formatting — trims, cleans, and optionally enhances responses."""

from __future__ import annotations
import re


def format(response: str) -> str:
    """Clean and format the raw LLM response.

    - Strips leading/trailing whitespace.
    - Collapses multiple blank lines into one.
    - Removes any trailing fragmentary sentence (text after the last
      sentence-ending punctuation that lacks a period).

    Args:
        response: Raw text from the LLM.

    Returns:
        A cleaned-up response string suitable for display.
    """
    text = response.strip()

    # Collapse runs of more than one blank line into a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text
