"""Tests for app.github.client (GithubClient)."""

from __future__ import annotations

import pytest

from app.github.client import GithubClient


class TestExtractRepo:
    def setup_method(self) -> None:
        self.client = GithubClient()

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("https://github.com/owner/repo", "owner/repo"),
            ("https://www.github.com/owner/repo", "owner/repo"),
            ("http://github.com/owner/repo", "owner/repo"),
            ("owner/repo", "owner/repo"),
            ("please analyze https://github.com/facebook/react for me", "facebook/react"),
            ("owner-name/repo_name.js", "owner-name/repo_name.js"),
            ("https://github.com/owner/repo.git", "owner/repo.git"),
            ("https://github.com/owner/repo/", "owner/repo"),
        ],
    )
    def test_extract_repo_matches(self, text: str, expected: str) -> None:
        assert self.client.extract_repo(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "hello world",
            "",
            "just some text with no slashes",
        ],
    )
    def test_extract_repo_returns_none_when_no_match(self, text: str) -> None:
        assert self.client.extract_repo(text) is None

    def test_extract_repo_picks_first_match_in_text(self) -> None:
        text = "compare owner1/repo1 with owner2/repo2"
        assert self.client.extract_repo(text) == "owner1/repo1"


class TestBuildCloneUrl:
    def setup_method(self) -> None:
        self.client = GithubClient()

    def test_build_clone_url_basic(self) -> None:
        assert self.client.build_clone_url("owner/repo") == "https://github.com/owner/repo.git"

    def test_build_clone_url_with_dots_and_dashes(self) -> None:
        url = self.client.build_clone_url("my-org/my.repo-name")
        assert url == "https://github.com/my-org/my.repo-name.git"