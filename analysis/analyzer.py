"""Repository analysis orchestrator — ties together cloning, scanning, statistics, and LLM reporting.

Pipeline:
    1. Extract repository identifier from user input.
    2. Clone the repository into a temporary directory.
    3. Index files and detect languages.
    4. Run security, complexity, documentation, and git analysis.
    5. Build structured context.
    6. Send context to LLM for analysis.
    7. Build and return the final report.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from analysis.report import AnalysisReport
from analysis.report_builder import ReportBuilder
from analysis.prompt_builder import PromptBuilder
from app.github.client import GithubClient
from scanner.repo_cloner import RepoCloner, CloneError
from scanner.file_indexer import FileIndexer
from scanner.language_detector import LanguageDetector
from scanner.dependency_detector import DependencyDetector
from security.security_scanner import SecurityScanner
from metrics.complexity import ComplexityAnalyzer
from metrics.documentation import DocumentationAnalyzer
from metrics.git_scanner import GitScanner
from terminal.command_runner import CommandRunner

logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Raised when the analysis pipeline encounters a fatal error."""


class StatisticsCollector:
    """Collects aggregate statistics from the file index and analysis results."""

    @staticmethod
    def collect(
        file_index: list[dict[str, Any]],
        languages: dict[str, float],
        git_info: dict[str, Any],
        documentation: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a statistics summary.

        Args:
            file_index: The complete file index.
            languages: Detected language distribution.
            git_info: Git metadata.
            documentation: Documentation analysis.

        Returns:
            A dict with aggregate statistics.
        """
        total_files = len(file_index)
        total_lines = sum(f.get("lines", 0) for f in file_index)
        total_size = sum(f.get("size", 0) for f in file_index)

        # Count by extension
        ext_counts: dict[str, int] = {}
        for f in file_index:
            ext = f.get("extension", "(unknown)")
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

        # Top 10 extensions
        top_exts = sorted(ext_counts.items(), key=lambda x: -x[1])[:10]

        has_tests = any(
            "test" in f.get("path", "").lower() or
            f.get("path", "").startswith("tests/") or
            f.get("path", "").startswith("test/")
            for f in file_index
        )

        stats = {
            "total_files": total_files,
            "total_lines": total_lines,
            "total_size_bytes": total_size,
            "total_size_kb": round(total_size / 1024, 1),
            "languages_detected": list(languages.keys()),
            "top_extensions": dict(top_exts),
            "has_tests": has_tests,
            "test_files_count": sum(
                1 for f in file_index
                if "test" in f.get("path", "").lower()
            ),
            "documentation_coverage": documentation.get("docstring_coverage", 0),
            "comment_density": documentation.get("comment_density", 0),
            "todo_count": documentation.get("todo_count", 0),
            "fixme_count": documentation.get("fixme_count", 0),
            "commit_count": git_info.get("commit_count", 0),
            "contributors": git_info.get("contributors", 0),
            "has_ci": documentation.get("has_ci", False),
            "has_docker": False,
        }

        logger.info(
            "Statistics collected: %d files, %d lines, %.1f KB, %d commits",
            stats["total_files"],
            stats["total_lines"],
            stats["total_size_kb"],
            stats["commit_count"],
        )
        return stats


class RepoAnalyzer:
    """Orchestrates the full repository analysis pipeline.

    All command execution is owned by Python modules. The LLM receives
    only structured data and generates analysis.
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
        self._command_runner = CommandRunner(timeout=command_timeout)
        self._file_indexer = FileIndexer()
        self._language_detector = LanguageDetector()
        self._dependency_detector = DependencyDetector()
        self._security_scanner = SecurityScanner()
        self._complexity_analyzer = ComplexityAnalyzer()
        self._documentation_analyzer = DocumentationAnalyzer()
        self._git_scanner = GitScanner(command_runner=self._command_runner)
        self._prompt_builder = PromptBuilder()
        self._report_builder = ReportBuilder()
        self._statistics_collector = StatisticsCollector()

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

        # Step 2: Clone repository
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

        Python owns all command execution. The LLM only receives structured data.

        Args:
            repo_id: The ``owner/repo`` identifier.
            clone_url: The clone URL used.
            repo_path: Path to the cloned repository on disk.

        Returns:
            A fully populated :class:`AnalysisReport`.
        """
        # Step 3: Index files
        logger.info("Indexing files: %s", repo_path)
        file_index = self._file_indexer.scan(repo_path)
        logger.info("Indexed %d files", len(file_index))

        # Step 4: Detect languages
        logger.info("Detecting languages...")
        languages = self._language_detector.detect(file_index)

        # Step 5: Detect dependencies
        logger.info("Detecting dependencies...")
        dependencies = self._dependency_detector.detect(repo_path)

        # Step 6: Run security scan
        logger.info("Running security scan...")
        security = self._security_scanner.scan(repo_path, file_index)

        # Step 7: Run complexity analysis
        logger.info("Analyzing complexity...")
        complexity = self._complexity_analyzer.analyze(repo_path, file_index)

        # Step 8: Analyze documentation
        logger.info("Analyzing documentation...")
        documentation = self._documentation_analyzer.analyze(repo_path, file_index)

        # Step 9: Gather git statistics
        logger.info("Gathering git statistics...")
        git_info = self._git_scanner.scan(repo_path)

        # Step 10: Collect aggregate statistics
        logger.info("Collecting statistics...")
        statistics = self._statistics_collector.collect(
            file_index=file_index,
            languages=languages,
            git_info=git_info,
            documentation=documentation,
        )

        # Step 11: Build structured context and send to LLM
        logger.info("Building prompt and sending to LLM...")
        prompt = self._prompt_builder.build_analysis_prompt(
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

        llm_response = self._call_llm(prompt)

        # Step 12: Build report from LLM response
        logger.info("Building final report...")
        report = self._report_builder.build(
            repo_id=repo_id,
            clone_url=clone_url,
            llm_response=llm_response,
        )

        # Add analysis metadata
        report.languages = languages

        return report

    def _call_llm(self, prompt: str) -> str:
        """Send the prompt to the LLM and return the response.

        Args:
            prompt: The full prompt (system + user) with structured data.

        Returns:
            The LLM's response string.

        Raises:
            AnalysisError: If the LLM call fails.
        """
        try:
            from openai import APIError, OpenAI

            client = OpenAI(
                api_key=self._llm_api_key,
                base_url=self._llm_base_url,
                timeout=self._llm_timeout,
            )

            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self._llm_model,
                temperature=0.3,
            )

            reply = response.choices[0].message.content.strip()
            logger.debug("LLM response received (%d characters)", len(reply))
            return reply

        except APIError as exc:
            raise AnalysisError(f"LLM API error: {exc}") from exc
        except ImportError as exc:
            raise AnalysisError(
                "Missing required dependency: openai. Run 'pip install -r requirements.txt'."
            ) from exc
        except Exception as exc:
            raise AnalysisError(f"Unexpected LLM error: {exc}") from exc

