"""Tests for analysis.prompts (SYSTEM_PROMPT, ANALYSIS_INSTRUCTIONS, build_file_index_prompt)."""

from __future__ import annotations

from analysis.prompts import ANALYSIS_INSTRUCTIONS, SYSTEM_PROMPT, build_file_index_prompt


class TestStaticPrompts:
    def test_system_prompt_is_nonempty_string(self) -> None:
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT.strip()) > 0

    def test_system_prompt_mentions_key_responsibilities(self) -> None:
        assert "structured report" in SYSTEM_PROMPT.lower() or "report" in SYSTEM_PROMPT.lower()
        assert "terminal" in SYSTEM_PROMPT.lower() or "command" in SYSTEM_PROMPT.lower()

    def test_analysis_instructions_is_nonempty_string(self) -> None:
        assert isinstance(ANALYSIS_INSTRUCTIONS, str)
        assert len(ANALYSIS_INSTRUCTIONS.strip()) > 0

    def test_analysis_instructions_covers_expected_dimensions(self) -> None:
        for heading in ("Security", "Testing", "Documentation", "Complexity", "Performance"):
            assert heading in ANALYSIS_INSTRUCTIONS


class TestBuildFileIndexPrompt:
    def test_empty_file_index_returns_fallback_message(self) -> None:
        result = build_file_index_prompt([])
        assert "empty" in result.lower() or "skipped" in result.lower()

    def test_includes_total_file_count(self) -> None:
        file_index = [
            {"path": "a.py", "extension": ".py", "size": 100},
            {"path": "b.py", "extension": ".py", "size": 200},
            {"path": "README.md", "extension": ".md", "size": 300},
        ]
        result = build_file_index_prompt(file_index)
        assert "Total files scanned: 3" in result

    def test_lists_every_file_path(self) -> None:
        file_index = [
            {"path": "a.py", "extension": ".py", "size": 1024},
            {"path": "nested/b.py", "extension": ".py", "size": 2048},
        ]
        result = build_file_index_prompt(file_index)
        assert "a.py" in result
        assert "nested/b.py" in result

    def test_formats_file_size_in_kb_with_one_decimal(self) -> None:
        file_index = [{"path": "a.py", "extension": ".py", "size": 2048}]
        result = build_file_index_prompt(file_index)
        assert "2.0 KB" in result

    def test_extension_counts_sorted_descending(self) -> None:
        file_index = [
            {"path": "a.py", "extension": ".py", "size": 10},
            {"path": "b.py", "extension": ".py", "size": 10},
            {"path": "c.md", "extension": ".md", "size": 10},
        ]
        result = build_file_index_prompt(file_index)
        py_index = result.index(".py: 2 file(s)")
        md_index = result.index(".md: 1 file(s)")
        assert py_index < md_index

    def test_missing_extension_key_defaults_to_unknown(self) -> None:
        file_index = [{"path": "weird", "size": 5}]
        result = build_file_index_prompt(file_index)
        assert "(unknown): 1 file(s)" in result

    def test_missing_size_key_defaults_to_zero_kb(self) -> None:
        file_index = [{"path": "weird", "extension": ".txt"}]
        result = build_file_index_prompt(file_index)
        assert "0.0 KB" in result