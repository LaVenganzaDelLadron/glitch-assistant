"""Prompt builder — constructs structured context for the LLM analysis prompt."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Builds structured JSON context for the LLM analysis.

    The LLM receives ONLY structured data and a clear instruction to analyze it.
    No instructions to run commands or call tools are included.
    """

    def build_analysis_prompt(
        self,
        repo_id: str,
        languages: dict[str, float],
        file_index: list[dict[str, Any]],
        statistics: dict[str, Any],
        security: list[dict[str, Any]],
        complexity: list[dict[str, Any]],
        documentation: dict[str, Any],
        git_info: dict[str, Any],
        dependencies: list[dict[str, Any]],
    ) -> str:
        """Build a complete system + user prompt for the LLM.

        The prompt contains everything the LLM needs to produce a report
        without executing any commands.

        Args:
            repo_id: The ``owner/repo`` identifier.
            languages: Language distribution dict.
            file_index: The complete file index.
            statistics: Collected statistics.
            security: Security findings.
            complexity: Complexity findings.
            documentation: Documentation analysis.
            git_info: Git metadata and statistics.
            dependencies: Dependency file information.

        Returns:
            A formatted prompt string ready to send to the LLM.
        """
        # Build structured context
        context = self._build_structured_context(
            repo_id=repo_id,
            languages=languages,
            file_index=file_index,
            statistics=statistics,
            security=security,
            complexity=complexity,
            documentation=documentation,
            git_info=git_info,
            dependencies=dependencies,
        )

        system_prompt = (
            "You are an expert software engineer and code reviewer. "
            "Your task is to analyze a repository and produce a comprehensive, "
            "actionable report about its quality, structure, and potential improvements.\n\n"
            "You will receive structured repository data below. "
            "Analyze this data carefully and produce a detailed report.\n\n"
            "Focus on:\n"
            "1. Architecture & Organization\n"
            "2. Code Quality & Style\n"
            "3. Security Issues\n"
            "4. Documentation Quality\n"
            "5. Testing Coverage\n"
            "6. Complexity & Maintainability\n"
            "7. Dependency Management\n"
            "8. CI/CD & DevOps\n"
            "9. Performance Considerations\n\n"
            "Be thorough but practical. Focus on findings that provide real value.\n"
            "Output ONLY a JSON object with the following structure:\n"
            '{\n'
            '  "summary": "Overall analysis summary",\n'
            '  "score": 0-100,\n'
            '  "strengths": [{"category": "...", "description": "..."}],\n'
            '  "issues": [{"category": "...", "description": "...", "severity": "low|medium|high|critical", "file": "..."}],\n'
            '  "recommendations": [{"priority": "HIGH|MEDIUM|LOW", "category": "...", "description": "...", "details": "..."}],\n'
            '  "security": ["...", "..."],\n'
            '  "performance": ["...", "..."],\n'
            '  "documentation": ["...", "..."],\n'
            '  "architecture": ["...", "..."],\n'
            '  "tests": ["...", "..."],\n'
            '  "complexity": ["...", "..."],\n'
            '  "dependencies": ["...", "..."],\n'
            '  "ci_cd": ["...", "..."],\n'
            '  "docker": ["...", "..."],\n'
            '  "maintainability": ["...", "..."]\n'
            '}\n\n'
            "IMPORTANT: Return ONLY valid JSON. No markdown, no explanation, no code blocks."
        )

        user_prompt = (
            f"Please analyze this GitHub repository: {repo_id}\n\n"
            f"## Structured Repository Data\n\n"
            f"```json\n{json.dumps(context, indent=2, default=str)}\n```\n\n"
            f"Analyze the data above and produce your report as JSON following the format specified."
        )

        combined = f"{system_prompt}\n\n{user_prompt}"
        logger.debug(
            "Built analysis prompt (%d characters, %d context keys)",
            len(combined),
            len(context),
        )
        return combined

    def _build_structured_context(
        self,
        repo_id: str,
        languages: dict[str, float],
        file_index: list[dict[str, Any]],
        statistics: dict[str, Any],
        security: list[dict[str, Any]],
        complexity: list[dict[str, Any]],
        documentation: dict[str, Any],
        git_info: dict[str, Any],
        dependencies: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build the structured context dictionary for the LLM.

        Args:
            See :meth:`build_analysis_prompt`.

        Returns:
            A dict containing only structured data — no prompts or instructions.
        """
        # Summarize file index (don't include full content to keep context size manageable)
        file_summary = self._summarize_file_index(file_index)

        return {
            "repository": repo_id,
            "languages": languages,
            "statistics": statistics,
            "file_structure": file_summary,
            "security": security,
            "complexity": complexity,
            "documentation": documentation,
            "git": git_info,
            "dependencies": dependencies,
        }

    def _summarize_file_index(
        self, file_index: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Build a lightweight summary of the file index (without full content).

        Args:
            file_index: The complete file index (with content).

        Returns:
            A summary dict with:
                - ``total_files``: int
                - ``total_lines``: int
                - ``total_size_bytes``: int
                - ``directories``: list of top-level directories
                - ``file_list``: list of dicts with path, extension, size, lines (no content)
        """
        total_lines = 0
        total_size = 0
        directories: set[str] = set()
        file_list: list[dict[str, Any]] = []

        for f in file_index:
            total_lines += f.get("lines", 0)
            total_size += f.get("size", 0)
            path = f.get("path", "")

            # Extract top-level directory
            parts = path.split("/")
            if len(parts) > 1:
                directories.add(parts[0])

            file_list.append({
                "path": path,
                "extension": f.get("extension", ""),
                "size": f.get("size", 0),
                "lines": f.get("lines", 0),
            })

        return {
            "total_files": len(file_index),
            "total_lines": total_lines,
            "total_size_bytes": total_size,
            "directories": sorted(directories),
            "files": file_list,
        }

