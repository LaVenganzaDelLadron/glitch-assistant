"""GitHub analysis tool — wires up the full local clone → AI analysis pipeline."""

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
        # Load LLM settings from the application configuration
        from app.core.config.settings import get_settings
        settings = get_settings()

        analyzer = RepoAnalyzer(
            llm_api_key=settings.api_key,
            llm_model=settings.model,
            llm_base_url=settings.base_url,
            llm_timeout=settings.timeout,
        )

        report = analyzer.analyze(raw_input)

        # Serialize to dict
        report_dict = report.to_dict()
        logger.info(
            "Analysis complete — score: %d/100, issues: %d, recommendations: %d",
            report_dict.get("score", 0),
            len(report_dict.get("issues", [])),
            len(report_dict.get("recommendations", [])),
        )

        # Build a summarized result for the LLM
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

