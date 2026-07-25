"""Tests for ai.agent (AIAgent, AgentError)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from openai import APIError

import ai.agent as agent_module
from ai.agent import AgentError, AIAgent
from terminal.command_runner import (
    CommandResult,
    DangerousCommandError,
    TimeoutError as CmdTimeoutError,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self) -> None:
        self._replies: list[Any] = []
        self.calls: list[dict[str, Any]] = []

    def queue_reply(self, content: str) -> None:
        self._replies.append(content)

    def queue_error(self, error: Exception) -> None:
        self._replies.append(error)

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        if not self._replies:
            raise AssertionError("No more fake replies queued")
        item = self._replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return _FakeResponse(item)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeOpenAIClient:
    def __init__(self, **kwargs: Any) -> None:
        self.init_kwargs = kwargs
        self.completions = _FakeCompletions()
        self.chat = _FakeChat(self.completions)


class _FakeCommandRunner:
    def __init__(self) -> None:
        self.run_calls: list[dict[str, Any]] = []
        self.result: CommandResult | None = None
        self.error: Exception | None = None

    def run(self, command, cwd=None, timeout=None) -> CommandResult:
        self.run_calls.append({"command": command, "cwd": cwd, "timeout": timeout})
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _make_agent(monkeypatch: pytest.MonkeyPatch, repo_path: Path, command_runner=None) -> tuple[AIAgent, _FakeOpenAIClient]:
    monkeypatch.setattr(agent_module, "OpenAI", _FakeOpenAIClient)
    agent = AIAgent(
        api_key="key",
        model="test-model",
        base_url="https://example.invalid",
        timeout=10,
        command_runner=command_runner or _FakeCommandRunner(),
        repo_path=repo_path,
    )
    return agent, agent._client  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_init_creates_client_with_expected_kwargs(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        agent, client = _make_agent(monkeypatch, tmp_path)
        assert client.init_kwargs == {
            "api_key": "key",
            "base_url": "https://example.invalid",
            "timeout": 10,
        }
        assert agent._loaded_files == set()
        assert agent._messages == []


# ---------------------------------------------------------------------------
# analyze() loop
# ---------------------------------------------------------------------------

class TestAnalyzeLoop:
    def test_analyze_returns_report_immediately(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        agent, client = _make_agent(monkeypatch, tmp_path)
        report = {"action": "report", "summary": "done", "score": 90}
        client.completions.queue_reply(f"```json\n{json.dumps(report)}\n```")

        result = agent.analyze(
            system_prompt="sys",
            analysis_instructions="instr",
            file_index=[],
            file_index_text="none",
        )

        assert result == report
        assert len(client.completions.calls) == 1

    def test_analyze_handles_command_action_then_report(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        runner = _FakeCommandRunner()
        runner.result = CommandResult(stdout="file1\nfile2\n", stderr="", return_code=0, command=["ls"])

        agent, client = _make_agent(monkeypatch, tmp_path, command_runner=runner)
        client.completions.queue_reply(
            '```json\n{"action": "command", "command": ["ls", "-la"], "timeout": 15}\n```'
        )
        client.completions.queue_reply('```json\n{"action": "report", "summary": "ok", "score": 70}\n```')

        result = agent.analyze("sys", "instr", [], "none")

        assert result == {"action": "report", "summary": "ok", "score": 70}
        assert runner.run_calls == [{"command": ["ls", "-la"], "cwd": tmp_path, "timeout": 15}]
        # The command result should have been fed back into the conversation.
        assert any("file1" in m["content"] for m in agent._messages if m["role"] == "user")

    def test_analyze_handles_read_file_action_then_report(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        (tmp_path / "README.md").write_text("# Hello")
        agent, client = _make_agent(monkeypatch, tmp_path)
        client.completions.queue_reply('```json\n{"action": "read_file", "path": "README.md"}\n```')
        client.completions.queue_reply('```json\n{"action": "report", "summary": "ok", "score": 70}\n```')

        result = agent.analyze("sys", "instr", [{"path": "README.md", "size": 7}], "none")

        assert result == {"action": "report", "summary": "ok", "score": 70}
        assert "README.md" in agent._loaded_files
        assert any("# Hello" in m["content"] for m in agent._messages if m["role"] == "user")

    def test_analyze_handles_natural_language_reply_and_continues(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        agent, client = _make_agent(monkeypatch, tmp_path)
        client.completions.queue_reply("Let me think about this repository first.")
        client.completions.queue_reply('```json\n{"action": "report", "summary": "ok", "score": 50}\n```')

        result = agent.analyze("sys", "instr", [], "none")

        assert result == {"action": "report", "summary": "ok", "score": 50}
        assert any(
            m["role"] == "assistant" and "Let me think" in m["content"] for m in agent._messages
        )

    def test_analyze_unrecognized_action_appended_as_assistant_message(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        agent, client = _make_agent(monkeypatch, tmp_path)
        client.completions.queue_reply('{"action": "unknown_thing"}')
        client.completions.queue_reply('```json\n{"action": "report", "summary": "ok", "score": 1}\n```')

        result = agent.analyze("sys", "instr", [], "none")
        assert result == {"action": "report", "summary": "ok", "score": 1}

    def test_analyze_raises_agent_error_on_api_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        agent, client = _make_agent(monkeypatch, tmp_path)
        request = httpx.Request("POST", "https://example.invalid")
        client.completions.queue_error(APIError("boom", request, body=None))

        with pytest.raises(AgentError, match="LLM API error"):
            agent.analyze("sys", "instr", [], "none")

    def test_analyze_exhausts_iterations_and_forces_report(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        agent, client = _make_agent(monkeypatch, tmp_path)
        # Queue MAX_ITERATIONS non-JSON replies, then one final forced report reply.
        for i in range(agent_module._MAX_ITERATIONS):
            client.completions.queue_reply(f"Thinking step {i}, still not ready.")
        client.completions.queue_reply(json.dumps({"summary": "forced", "score": 33}))

        result = agent.analyze("sys", "instr", [], "none")

        assert result == {"summary": "forced", "score": 33}
        assert len(client.completions.calls) == agent_module._MAX_ITERATIONS + 1


# ---------------------------------------------------------------------------
# _parse_json_action
# ---------------------------------------------------------------------------

class TestParseJsonAction:
    def setup_method(self) -> None:
        self.agent = AIAgent.__new__(AIAgent)  # bypass __init__, pure parsing logic

    def test_plain_text_returns_none(self) -> None:
        assert self.agent._parse_json_action("Just some thoughts.") is None

    def test_json_code_block_with_action_parsed(self) -> None:
        text = '```json\n{"action": "command", "command": ["ls"]}\n```'
        result = self.agent._parse_json_action(text)
        assert result == {"action": "command", "command": ["ls"]}

    def test_generic_code_block_with_action_parsed(self) -> None:
        text = '```\n{"action": "read_file", "path": "a.py"}\n```'
        result = self.agent._parse_json_action(text)
        assert result == {"action": "read_file", "path": "a.py"}

    def test_bare_json_object_with_action_parsed(self) -> None:
        text = '{"action": "report", "summary": "s"}'
        result = self.agent._parse_json_action(text)
        assert result == {"action": "report", "summary": "s"}

    def test_json_without_action_key_returns_none(self) -> None:
        text = '{"foo": "bar"}'
        assert self.agent._parse_json_action(text) is None

    def test_invalid_json_in_code_block_returns_none(self) -> None:
        text = '```json\nnot json at all\n```'
        assert self.agent._parse_json_action(text) is None

    def test_large_report_with_action_key_parsed_via_full_text(self) -> None:
        payload = {"action": "report", "summary": "x" * 600, "score": 10}
        text = json.dumps(payload)
        assert len(text) > 500
        result = self.agent._parse_json_action(text)
        assert result == payload

    def test_large_json_with_summary_key_but_no_action_is_parsed(self) -> None:
        payload = {"summary": "x" * 600, "score": 10}
        text = json.dumps(payload)
        assert len(text) > 500
        result = self.agent._parse_json_action(text)
        assert result == payload

    def test_large_json_without_action_or_summary_or_score_returns_none(self) -> None:
        payload = {"foo": "x" * 600}
        text = json.dumps(payload)
        assert len(text) > 500
        assert self.agent._parse_json_action(text) is None

    def test_large_invalid_json_with_action_marker_returns_none(self) -> None:
        text = '{"action": "report", ' + ("x" * 600) + ' this is not valid json'
        assert self.agent._parse_json_action(text) is None


# ---------------------------------------------------------------------------
# _handle_command_action
# ---------------------------------------------------------------------------

class TestHandleCommandAction:
    def _agent(self, tmp_path: Path, runner=None) -> AIAgent:
        agent = AIAgent.__new__(AIAgent)
        agent._command_runner = runner or _FakeCommandRunner()
        agent._repo_path = tmp_path
        return agent

    def test_no_command_returns_error(self, tmp_path: Path) -> None:
        agent = self._agent(tmp_path)
        result = agent._handle_command_action({"action": "command"})
        assert "No command specified" in result

    def test_disallowed_command_returns_error(self, tmp_path: Path) -> None:
        agent = self._agent(tmp_path)
        result = agent._handle_command_action({"command": ["rm", "-rf", "/"]})
        assert "not in the allowed list" in result
        assert "rm" in result

    def test_allowed_command_success_formats_output(self, tmp_path: Path) -> None:
        runner = _FakeCommandRunner()
        runner.result = CommandResult(stdout="out-data", stderr="err-data", return_code=0, command=["ls"])
        agent = self._agent(tmp_path, runner=runner)

        result = agent._handle_command_action({"command": ["ls", "-la"]})

        assert "Exit code: 0" in result
        assert "out-data" in result
        assert "err-data" in result
        assert runner.run_calls[0]["command"] == ["ls", "-la"]
        assert runner.run_calls[0]["cwd"] == tmp_path

    def test_truncates_long_stdout(self, tmp_path: Path) -> None:
        runner = _FakeCommandRunner()
        long_output = "a" * (agent_module._MAX_TOOL_OUTPUT + 100)
        runner.result = CommandResult(stdout=long_output, stderr="", return_code=0, command=["cat"])
        agent = self._agent(tmp_path, runner=runner)

        result = agent._handle_command_action({"command": ["cat", "bigfile"]})
        assert "[TRUNCATED]" in result

    def test_dangerous_command_error_from_runner(self, tmp_path: Path) -> None:
        runner = _FakeCommandRunner()
        runner.error = DangerousCommandError("blocked")
        agent = self._agent(tmp_path, runner=runner)

        result = agent._handle_command_action({"command": ["git", "push"]})
        assert "Error: blocked" in result

    def test_timeout_error_from_runner(self, tmp_path: Path) -> None:
        runner = _FakeCommandRunner()
        runner.error = CmdTimeoutError("too slow")
        agent = self._agent(tmp_path, runner=runner)

        result = agent._handle_command_action({"command": ["git", "log"]})
        assert "Command timed out" in result

    def test_file_not_found_error_from_runner(self, tmp_path: Path) -> None:
        runner = _FakeCommandRunner()
        runner.error = FileNotFoundError("no such tool")
        agent = self._agent(tmp_path, runner=runner)

        result = agent._handle_command_action({"command": ["radon", "cc", "."]})
        assert "Error:" in result
        assert "no such tool" in result

    def test_unexpected_exception_from_runner(self, tmp_path: Path) -> None:
        runner = _FakeCommandRunner()
        runner.error = RuntimeError("kaboom")
        agent = self._agent(tmp_path, runner=runner)

        result = agent._handle_command_action({"command": ["git", "status"]})
        assert "Unexpected error" in result
        assert "kaboom" in result


# ---------------------------------------------------------------------------
# _handle_read_file_action
# ---------------------------------------------------------------------------

class TestHandleReadFileAction:
    def _agent(self, tmp_path: Path) -> AIAgent:
        agent = AIAgent.__new__(AIAgent)
        agent._repo_path = tmp_path
        agent._loaded_files = set()
        return agent

    def test_no_path_returns_error(self, tmp_path: Path) -> None:
        agent = self._agent(tmp_path)
        result = agent._handle_read_file_action({}, [])
        assert "No file path specified" in result

    def test_already_loaded_file_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1")
        agent = self._agent(tmp_path)
        agent._loaded_files.add("a.py")

        result = agent._handle_read_file_action({"path": "a.py"}, [])
        assert "already loaded" in result

    def test_nonexistent_file_returns_error(self, tmp_path: Path) -> None:
        agent = self._agent(tmp_path)
        result = agent._handle_read_file_action({"path": "missing.py"}, [])
        assert "does not exist" in result

    def test_directory_path_returns_error(self, tmp_path: Path) -> None:
        (tmp_path / "subdir").mkdir()
        agent = self._agent(tmp_path)
        result = agent._handle_read_file_action({"path": "subdir"}, [])
        assert "is not a file" in result

    def test_successful_read_includes_size_from_index(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1")
        agent = self._agent(tmp_path)

        result = agent._handle_read_file_action({"path": "a.py"}, [{"path": "a.py", "size": 5}])

        assert "--- a.py (5 bytes) ---" in result
        assert "x = 1" in result
        assert "a.py" in agent._loaded_files

    def test_successful_read_without_index_metadata(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1")
        agent = self._agent(tmp_path)

        result = agent._handle_read_file_action({"path": "a.py"}, [])

        assert "--- a.py ---" in result

    def test_truncates_large_file_content(self, tmp_path: Path) -> None:
        big_content = "a" * 50_005
        (tmp_path / "big.txt").write_text(big_content)
        agent = self._agent(tmp_path)

        result = agent._handle_read_file_action({"path": "big.txt"}, [])
        assert "[TRUNCATED]" in result

    def test_unreadable_file_returns_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "bad.txt").write_text("data")
        agent = self._agent(tmp_path)

        def flaky_read_text(self, *args, **kwargs):
            raise OSError("cannot read")

        monkeypatch.setattr(Path, "read_text", flaky_read_text)

        result = agent._handle_read_file_action({"path": "bad.txt"}, [])
        assert "Error: Could not read file" in result


# ---------------------------------------------------------------------------
# _force_report
# ---------------------------------------------------------------------------

class TestForceReport:
    def _agent(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[AIAgent, _FakeOpenAIClient]:
        return _make_agent(monkeypatch, tmp_path)

    def test_force_report_parses_valid_json_reply(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        agent, client = self._agent(monkeypatch, tmp_path)
        agent._messages = [{"role": "system", "content": "sys"}]
        client.completions.queue_reply(json.dumps({"summary": "final", "score": 88}))

        result = agent._force_report()
        assert result == {"summary": "final", "score": 88}

    def test_force_report_falls_back_to_plain_text_summary(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        agent, client = self._agent(monkeypatch, tmp_path)
        agent._messages = [{"role": "system", "content": "sys"}]
        client.completions.queue_reply("This is not JSON at all.")

        result = agent._force_report()
        assert result["summary"] == "This is not JSON at all."
        assert result["score"] == 50
        assert result["issues"] == []
        assert result["recommendations"] == []

    def test_force_report_handles_api_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        agent, client = self._agent(monkeypatch, tmp_path)
        agent._messages = [{"role": "system", "content": "sys"}]
        request = httpx.Request("POST", "https://example.invalid")
        client.completions.queue_error(APIError("down", request, body=None))

        result = agent._force_report()
        assert result["score"] == 0
        assert "API error" in result["summary"]


class TestAllowedCommands:
    def test_expected_commands_present(self) -> None:
        for cmd in ("git", "ls", "pytest", "ruff", "find"):
            assert cmd in AIAgent.ALLOWED_COMMANDS

    def test_dangerous_commands_not_allowed(self) -> None:
        for cmd in ("rm", "sudo", "curl", "wget"):
            assert cmd not in AIAgent.ALLOWED_COMMANDS