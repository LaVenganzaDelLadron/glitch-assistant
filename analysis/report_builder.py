"""Report builder — parses LLM responses and populates AnalysisReport objects."""

from __future__ import annotations

import json
import logging
from typing import Any

from analysis.report import AnalysisReport, Issue, Recommendation, Strength

logger = logging.getLogger(__name__)


class ReportBuilder:
    """Parses LLM response JSON and builds an :class:`AnalysisReport`.

    Handles:
        - Valid JSON response
        - Invalid JSON (fallback to raw text as summary)
        - Partial data (fills missing fields with defaults)
    """

    def build(
        self,
        repo_id: str,
        clone_url: str,
        llm_response: str,
    ) -> AnalysisReport:
        """Build an :class:`AnalysisReport` from the LLM's response.

        Args:
            repo_id: The ``owner/repo`` identifier.
            clone_url: The clone URL used.
            llm_response: The LLM's raw response string (expected to be JSON).

        Returns:
            A populated :class:`AnalysisReport`.
        """
        report = AnalysisReport(
            repository=repo_id,
            clone_url=clone_url,
        )

        # Try to parse as JSON
        data = self._parse_json(llm_response)

        if data is None:
            # Failed to parse — use raw text as summary
            report.summary = llm_response
            report.score = 50
            logger.warning(
                "LLM response was not valid JSON; using as plain text summary "
                "(%d characters)",
                len(llm_response),
            )
            return report

        # Populate report fields from parsed data
        report.summary = data.get("summary", "")
        report.score = data.get("score", 50)
        report.languages = data.get("languages", {})

        # Issues
        for issue_data in data.get("issues", []):
            report.issues.append(Issue(
                category=issue_data.get("category", "general"),
                description=issue_data.get("description", ""),
                file=issue_data.get("file"),
                line=issue_data.get("line"),
                severity=issue_data.get("severity", "medium"),
            ))

        # Strengths
        for strength_data in data.get("strengths", []):
            report.strengths.append(Strength(
                category=strength_data.get("category", "general"),
                description=strength_data.get("description", ""),
            ))

        # Recommendations
        for rec_data in data.get("recommendations", []):
            report.recommendations.append(Recommendation(
                priority=rec_data.get("priority", "MEDIUM"),
                category=rec_data.get("category", "general"),
                description=rec_data.get("description", ""),
                details=rec_data.get("details", ""),
            ))

        # Categorized findings
        report.security = data.get("security", [])
        report.performance = data.get("performance", [])
        report.documentation = data.get("documentation", [])
        report.architecture = data.get("architecture", [])
        report.tests = data.get("tests", [])
        report.complexity = data.get("complexity", [])
        report.dependencies = data.get("dependencies", [])
        report.ci_cd = data.get("ci_cd", [])
        report.docker = data.get("docker", [])
        report.maintainability = data.get("maintainability", [])

        logger.info(
            "Built report for %s — score=%d, issues=%d, recommendations=%d",
            repo_id,
            report.score,
            len(report.issues),
            len(report.recommendations),
        )

        return report

    def _parse_json(self, text: str) -> dict[str, Any] | None:
        """
        Parse an LLM response into a JSON object.
        
        The response may contain raw JSON, JSON in a Markdown code block, or a
        JSON object embedded in surrounding text.
        
        Args:
            text: The LLM response text.
        
        Returns:
            The parsed JSON object, or ``None`` if no valid JSON object is found.
        """
        # Strategy 1: Direct parse
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from ```json ... ``` block
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start) if "```" in text[start:] else len(text)
            json_str = text[start:end].strip()
            try:
                data = json.loads(json_str)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        # Strategy 3: Extract from any ``` ... ``` block
        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            json_str = text[start:end].strip()
            try:
                data = json.loads(json_str)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        # Strategy 4: Look for first { ... } block
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            json_str = text[brace_start : brace_end + 1]
            try:
                data = json.loads(json_str)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse JSON from LLM response")
        return None

