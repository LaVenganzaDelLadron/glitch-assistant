"""Tests for terminal.command_runner (CommandRunner, CommandResult, exceptions)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from terminal.command_runner import (
    CommandResult,
    CommandRunner,
    DangerousCommandError,
    TimeoutError as CmdTimeoutError,
)


class TestCommandRunnerSuccess:
    def test_run_returns_command_result_with_stdout(self) -> None:
        runner = CommandRunner(timeout=10)
        result = runner.run(["echo", "hello"])

        assert isinstance(result, CommandResult)
        assert result.return_code == 0
        assert "hello" in result.stdout
        assert result.command == ["echo", "hello"]

    def test_run_captures_nonzero_return_code(self) -> None:
        runner = CommandRunner(timeout=10)
        # `ls` on a path that does not exist -> nonzero exit code.
        result = runner.run(["ls", "/this/path/does/not/exist/xyz"])

        assert result.return_code != 0
        assert result.stderr != "" or result.stdout != ""

    def test_run_passes_cwd(self, tmp_path: Path) -> None:
        (tmp_path / "marker.txt").write_text("content")
        runner = CommandRunner(timeout=10)
        result = runner.run(["ls"], cwd=tmp_path)

        assert "marker.txt" in result.stdout

    def test_run_uses_default_timeout_when_not_overridden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = {}

        def fake_run(*args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        runner = CommandRunner(timeout=42)
        runner.run(["echo", "hi"])

        assert captured["timeout"] == 42

    def test_run_override_timeout_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = {}

        def fake_run(*args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        runner = CommandRunner(timeout=42)
        runner.run(["echo", "hi"], timeout=5)

        assert captured["timeout"] == 5

    def test_run_no_shell_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = {}

        def fake_run(*args, **kwargs):
            captured.update(kwargs)
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        runner = CommandRunner()
        runner.run(["echo", "hi"])

        assert captured.get("shell") is not True


class TestCommandRunnerValidation:
    def test_run_empty_command_raises_value_error(self) -> None:
        runner = CommandRunner()
        with pytest.raises(ValueError):
            runner.run([])

    @pytest.mark.parametrize(
        "dangerous_cmd",
        ["rm", "sudo", "shutdown", "wget", "curl", "docker", "npm", "chmod"],
    )
    def test_run_blocks_dangerous_commands(self, dangerous_cmd: str) -> None:
        runner = CommandRunner()
        with pytest.raises(DangerousCommandError):
            runner.run([dangerous_cmd, "-x"])

    def test_run_blocks_dangerous_command_given_as_full_path(self) -> None:
        runner = CommandRunner()
        with pytest.raises(DangerousCommandError):
            runner.run(["/usr/bin/rm", "-rf", "/tmp/x"])

    def test_run_allows_safe_commands(self) -> None:
        runner = CommandRunner()
        # Should not raise DangerousCommandError.
        result = runner.run(["echo", "safe"])
        assert result.return_code == 0


class TestCommandRunnerErrors:
    def test_run_timeout_raises_custom_timeout_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args, timeout=kwargs.get("timeout", 1))

        monkeypatch.setattr(subprocess, "run", fake_run)
        runner = CommandRunner(timeout=1)

        with pytest.raises(CmdTimeoutError):
            runner.run(["echo", "hi"])

    def test_run_file_not_found_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(*args, **kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr(subprocess, "run", fake_run)
        runner = CommandRunner()

        with pytest.raises(FileNotFoundError):
            runner.run(["some-nonexistent-tool"])

    def test_run_nonexistent_real_executable_raises_file_not_found(self) -> None:
        runner = CommandRunner()
        with pytest.raises(FileNotFoundError):
            runner.run(["this-command-should-not-exist-anywhere-xyz"])


class TestCommandResult:
    def test_command_result_is_frozen(self) -> None:
        result = CommandResult(stdout="a", stderr="b", return_code=0, command=["ls"])
        with pytest.raises(Exception):
            result.stdout = "changed"  # type: ignore[misc]

    def test_command_field_excluded_from_repr(self) -> None:
        result = CommandResult(stdout="a", stderr="b", return_code=0, command=["ls", "-la"])
        assert "ls" not in repr(result)
        assert "-la" not in repr(result)