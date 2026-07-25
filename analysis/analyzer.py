"""Repository analysis orchestrator — ties together cloning, scanning, AI agent, and reporting."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from analysis.prompts import SYSTEM_PROMPT, ANALYSIS_INSTRUCTIONS, build_file_index_prompt
from analysis.report import AnalysisReport
from app.github.client import GithubClient
from app.github.clone import RepoCloner, CloneError
from app.github.scanner import RepoScanner
from terminal.command_runner import CommandRunner, CommandResult, DangerousCommandError, TimeoutError
from ai.agent import AIAgent
from recommendation.suggester import RecommendationSuggester

logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Raised when the analysis pipeline encounters a fatal error."""


class RepoAnalyzer:
    """Orchestrates the full repository analysis pipeline.

    Steps:
        1. Extract repository identifier from user input.
        2. Clone the repository into a temporary directory.
        3. Scan the local file tree.
        4. Initialize an AI agent with file context and command capabilities.
        5. Run the AI agent to produce a structured report.
        6. Apply priority levels to recommendations.
        7. Return the final report.
    """

    def __init__(
        self,
        llm_api_key: str,
        llm_model: str = "openai/gpt-oss-20b",
        llm_base_url: str = "https://api.groq.com/openai/v1",
        llm_timeout: int = 120,
        command_timeout: int = 60,
        clone_timeout: int = 120,
    ) -> None:
        """Initialize the analyzer.

        Args:
            llm_api_key: API key for the LLM provider.
            llm_model: Model identifier string.
            llm_base_url: Base URL for the LLM API.
            llm_timeout: Timeout in seconds for LLM requests.
            command_timeout: Default timeout in seconds for terminal commands.
            clone_timeout: Timeout in seconds for git clone operations.
        """
        self._llm_api_key = llm_api_key
        self._llm_model = llm_model
        self._llm_base_url = llm_base_url
        self._llm_timeout = llm_timeout
        self._command_timeout = command_timeout
        self._clone_timeout = clone_timeout

        self._github_client = GithubClient()
        self._scanner = RepoScanner()
        self._command_runner = CommandRunner(timeout=command_timeout)
        self._suggester = RecommendationSuggester()

    def analyze(self, user_input: str) -> AnalysisReport:
        """Run the full analysis pipeline.

        Args:
            user_input: Raw user input containing a GitHub repository URL or identifier.

        Returns:
            A populated :class:`AnalysisReport` instance.

        Raises:
            AnalysisError: If the pipeline fails at any stage.
        """
        # Step 1: Extract repository
        repo_id = self._github_client.extract_repo(user_input)
        if repo_id is None:
            raise AnalysisError(
                "Could not extract a GitHub repository from the input. "
                "Please provide a URL like https://github.com/owner/repo "
                "or an identifier like 'owner/repo'."
            )

        clone_url = self._github_client.build_clone_url(repo_id)
        logger.info("Starting analysis of %s (%s)", repo_id, clone_url)

        # Step 2: Clone
        cloner = RepoCloner(timeout=self._clone_timeout)
        try:
            with cloner.clone(clone_url) as repo_path:
                report = self._analyze_cloned_repo(repo_id, clone_url, repo_path)
        except CloneError as exc:
            raise AnalysisError(f"Failed to clone repository: {exc}") from exc

        logger.info(
            "Analysis complete for %s — score: %d/100, %d recommendations",
            repo_id,
            report.score,
            len(report.recommendations),
        )
        return report

    def _analyze_cloned_repo(
        self,
        repo_id: str,
        clone_url: str,
        repo_path: Path,
    ) -> AnalysisReport:
        """Analyze a repository that has already been cloned to a local path.

        Args:
            repo_id: The ``owner/repo`` identifier.
            clone_url: The clone URL used.
            repo_path: Path to the cloned repository on disk.

        Returns:
            A fully populated :class:`AnalysisReport`.
        """
        # Step 3: Scan file tree
        logger.info("Scanning file tree: %s", repo_path)
        file_index = self._scanner.scan(repo_path)
        logger.info("Scanned %d files", len(file_index))

        # Step 4: Build file index prompt
        file_index_text = build_file_index_prompt(file_index)
        logger.debug("File index prompt built (%d characters)", len(file_index_text))

        # Step 5: Initialize AI agent
        agent = AIAgent(
            api_key=self._llm_api_key,
            model=self._llm_model,
            base_url=self._llm_base_url,
            timeout=self._llm_timeout,
            command_runner=self._command_runner,
            repo_path=repo_path,
        )

        # Step 6: Run the AI agent iteratively
        logger.info("Starting AI agent analysis…")
        analysis_result = agent.analyze(
            system_prompt=SYSTEM_PROMPT,
            analysis_instructions=ANALYSIS_INSTRUCTIONS,
            file_index=file_index,
            file_index_text=file_index_text,
        )
        logger.info("AI agent analysis completed")

        # Step 7: Build the report from the AI response
        report = self._build_report(repo_id, clone_url, analysis_result)

        # Step 8: Apply priority levels to recommendations
        report.recommendations = self._suggester.prioritize(report.recommendations)

        return report

    def _build_report(
        self,
        repo_id: str,
        clone_url: str,
        analysis_result: dict[str, Any] | str,
    ) -> AnalysisReport:
        """Build an :class:`AnalysisReport` from the AI agent's result.

        If the result is a string, it tries to parse it as JSON first,
        falling back to a minimal report with the raw text as summary.

        Args:
            repo_id: The ``owner/repo`` identifier.
            clone_url: The clone URL used.
            analysis_result: The AI agent's output — either a dict or a JSON string.

        Returns:
            A populated :class:`AnalysisReport`.
        """
        report = AnalysisReport(
            repository=repo_id,
            clone_url=clone_url,
        )

        # Parse the analysis result
        if isinstance(analysis_result, dict):
            data = analysis_result
        elif isinstance(analysis_result, str):
            try:
                data = json.loads(analysis_result)
            except json.JSONDecodeError:
                # If the AI didn't return valid JSON, use the raw text as summary
                report.summary = analysis_result
                report.score = 50
                logger.warning("AI output was not valid JSON; using as plain text summary")
                return report
        else:
            report.summary = str(analysis_result)
            report.score = 50
            return report

        # Populate report fields
        report.summary = data.get("summary", "")
        report.score = data.get("score", 50)
        report.languages = data.get("languages", {})

        # Issues
        for issue_data in data.get("issues", []):
            from analysis.report import Issue
            report.issues.append(Issue(
                category=issue_data.get("category", "general"),
                description=issue_data.get("description", ""),
                file=issue_data.get("file"),
                line=issue_data.get("line"),
                severity=issue_data.get("severity", "medium"),
            ))

        # Strengths
        for strength_data in data.get("strengths", []):
            from analysis.report import Strength
            report.strengths.append(Strength(
                category=strength_data.get("category", "general"),
                description=strength_data.get("description", ""),
            ))

        # Recommendations
        for rec_data in data.get("recommendations", []):
            from analysis.report import Recommendation
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

        return report

