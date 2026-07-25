"""GitHub analysis tool — wires up the full clone → scan → LLM analysis pipeline.

This module is called by the pipeline when a GitHub repository URL or
owner/repo identifier is detected. It:

1. Clones the repository locally
2. Indexes files, detects languages, scans dependencies
3. Runs security, complexity, documentation, and git analysis
4. Sends structured data to the LLM
5. Returns the analysis result as a JSON string

All command execution is handled by Python. The LLM only receives
structured data and generates the report.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from analysis.analyzer import RepoAnalyzer, AnalysisError

logger = logging.getLogger(__name__)


def analyze_repository(raw_input: str) -> str:
    """Analyze a GitHub repository by cloning it locally and using AI.

    Accepts the raw user input and automatically extracts the repository
    identifier (``owner/repo``) from URLs or plain text.

    This function is called by the pipeline tool dispatcher. It loads the
    LLM configuration from settings, initializes the :class:`RepoAnalyzer`,
    and returns the analysis report as a JSON string suitable for inclusion
    in the LLM context.

    Args:
        raw_input: User input that contains a GitHub repo URL or identifier.

    Returns:
        A JSON string containing the full analysis report, or an error JSON.
    """
    try:
        from app.core.config.settings import get_settings
        settings = get_settings()

        analyzer = RepoAnalyzer(
            llm_api_key=settings.api_key,
            llm_model=settings.model,
            llm_base_url=settings.base_url,
            llm_timeout=60 if isinstance(settings.timeout, (int, float)) else 60,
        )

        report = analyzer.analyze(raw_input)

        report_dict = report.to_dict()
        logger.info(
            "Analysis complete — score: %d/100, issues: %d, recommendations: %d",
            report_dict.get("score", 0),
            len(report_dict.get("issues", [])),
            len(report_dict.get("recommendations", [])),
        )

        result = {
            "analysis": report_dict,
            "summary": report_dict.get("summary", ""),
            "score": report_dict.get("score", 0),
            "suggestion": {
                "recommendations": report_dict.get("recommendations", []),
                "strengths": report_dict.get("strengths", []),
            },
        }

        return json.dumps(result, indent=2, ensure_ascii=False)

    except AnalysisError as exc:
        logger.error("Analysis failed: %s", exc)
        return json.dumps({
            "analysis": {"error": str(exc)},
            "summary": f"Analysis failed: {exc}",
            "score": 0,
            "suggestion": {"recommendations": [], "strengths": []},
        })
    except Exception as exc:
        logger.exception("Unexpected error during repository analysis")
        return json.dumps({
            "analysis": {"error": f"Unexpected error: {exc}"},
            "summary": f"An unexpected error occurred: {exc}",
            "score": 0,
            "suggestion": {"recommendations": [], "strengths": []},
        })

