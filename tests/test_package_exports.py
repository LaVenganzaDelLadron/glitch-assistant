"""Tests for the new package __init__.py files added in this PR.

Verifies that each package correctly re-exports its public symbols and that
``__all__`` matches what is actually importable.
"""

from __future__ import annotations


class TestAiPackage:
    def test_exports(self) -> None:
        import ai

        assert ai.__all__ == ["AIAgent", "AgentError"]
        assert ai.AIAgent is not None
        assert ai.AgentError is not None

    def test_ai_agent_is_the_same_object_as_submodule(self) -> None:
        import ai
        from ai.agent import AIAgent

        assert ai.AIAgent is AIAgent


class TestAnalysisPackage:
    def test_exports(self) -> None:
        import analysis

        assert set(analysis.__all__) == {
            "SYSTEM_PROMPT", "ANALYSIS_INSTRUCTIONS", "AnalysisReport",
            "Issue", "Recommendation", "Strength", "RepoAnalyzer",
        }
        assert isinstance(analysis.SYSTEM_PROMPT, str)
        assert isinstance(analysis.ANALYSIS_INSTRUCTIONS, str)

    def test_analysis_report_is_same_object_as_submodule(self) -> None:
        import analysis
        from analysis.report import AnalysisReport

        assert analysis.AnalysisReport is AnalysisReport


class TestAppGithubPackage:
    def test_exports(self) -> None:
        from app import github

        assert set(github.__all__) == {"GithubClient", "RepoCloner", "CloneError", "RepoScanner"}
        assert github.GithubClient is not None
        assert github.RepoCloner is not None
        assert github.CloneError is not None
        assert github.RepoScanner is not None

    def test_clone_error_is_an_exception_subclass(self) -> None:
        from app.github import CloneError

        assert issubclass(CloneError, Exception)


class TestRecommendationPackage:
    def test_exports(self) -> None:
        import recommendation

        assert recommendation.__all__ == ["RecommendationSuggester"]
        assert recommendation.RecommendationSuggester is not None


class TestTerminalPackage:
    def test_exports(self) -> None:
        import terminal

        assert set(terminal.__all__) == {
            "CommandRunner", "CommandResult", "DangerousCommandError", "TimeoutError",
        }
        assert terminal.CommandRunner is not None
        assert terminal.CommandResult is not None

    def test_terminal_timeout_error_is_local_exception_not_builtin(self) -> None:
        import builtins

        import terminal

        assert terminal.TimeoutError is not builtins.TimeoutError
        assert issubclass(terminal.TimeoutError, Exception)