"""Structured analysis report model with JSON serialization."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Issue:
    """A single issue or problem found in the repository."""

    category: str  # e.g. "security", "complexity", "style"
    description: str
    file: str | None = None
    line: int | None = None
    severity: str = "medium"  # "low", "medium", "high", "critical"


@dataclass
class Strength:
    """A positive finding or strength of the repository."""

    category: str
    description: str


@dataclass
class Recommendation:
    """A prioritized recommendation."""

    priority: str  # "HIGH", "MEDIUM", "LOW"
    category: str
    description: str
    details: str = ""


@dataclass
class AnalysisReport:
    """Complete analysis report for a repository."""

    # Repository metadata
    repository: str = ""
    clone_url: str = ""

    # Summary
    summary: str = ""
    score: int = 0  # 0–100

    # Languages detected
    languages: dict[str, float] = field(default_factory=dict)

    # Findings
    issues: list[Issue] = field(default_factory=list)
    strengths: list[Strength] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)

    # Categorized findings
    security: list[str] = field(default_factory=list)
    performance: list[str] = field(default_factory=list)
    documentation: list[str] = field(default_factory=list)
    architecture: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    complexity: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    ci_cd: list[str] = field(default_factory=list)
    docker: list[str] = field(default_factory=list)
    maintainability: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the report to a JSON-serializable dict."""
        return {
            "summary": self.summary,
            "score": self.score,
            "repository": self.repository,
            "clone_url": self.clone_url,
            "languages": self.languages,
            "issues": [asdict(issue) for issue in self.issues],
            "strengths": [asdict(s) for s in self.strengths],
            "recommendations": [asdict(r) for r in self.recommendations],
            "security": self.security,
            "performance": self.performance,
            "documentation": self.documentation,
            "architecture": self.architecture,
            "tests": self.tests,
            "complexity": self.complexity,
            "dependencies": self.dependencies,
            "ci_cd": self.ci_cd,
            "docker": self.docker,
            "maintainability": self.maintainability,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize the report to a pretty-printed JSON string.

        Args:
            indent: Number of spaces for JSON indentation.

        Returns:
            A JSON string of the report.
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> AnalysisReport:
        """Deserialize a report from a JSON string.

        Args:
            json_str: A JSON string produced by :meth:`to_json`.

        Returns:
            An :class:`AnalysisReport` instance.
        """
        data = json.loads(json_str)
        report = cls(
            repository=data.get("repository", ""),
            clone_url=data.get("clone_url", ""),
            summary=data.get("summary", ""),
            score=data.get("score", 0),
            languages=data.get("languages", {}),
            security=data.get("security", []),
            performance=data.get("performance", []),
            documentation=data.get("documentation", []),
            architecture=data.get("architecture", []),
            tests=data.get("tests", []),
            complexity=data.get("complexity", []),
            dependencies=data.get("dependencies", []),
            ci_cd=data.get("ci_cd", []),
            docker=data.get("docker", []),
            maintainability=data.get("maintainability", []),
        )
        for issue_data in data.get("issues", []):
            report.issues.append(Issue(**issue_data))
        for strength_data in data.get("strengths", []):
            report.strengths.append(Strength(**strength_data))
        for rec_data in data.get("recommendations", []):
            report.recommendations.append(Recommendation(**rec_data))
        return report

