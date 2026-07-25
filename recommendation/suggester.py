"""Recommendation suggester — assigns priority levels and enhances recommendations."""

from __future__ import annotations

import logging
from typing import Sequence

from analysis.report import Recommendation

logger = logging.getLogger(__name__)

# Keywords that indicate HIGH priority findings.
_HIGH_PRIORITY_KEYWORDS: frozenset[str] = frozenset({
    "api key", "secret", "token", "password", "credential",
    "vulnerability", "cve", "security", "injection",
    "sql", "xss", "csrf", "rce",
    "remote code execution", "arbitrary code",
    "hardcoded", "plaintext",
    "authentication", "authorization", "permission",
    "encryption", "https", "ssl", "tls",
    "cross-site", "path traversal",
    "denial of service", "dos",
    "buffer overflow", "memory leak",
    "zero-day", "exploit",
})

# Keywords that indicate MEDIUM priority findings.
_MEDIUM_PRIORITY_KEYWORDS: frozenset[str] = frozenset({
    "test", "coverage", "unittest", "pytest",
    "complexity", "duplicate", "duplication",
    "lint", "style", "formatting", "pep8",
    "docstring", "documentation",
    "type hint", "typing",
    "error handling", "exception",
    "logging", "debug",
    "dependency", "outdated", "deprecated",
    "ci", "cd", "continuous integration",
    "docker", "container",
    "performance", "optimization", "bottleneck",
    "refactor", "maintainability",
})


class RecommendationSuggester:
    """Assigns priority levels (HIGH / MEDIUM / LOW) to recommendations.

    Uses keyword matching on the recommendation description to determine
    an appropriate priority level.
    """

    def prioritize(self, recommendations: Sequence[Recommendation]) -> list[Recommendation]:
        """Assign or adjust priority levels for a list of recommendations.

        Recommendations that already have a priority set will keep it unless
        it's empty. Unprioritized recommendations are classified based on
        keyword matching.

        Args:
            recommendations: A sequence of :class:`Recommendation` objects.

        Returns:
            A new list of :class:`Recommendation` objects with updated priorities.
        """
        prioritized: list[Recommendation] = []

        for rec in recommendations:
            # If priority is already explicitly set and not empty, keep it
            if rec.priority and rec.priority in ("HIGH", "MEDIUM", "LOW"):
                prioritized.append(rec)
                continue

            # Classify based on description + details
            combined = f"{rec.description} {rec.details}".lower()
            new_priority = self._classify(combined)

            prioritized.append(Recommendation(
                priority=new_priority,
                category=rec.category,
                description=rec.description,
                details=rec.details,
            ))

        # Sort: HIGH first, then MEDIUM, then LOW
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        prioritized.sort(key=lambda r: priority_order.get(r.priority, 3))

        logger.info(
            "Prioritized %d recommendations: %d HIGH, %d MEDIUM, %d LOW",
            len(prioritized),
            sum(1 for r in prioritized if r.priority == "HIGH"),
            sum(1 for r in prioritized if r.priority == "MEDIUM"),
            sum(1 for r in prioritized if r.priority == "LOW"),
        )

        return prioritized

    def _classify(self, text: str) -> str:
        """Classify a text description into a priority level.

        Args:
            text: Lowercased combined description and details text.

        Returns:
            ``"HIGH"``, ``"MEDIUM"``, or ``"LOW"``.
        """
        # Check HIGH priority keywords first
        for keyword in _HIGH_PRIORITY_KEYWORDS:
            if keyword in text:
                return "HIGH"

        # Check MEDIUM priority keywords
        for keyword in _MEDIUM_PRIORITY_KEYWORDS:
            if keyword in text:
                return "MEDIUM"

        # Default to LOW
        return "LOW"

