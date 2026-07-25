import re

from app.github.client import GithubClient
from app.github.scanner import GithubScanner
from app.github.analyzer import RepoAnalyzer
from app.github.suggester import SuggestionGenerator

# Pattern to match GitHub URLs or bare owner/repo strings.
_REPO_PATTERN = re.compile(
    r"(?:https?://(?:www\.)?github\.com/)?([a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+)"
)


def _extract_repo(text: str) -> str | None:
    """Try to extract a ``owner/repo`` identifier from the given text.

    Supports:
        - Full URLs: ``https://github.com/owner/repo``
        - Bare identifiers: ``owner/repo``
        - Natural language: ``"analyze my repo: https://github.com/owner/repo"``

    Returns:
        The ``owner/repo`` string, or ``None`` if no match is found.
    """
    match = _REPO_PATTERN.search(text)
    if match:
        return match.group(1)
    return None


def analyze_repository(raw_input: str) -> dict | None:
    """Scan, analyze and suggest improvements for a GitHub repository.

    Accepts the raw user input and automatically extracts the repository
    identifier (``owner/repo``) from URLs or plain text.

    Args:
        raw_input: User input that contains a GitHub repo URL or identifier.

    Returns:
        A dict with ``analysis`` and ``suggestion`` keys, or ``None``
        when the input could not be parsed.
    """
    repo = _extract_repo(raw_input)
    if repo is None:
        return {
            "analysis": {"error": "Could not extract a GitHub repository from the input."},
            "suggestion": {"suggestions": []},
        }

    client = GithubClient()
    scanner = GithubScanner(client)
    analyzer = RepoAnalyzer()
    suggester = SuggestionGenerator()
    repository = scanner.scan(repo)
    analysis = analyzer.analyze(repository)
    suggestion = suggester.generate(analysis)

    return {
        "analysis": analysis,
        "suggestion": suggestion,
    }
