"""Tests for app.core.pipeline.tools.github_tool (analyze_repository)."""

from __future__ import annotations

import json
from typing import Any

import pytest

import app.core.pipeline.tools.github_tool as github_tool_module
from analysis.analyzer import AnalysisError
from app.core.config.configuration_error import ConfigurationError
from app.core.config.settings import Settings


def _settings() -> Settings:
    return Settings(api_key="k", model="m", base_url="https://b", timeout=10.0)


class _FakeReport:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return self._data


class _FakeRepoAnalyzer:
    instances: list["_FakeRepoAnalyzer"] = []

    def __init__(self, llm_api_key, llm_model, llm_base_url, llm_timeout) -> None:
        self.init_kwargs = dict(
            llm_api_key=llm_api_key, llm_model=llm_model,
            llm_base_url=llm_base_url, llm_timeout=llm_timeout,
        )
        self.raised: Exception | None = None
        self.report_data: dict[str, Any] = {
            "summary": "s", "score": 80, "issues": [], "recommendations": [], "strengths": [],
        }
        _FakeRepoAnalyzer.instances.append(self)

    def analyze(self, user_input: str):
        if self.raised is not None:
            raise self.raised
        return _FakeReport(self.report_data)


@pytest.fixture(autouse=True)
def _reset_instances() -> None:
    _FakeRepoAnalyzer.instances.clear()
    yield
    _FakeRepoAnalyzer.instances.clear()


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.get_settings", _settings)


class TestAnalyzeRepositorySuccess:
    def test_returns_json_with_expected_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(github_tool_module, "RepoAnalyzer", _FakeRepoAnalyzer)

        raw = github_tool_module.analyze_repository("https://github.com/owner/repo")
        data = json.loads(raw)

        assert data["summary"] == "s"
        assert data["score"] == 80
        assert "analysis" in data
        assert "suggestion" in data
        assert data["suggestion"]["recommendations"] == []
        assert data["suggestion"]["strengths"] == []

    def test_constructs_analyzer_with_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(github_tool_module, "RepoAnalyzer", _FakeRepoAnalyzer)

        github_tool_module.analyze_repository("owner/repo")

        instance = _FakeRepoAnalyzer.instances[0]
        assert instance.init_kwargs == {
            "llm_api_key": "k", "llm_model": "m", "llm_base_url": "https://b", "llm_timeout": 10.0,
        }

    def test_includes_recommendations_and_strengths_in_suggestion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _AnalyzerWithFindings(_FakeRepoAnalyzer):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.report_data["recommendations"] = [
                    {"priority": "HIGH", "category": "x", "description": "y"}
                ]
                self.report_data["strengths"] = [{"category": "tests", "description": "good coverage"}]

        monkeypatch.setattr(github_tool_module, "RepoAnalyzer", _AnalyzerWithFindings)

        raw = github_tool_module.analyze_repository("owner/repo")
        data = json.loads(raw)

        assert data["suggestion"]["recommendations"] == [
            {"priority": "HIGH", "category": "x", "description": "y"}
        ]
        assert data["suggestion"]["strengths"] == [{"category": "tests", "description": "good coverage"}]


class TestAnalyzeRepositoryErrors:
    def test_analysis_error_returns_error_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Configure the instance to raise on analyze() rather than __init__.
        class _RaisingAnalyzer(_FakeRepoAnalyzer):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.raised = AnalysisError("could not extract repo")

        monkeypatch.setattr(github_tool_module, "RepoAnalyzer", _RaisingAnalyzer)

        raw = github_tool_module.analyze_repository("not a repo")
        data = json.loads(raw)

        assert "could not extract repo" in data["analysis"]["error"]
        assert "Analysis failed" in data["summary"]
        assert data["score"] == 0
        assert data["suggestion"] == {"recommendations": [], "strengths": []}

    def test_unexpected_exception_returns_generic_error_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _RaisingAnalyzer(_FakeRepoAnalyzer):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.raised = RuntimeError("boom")

        monkeypatch.setattr(github_tool_module, "RepoAnalyzer", _RaisingAnalyzer)

        raw = github_tool_module.analyze_repository("owner/repo")
        data = json.loads(raw)

        assert "Unexpected error" in data["analysis"]["error"]
        assert "boom" in data["analysis"]["error"]
        assert data["score"] == 0

    def test_configuration_error_from_settings_is_handled_as_unexpected_error(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def _raise_config_error() -> Settings:
            raise ConfigurationError("GROQ_API_KEY is required.")

        monkeypatch.setattr("app.core.config.settings.get_settings", _raise_config_error)
        monkeypatch.setattr(github_tool_module, "RepoAnalyzer", _FakeRepoAnalyzer)

        raw = github_tool_module.analyze_repository("owner/repo")
        data = json.loads(raw)

        assert "Unexpected error" in data["analysis"]["error"]
        assert "GROQ_API_KEY" in data["analysis"]["error"]
        assert data["score"] == 0

    def test_returns_valid_json_even_on_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _RaisingAnalyzer(_FakeRepoAnalyzer):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.raised = AnalysisError("bad input")

        monkeypatch.setattr(github_tool_module, "RepoAnalyzer", _RaisingAnalyzer)

        raw = github_tool_module.analyze_repository("owner/repo")
        # Should not raise when parsed as JSON.
        json.loads(raw)