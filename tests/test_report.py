"""Tests for analysis.report (AnalysisReport, Issue, Recommendation, Strength)."""

from __future__ import annotations

import json

import pytest

from analysis.report import AnalysisReport, Issue, Recommendation, Strength


class TestDataclassDefaults:
    def test_issue_defaults(self) -> None:
        issue = Issue(category="security", description="hardcoded secret")
        assert issue.file is None
        assert issue.line is None
        assert issue.severity == "medium"

    def test_strength_requires_category_and_description(self) -> None:
        strength = Strength(category="tests", description="good coverage")
        assert strength.category == "tests"
        assert strength.description == "good coverage"

    def test_recommendation_defaults(self) -> None:
        rec = Recommendation(priority="HIGH", category="security", description="fix it")
        assert rec.details == ""

    def test_analysis_report_defaults(self) -> None:
        report = AnalysisReport()
        assert report.repository == ""
        assert report.clone_url == ""
        assert report.summary == ""
        assert report.score == 0
        assert report.languages == {}
        assert report.issues == []
        assert report.strengths == []
        assert report.recommendations == []
        assert report.security == []
        assert report.docker == []


class TestToDict:
    def test_to_dict_contains_all_top_level_keys(self) -> None:
        report = AnalysisReport(repository="owner/repo", clone_url="https://x.git")
        data = report.to_dict()

        expected_keys = {
            "summary", "score", "repository", "clone_url", "languages",
            "issues", "strengths", "recommendations", "security",
            "performance", "documentation", "architecture", "tests",
            "complexity", "dependencies", "ci_cd", "docker", "maintainability",
        }
        assert expected_keys <= set(data.keys())

    def test_to_dict_serializes_nested_dataclasses(self) -> None:
        report = AnalysisReport(
            issues=[Issue(category="security", description="leak", file="a.py", line=10, severity="high")],
            strengths=[Strength(category="tests", description="good")],
            recommendations=[Recommendation(priority="HIGH", category="security", description="fix", details="d")],
        )
        data = report.to_dict()

        assert data["issues"] == [
            {"category": "security", "description": "leak", "file": "a.py", "line": 10, "severity": "high"}
        ]
        assert data["strengths"] == [{"category": "tests", "description": "good"}]
        assert data["recommendations"] == [
            {"priority": "HIGH", "category": "security", "description": "fix", "details": "d"}
        ]


class TestToJson:
    def test_to_json_produces_valid_json(self) -> None:
        report = AnalysisReport(repository="owner/repo", score=80)
        raw = report.to_json()
        parsed = json.loads(raw)
        assert parsed["repository"] == "owner/repo"
        assert parsed["score"] == 80

    def test_to_json_respects_indent(self) -> None:
        report = AnalysisReport()
        raw = report.to_json(indent=4)
        assert raw.startswith("{\n    ")


class TestFromJson:
    def test_from_json_round_trip_preserves_equality(self) -> None:
        report = AnalysisReport(
            repository="owner/repo",
            clone_url="https://github.com/owner/repo.git",
            summary="A summary",
            score=72,
            languages={"Python": 0.9, "Shell": 0.1},
            issues=[Issue(category="security", description="leak", file="a.py", line=1, severity="high")],
            strengths=[Strength(category="tests", description="good coverage")],
            recommendations=[
                Recommendation(priority="HIGH", category="security", description="fix", details="do it")
            ],
            security=["no secrets found"],
            docker=["Dockerfile present"],
        )

        restored = AnalysisReport.from_json(report.to_json())

        assert restored == report

    def test_from_json_defaults_missing_optional_fields(self) -> None:
        raw = json.dumps({"repository": "owner/repo"})
        report = AnalysisReport.from_json(raw)

        assert report.repository == "owner/repo"
        assert report.summary == ""
        assert report.score == 0
        assert report.issues == []
        assert report.strengths == []
        assert report.recommendations == []

    def test_from_json_reconstructs_nested_objects_as_dataclass_instances(self) -> None:
        raw = json.dumps({
            "issues": [{"category": "style", "description": "bad naming"}],
            "strengths": [{"category": "docs", "description": "great readme"}],
            "recommendations": [
                {"priority": "LOW", "category": "style", "description": "rename vars"}
            ],
        })
        report = AnalysisReport.from_json(raw)

        assert isinstance(report.issues[0], Issue)
        assert report.issues[0].severity == "medium"  # default applied
        assert isinstance(report.strengths[0], Strength)
        assert isinstance(report.recommendations[0], Recommendation)
        assert report.recommendations[0].details == ""

    def test_from_json_invalid_json_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            AnalysisReport.from_json("not valid json")