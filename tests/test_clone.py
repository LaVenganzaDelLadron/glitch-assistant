"""Tests for app.github.clone (RepoCloner, CloneError).

Note: ``RepoCloner.clone`` is implemented as a plain generator function and
is NOT decorated with ``@contextlib.contextmanager``. Several tests below
drive the generator manually (via ``next()``/``gen.close()``) to exercise
the clone/cleanup logic, and one test explicitly documents the fact that
using it directly with a ``with`` statement currently fails — this protects
against silent behavior changes either way.
"""

from __future__ import annotations

import subprocess
import types
from pathlib import Path

import pytest

from app.github.clone import CloneError, RepoCloner


def _drive_to_yield(gen):
    """Advance a generator to its first yield and return the yielded value."""
    return next(gen)


class TestRepoClonerSuccess:
    def test_clone_creates_temp_dir_and_yields_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured_cmd = {}

        def fake_run(cmd, **kwargs):
            captured_cmd["cmd"] = cmd
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        cloner = RepoCloner(timeout=30)
        gen = cloner.clone("https://github.com/owner/repo.git")

        repo_path = _drive_to_yield(gen)

        assert isinstance(repo_path, Path)
        assert repo_path.exists()
        assert repo_path.is_dir()
        assert captured_cmd["cmd"] == [
            "git", "clone", "--depth", "1",
            "https://github.com/owner/repo.git", str(repo_path),
        ]

        # Exhaust the generator to trigger cleanup in the `finally` block.
        with pytest.raises(StopIteration):
            next(gen)

        assert not repo_path.exists()

    def test_clone_cleanup_via_close(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda cmd, **kwargs: subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr=""),
        )

        cloner = RepoCloner()
        gen = cloner.clone("https://github.com/owner/repo.git")
        repo_path = _drive_to_yield(gen)
        assert repo_path.exists()

        gen.close()

        assert not repo_path.exists()


class TestRepoClonerFailures:
    def test_clone_nonzero_return_code_raises_clone_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=128, stdout="", stderr="fatal: repository not found",
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        cloner = RepoCloner()
        gen = cloner.clone("https://github.com/owner/does-not-exist.git")

        with pytest.raises(CloneError, match="repository not found"):
            next(gen)

    def test_clone_timeout_raises_clone_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 1))

        monkeypatch.setattr(subprocess, "run", fake_run)

        cloner = RepoCloner(timeout=5)
        gen = cloner.clone("https://github.com/owner/repo.git")

        with pytest.raises(CloneError, match="timed out"):
            next(gen)

    def test_clone_missing_git_raises_clone_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(cmd, **kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr(subprocess, "run", fake_run)

        cloner = RepoCloner()
        gen = cloner.clone("https://github.com/owner/repo.git")

        with pytest.raises(CloneError, match="Git executable not found"):
            next(gen)

    def test_clone_error_cleans_up_temp_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        created_dirs = []
        real_mkdtemp = __import__("tempfile").mkdtemp

        def tracking_mkdtemp(*args, **kwargs):
            path = real_mkdtemp(*args, **kwargs)
            created_dirs.append(path)
            return path

        monkeypatch.setattr("tempfile.mkdtemp", tracking_mkdtemp)

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="boom")

        monkeypatch.setattr(subprocess, "run", fake_run)

        cloner = RepoCloner()
        gen = cloner.clone("https://github.com/owner/repo.git")

        with pytest.raises(CloneError):
            next(gen)

        assert len(created_dirs) == 1
        assert not Path(created_dirs[0]).exists()


class TestRepoClonerContextManagerBug:
    """Documents the current behavior of ``clone()`` when used as intended.

    The docstring for :meth:`RepoCloner.clone` and its caller
    (:class:`analysis.analyzer.RepoAnalyzer`) use it as ``with cloner.clone(url) as p:``.
    Because the method is a plain generator (missing ``@contextlib.contextmanager``),
    this currently raises a ``TypeError`` rather than acting as a context manager.
    """

    def test_clone_result_is_a_plain_generator(self) -> None:
        cloner = RepoCloner()
        result = cloner.clone("https://github.com/owner/repo.git")
        assert isinstance(result, types.GeneratorType)
        result.close()

    def test_using_clone_as_context_manager_raises_type_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda cmd, **kwargs: subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr=""),
        )
        cloner = RepoCloner()

        with pytest.raises(TypeError):
            with cloner.clone("https://github.com/owner/repo.git") as _repo_path:
                pass


class TestRepoClonerCleanupHelper:
    def test_cleanup_is_noop_when_no_temp_dir(self) -> None:
        cloner = RepoCloner()
        # Should not raise even though no clone has happened yet.
        cloner._cleanup()
        assert cloner._temp_dir is None

    def test_cleanup_is_idempotent(self, tmp_path: Path) -> None:
        cloner = RepoCloner()
        target = tmp_path / "some_dir"
        target.mkdir()
        cloner._temp_dir = target

        cloner._cleanup()
        assert not target.exists()
        assert cloner._temp_dir is None

        # Calling again should be a no-op, not raise.
        cloner._cleanup()