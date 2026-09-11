"""Tests for app.github.scanner (RepoScanner)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.github import scanner as scanner_module
from app.github.scanner import RepoScanner


class TestRepoScannerBasics:
    def test_scan_raises_when_root_is_not_a_directory(self, tmp_path: Path) -> None:
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("content")

        scanner = RepoScanner()
        with pytest.raises(NotADirectoryError):
            scanner.scan(file_path)

    def test_scan_empty_directory_returns_empty_list(self, tmp_path: Path) -> None:
        scanner = RepoScanner()
        result = scanner.scan(tmp_path)
        assert result == []

    def test_scan_indexes_a_simple_text_file(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("print('hi')\n")

        scanner = RepoScanner()
        result = scanner.scan(tmp_path)

        assert len(result) == 1
        entry = result[0]
        assert entry["path"] == "main.py"
        assert entry["extension"] == ".py"
        assert entry["content"] == "print('hi')\n"
        assert entry["size"] == len("print('hi')\n")

    def test_scan_records_relative_paths_for_nested_files(self, tmp_path: Path) -> None:
        nested = tmp_path / "pkg" / "sub"
        nested.mkdir(parents=True)
        (nested / "module.py").write_text("x = 1")

        scanner = RepoScanner()
        result = scanner.scan(tmp_path)

        paths = {f["path"] for f in result}
        assert "pkg/sub/module.py" in paths

    def test_scan_file_without_extension_uses_placeholder(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("all:\n\techo hi")

        scanner = RepoScanner()
        result = scanner.scan(tmp_path)

        assert len(result) == 1
        assert result[0]["extension"] == "(no extension)"


class TestRepoScannerIgnoresAndFilters:
    @pytest.mark.parametrize("ignored_dir", [".git", "node_modules", "__pycache__", "venv", ".venv"])
    def test_scan_skips_ignored_directories(self, tmp_path: Path, ignored_dir: str) -> None:
        ignored = tmp_path / ignored_dir
        ignored.mkdir()
        (ignored / "should_be_skipped.py").write_text("secret = 1")
        (tmp_path / "visible.py").write_text("visible = 1")

        scanner = RepoScanner()
        result = scanner.scan(tmp_path)

        paths = [f["path"] for f in result]
        assert "visible.py" in paths
        assert not any(ignored_dir in p for p in paths)

    def test_scan_skips_binary_extensions(self, tmp_path: Path) -> None:
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")
        (tmp_path / "code.py").write_text("a = 1")

        scanner = RepoScanner()
        result = scanner.scan(tmp_path)

        paths = [f["path"] for f in result]
        assert "code.py" in paths
        assert "image.png" not in paths

    def test_scan_skips_files_over_max_size(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(scanner_module, "_MAX_FILE_SIZE", 10)
        (tmp_path / "big.txt").write_text("x" * 20)
        (tmp_path / "small.txt").write_text("ok")

        scanner = RepoScanner()
        result = scanner.scan(tmp_path)

        paths = [f["path"] for f in result]
        assert "small.txt" in paths
        assert "big.txt" not in paths

    def test_scan_truncates_content_over_max_length(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(scanner_module, "_MAX_CONTENT_LENGTH", 10)
        (tmp_path / "long.txt").write_text("a" * 50)

        scanner = RepoScanner()
        result = scanner.scan(tmp_path)

        assert len(result) == 1
        content = result[0]["content"]
        assert content.startswith("a" * 10)
        assert "[TRUNCATED]" in content

    def test_scan_skips_unreadable_files_without_crashing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / "unreadable.txt").write_text("data")
        (tmp_path / "ok.txt").write_text("fine")

        original_read_text = Path.read_text

        def flaky_read_text(self, *args, **kwargs):
            if self.name == "unreadable.txt":
                raise OSError("permission denied")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", flaky_read_text)

        scanner = RepoScanner()
        result = scanner.scan(tmp_path)

        paths = [f["path"] for f in result]
        assert "ok.txt" in paths
        assert "unreadable.txt" not in paths

    def test_scan_ignores_lock_files(self, tmp_path: Path) -> None:
        (tmp_path / "yarn.lock").write_text("lockfile contents")
        (tmp_path / "app.py").write_text("x = 1")

        scanner = RepoScanner()
        result = scanner.scan(tmp_path)

        paths = [f["path"] for f in result]
        assert "app.py" in paths
        assert "yarn.lock" not in paths