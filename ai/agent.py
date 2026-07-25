"""Iterative AI analysis agent — inspects repos, runs commands, and produces reports.

The agent works in an iterative loop:
1. Build a file index from the scanned repository.
2. Inspect important files first (README, config, entry points).
3. Execute terminal commands as needed (git log, linting, tests).
4. Request additional files when necessary.
5. Iterate until enough information is gathered.
6. Produce a comprehensive structured report.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Sequence

from openai import APIError, OpenAI

from terminal.command_runner import CommandRunner, CommandResult
from terminal.command_runner import DangerousCommandError as CmdDangerousError
from terminal.command_runner import TimeoutError as CmdTimeoutError

logger = logging.getLogger(__name__)

# Maximum number of analysis iterations.
_MAX_ITERATIONS = 10

# Size limit for tool result output sent to the LLM (characters).
_MAX_TOOL_OUTPUT = 50_000


class AgentError(Exception):
    """Raised when the AI agent encounters a fatal error."""


class AIAgent:
    """Iterative AI agent that analyzes a repository using LLM + terminal commands.

    The agent maintains a conversation with the LLM, progressively building
    understanding of the codebase through file inspection and command execution.
    """

    # Commands that the AI is explicitly allowed to run.
    ALLOWED_COMMANDS: frozenset[str] = frozenset({
        "git", "find", "rg", "tree", "ls", "cat", "head", "tail", "wc",
        "python", "pytest", "ruff", "pylint", "flake8", "bandit", "radon", "mypy",
        "npm", "cargo", "go",
    })

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout: int,
        command_runner: CommandRunner,
        repo_path: Path,
    ) -> None:
        """Initialize the AI agent.

        Args:
            api_key: API key for the LLM provider.
            model: Model identifier string.
            base_url: Base URL for the LLM API.
            timeout: Timeout in seconds for LLM API calls.
            command_runner: A :class:`CommandRunner` instance for executing commands.
            repo_path: Path to the cloned repository on disk.
        """
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._command_runner = command_runner
        self._repo_path = repo_path

        self._client = OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
        )

        # Conversation history for the iterative analysis.
        self._messages: list[dict[str, str]] = []
        # Files that have already been loaded into context.
        self._loaded_files: set[str] = set()

    def analyze(
        self,
        system_prompt: str,
        analysis_instructions: str,
        file_index: list[dict[str, Any]],
        file_index_text: str,
    ) -> dict[str, Any]:
        """Run the iterative analysis loop and return the final report.

        Args:
            system_prompt: The system prompt defining the AI's role.
            analysis_instructions: Detailed analysis dimensions/instructions.
            file_index: The complete list of scanned file metadata.
            file_index_text: Formatted text representation of the file index.

        Returns:
            A dict containing the structured analysis report, or a dict with
            a ``summary`` key if structured parsing fails.
        """
        self._messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Build the initial context message
        initial_context = (
            f"## Repository Location\n\n"
            f"The repository is cloned at: {self._repo_path}\n\n"
            f"## Analysis Instructions\n\n{analysis_instructions}\n\n"
            f"## File Index\n\n{file_index_text}\n\n"
            "You can execute terminal commands to explore the repository further. "
            "To run a command, respond with a JSON block like:\n\n"
            '```json\n{"action": "command", "command": ["ls", "-la"], "timeout": 30}\n```\n\n'
            "To read a specific file, respond with:\n\n"
            '```json\n{"action": "read_file", "path": "relative/path/to/file.py"}\n```\n\n'
            "When you have enough information to produce the final report, respond with:\n\n"
            '```json\n{"action": "report", ...report_data...}\n```\n\n'
            "Start by inspecting important files like README.md, configuration files, "
            "and entry points."
        )

        self._messages.append({"role": "user", "content": initial_context})

        # Iterative analysis loop
        for iteration in range(1, _MAX_ITERATIONS + 1):
            logger.info("Agent iteration %d/%d", iteration, _MAX_ITERATIONS)

            try:
                response = self._client.chat.completions.create(
                    messages=self._messages,
                    model=self._model,
                    temperature=0.3,
                )
            except APIError as exc:
                raise AgentError(f"LLM API error during analysis: {exc}") from exc

            reply = response.choices[0].message.content.strip()
            logger.debug("Agent reply (%.200s…)", reply)

            # Try to parse the reply as JSON
            parsed = self._parse_json_action(reply)

            if parsed is None:
                # The AI responded with natural language — just continue the conversation
                self._messages.append({"role": "assistant", "content": reply})
                continue

            action = parsed.get("action", "")

            if action == "command":
                result = self._handle_command_action(parsed)
                self._messages.append({
                    "role": "user",
                    "content": f"Command result:\n{result}",
                })

            elif action == "read_file":
                result = self._handle_read_file_action(parsed, file_index)
                self._messages.append({
                    "role": "user",
                    "content": f"File contents:\n{result}",
                })

            elif action == "report":
                # The AI produced the final report
                logger.info("Agent produced final report on iteration %d", iteration)
                return parsed

            else:
                self._messages.append({
                    "role": "assistant",
                    "content": reply,
                })

        # If we exhausted iterations without a report, ask the AI to produce one
        logger.warning("Agent reached max iterations without producing a report")
        return self._force_report()

    def _parse_json_action(self, text: str) -> dict[str, Any] | None:
        """Try to parse a JSON action block from the AI's response.

        Looks for a JSON code block (```json ... ```) or a standalone JSON object.

        Args:
            text: The AI's response text.

        Returns:
            A parsed JSON dict, or ``None`` if no valid JSON action is found.
        """
        # Try to extract JSON from a code block first
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start) if "```" in text[start:] else len(text)
            json_str = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            json_str = text[start:end].strip()
        else:
            # Try to parse the whole thing as JSON
            json_str = text.strip()

        # If the JSON string is too long, it might be a report — action must be "report"
        if len(json_str) > 500 and text.strip().startswith("{"):
            # Check if it looks like a structured report
            if '"action"' in text:
                try:
                    return json.loads(text.strip())
                except json.JSONDecodeError:
                    return None
            if '"summary"' in text or '"score"' in text:
                try:
                    return json.loads(text.strip())
                except json.JSONDecodeError:
                    return None
            return None

        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, dict) and "action" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass

        return None

    def _handle_command_action(self, parsed: dict[str, Any]) -> str:
        """Execute a command requested by the AI.

        Args:
            parsed: The parsed action dict with keys ``command`` (list), ``timeout`` (optional).

        Returns:
            A string representation of the command result.
        """
        command: list[str] = parsed.get("command", [])
        timeout: int | None = parsed.get("timeout")

        if not command:
            return "Error: No command specified."

        executable = command[0]
        if executable not in self.ALLOWED_COMMANDS:
            return (
                f"Error: Command '{executable}' is not in the allowed list. "
                f"Allowed commands: {', '.join(sorted(self.ALLOWED_COMMANDS))}"
            )

        try:
            result: CommandResult = self._command_runner.run(
                command=command,
                cwd=self._repo_path,
                timeout=timeout,
            )
        except CmdDangerousError as exc:
            return f"Error: {exc}"
        except CmdTimeoutError as exc:
            return f"Error: Command timed out — {exc}"
        except FileNotFoundError as exc:
            return f"Error: {exc}"
        except Exception as exc:
            logger.exception("Unexpected command error")
            return f"Error: Unexpected error — {exc}"

        output = f"Exit code: {result.return_code}\n"
        if result.stdout:
            # Truncate stdout if too long
            stdout = result.stdout
            if len(stdout) > _MAX_TOOL_OUTPUT:
                stdout = stdout[:_MAX_TOOL_OUTPUT] + "\n\n# ... [TRUNCATED]"
            output += f"stdout:\n{stdout}\n"
        if result.stderr:
            stderr = result.stderr
            if len(stderr) > _MAX_TOOL_OUTPUT:
                stderr = stderr[:_MAX_TOOL_OUTPUT] + "\n\n# ... [TRUNCATED]"
            output += f"stderr:\n{stderr}\n"

        return output

    def _handle_read_file_action(
        self,
        parsed: dict[str, Any],
        file_index: list[dict[str, Any]],
    ) -> str:
        """Read a file from the repository and return its contents.

        Args:
            parsed: The parsed action dict with key ``path``.
            file_index: The scanned file index for looking up file metadata.

        Returns:
            The file contents as a string, or an error message.
        """
        relative_path = parsed.get("path", "")
        if not relative_path:
            return "Error: No file path specified."

        # Prevent duplicate loading
        if relative_path in self._loaded_files:
            return f"File '{relative_path}' was already loaded. Skipping duplicate."

        file_path = self._repo_path / relative_path

        if not file_path.exists():
            return f"Error: File '{relative_path}' does not exist."
        if not file_path.is_file():
            return f"Error: '{relative_path}' is not a file."

        # Look up metadata from file index for size info
        file_meta = None
        for f in file_index:
            if f["path"] == relative_path:
                file_meta = f
                break

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except (UnicodeDecodeError, OSError) as exc:
            return f"Error: Could not read file '{relative_path}': {exc}"

        # Truncate very large files
        max_chars = 50_000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n# ... [TRUNCATED]"

        self._loaded_files.add(relative_path)

        size_info = f" ({file_meta['size']} bytes)" if file_meta else ""
        return (
            f"--- {relative_path}{size_info} ---\n"
            f"{content}\n"
            f"--- End of {relative_path} ---"
        )

    def _force_report(self) -> dict[str, Any]:
        """Force the AI to produce a final report when iterations are exhausted.

        Sends a final prompt asking for the report and returns the result.

        Returns:
            A dict containing the analysis report.
        """
        self._messages.append({
            "role": "user",
            "content": (
                "You have reached the maximum number of iterations. "
                "Please produce your final comprehensive analysis report now. "
                "Respond with a JSON object containing all findings."
            ),
        })

        try:
            response = self._client.chat.completions.create(
                messages=self._messages,
                model=self._model,
                temperature=0.3,
            )
        except APIError as exc:
            return {
                "summary": f"Analysis interrupted due to API error: {exc}",
                "score": 0,
                "issues": [],
                "recommendations": [],
            }

        reply = response.choices[0].message.content.strip()

        # Try to parse as JSON
        try:
            return json.loads(reply)
        except json.JSONDecodeError:
            return {
                "summary": reply,
                "score": 50,
                "issues": [],
                "recommendations": [],
            }

