"""Tests for recommendation.suggester (RecommendationSuggester)."""

from __future__ import annotations

import pytest

from analysis.report import Recommendation
from recommendation.suggester import RecommendationSuggester


class TestPrioritizeEmptyAndPassthrough:
    def setup_method(self) -> None:
        self.suggester = RecommendationSuggester()

    def test_prioritize_empty_list(self) -> None:
        assert self.suggester.prioritize([]) == []

    def test_existing_valid_priority_is_preserved_even_if_text_suggests_otherwise(self) -> None:
        rec = Recommendation(
            priority="LOW",
            category="security",
            description="Potential SQL injection vulnerability found",
        )
        result = self.suggester.prioritize([rec])
        assert result[0].priority == "LOW"


class TestClassificationByKeyword:
    def setup_method(self) -> None:
        self.suggester = RecommendationSuggester()

    @pytest.mark.parametrize(
        "description",
        [
            "Hardcoded API key found in config.py",
            "SQL injection vulnerability in query builder",
            "Missing HTTPS enforcement on login endpoint",
        ],
    )
    def test_unprioritized_recommendation_classified_as_high(self, description: str) -> None:
        rec = Recommendation(priority="", category="security", description=description)
        result = self.suggester.prioritize([rec])
        assert result[0].priority == "HIGH"

    @pytest.mark.parametrize(
        "description",
        [
            "Increase unit test coverage for the parser module",
            "Add docstrings to public functions",
            "Refactor the duplicate logic in scanner.py",
        ],
    )
    def test_unprioritized_recommendation_classified_as_medium(self, description: str) -> None:
        rec = Recommendation(priority="", category="quality", description=description)
        result = self.suggester.prioritize([rec])
        assert result[0].priority == "MEDIUM"

    def test_unprioritized_recommendation_with_no_keywords_defaults_to_low(self) -> None:
        rec = Recommendation(priority="", category="misc", description="Consider renaming the variable x")
        result = self.suggester.prioritize([rec])
        assert result[0].priority == "LOW"

    def test_invalid_priority_value_is_reclassified(self) -> None:
        rec = Recommendation(priority="URGENT", category="security", description="hardcoded secret found")
        result = self.suggester.prioritize([rec])
        assert result[0].priority == "HIGH"

    def test_classification_considers_details_field_too(self) -> None:
        rec = Recommendation(
            priority="",
            category="misc",
            description="Improve this",
            details="This relates to a possible CVE in a dependency",
        )
        result = self.suggester.prioritize([rec])
        assert result[0].priority == "HIGH"


class TestSortingOrder:
    def setup_method(self) -> None:
        self.suggester = RecommendationSuggester()

    def test_prioritize_sorts_high_medium_low(self) -> None:
        recs = [
            Recommendation(priority="LOW", category="misc", description="minor"),
            Recommendation(priority="HIGH", category="security", description="critical"),
            Recommendation(priority="MEDIUM", category="quality", description="moderate"),
        ]
        result = self.suggester.prioritize(recs)
        assert [r.priority for r in result] == ["HIGH", "MEDIUM", "LOW"]

    def test_prioritize_preserves_relative_order_within_same_priority(self) -> None:
        recs = [
            Recommendation(priority="HIGH", category="a", description="first high"),
            Recommendation(priority="HIGH", category="b", description="second high"),
        ]
        result = self.suggester.prioritize(recs)
        assert [r.description for r in result] == ["first high", "second high"]


class TestClassifyDirect:
    def setup_method(self) -> None:
        self.suggester = RecommendationSuggester()

    def test_classify_high_keyword(self) -> None:
        assert self.suggester._classify("this involves a known cve") == "HIGH"

    def test_classify_medium_keyword(self) -> None:
        assert self.suggester._classify("missing docstring here") == "MEDIUM"

    def test_classify_no_keyword_returns_low(self) -> None:
        assert self.suggester._classify("just some unrelated text") == "LOW"

    def test_classify_high_takes_precedence_over_medium(self) -> None:
        # "security" (HIGH) and "test" (MEDIUM) both appear; HIGH must win.
        text = "add tests to cover the security vulnerability"
        assert self.suggester._classify(text) == "HIGH"