"""GitHub client — extracts owner/repo identifiers from user input."""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

# Pattern to match GitHub URLs or bare owner/repo strings.
_REPO_PATTERN = re.compile(
    r"(?:https?://(?:www\.)?github\.com/)?([a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+)"
)


class GithubClient:
    """Minimal client that parses GitHub repository identifiers from text."""

    def extract_repo(self, text: str) -> str | None:
        """Extract an ``owner/repo`` identifier from the given text.

        Supports:
            - Full URLs: ``https://github.com/owner/repo``
            - Bare identifiers: ``owner/repo``
            - Natural language: ``"analyze my repo: https://github.com/owner/repo"``

        Args:
            text: A raw user input string.

        Returns:
            The ``owner/repo`` string (with ``.git`` suffix stripped), or ``None``
            if no match is found.
        """
        match = _REPO_PATTERN.search(text)
        if match:
            repo = match.group(1)
            # Strip trailing .git or .git/ suffix if present to avoid
            # double .git when build_clone_url appends it.
            if repo.endswith(".git"):
                repo = repo[:-4]
            elif repo.endswith(".git/"):
                repo = repo[:-5]
            logger.info("Extracted repository identifier: %s", repo)
            return repo
        logger.warning("Could not extract repository identifier from: %.60s…", text)
        return None

    def build_clone_url(self, repo: str) -> str:
        """Build an HTTPS clone URL from an owner/repo identifier.

        Args:
            repo: A repository identifier in ``owner/repo`` format.

        Returns:
            An HTTPS clone URL string.
        """
        return f"https://github.com/{repo}.git"

