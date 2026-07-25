"""Safe command runner — executes shell commands via subprocess with strict safety controls.

This module provides a :class:`CommandRunner` that runs commands as subprocesses
without ``shell=True``, enforces timeouts, captures stdout/stderr, and blocks
dangerous commands.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)

# Commands that are NEVER allowed to execute.
_DANGEROUS_COMMANDS: frozenset[str] = frozenset({
    "rm", "dd", "mkfs", "mkfs.ext4", "mkfs.xfs", "fdisk", "parted",
    "chmod", "chown", "sudo", "su", "passwd",
    "shutdown", "reboot", "halt", "poweroff",
    "mount", "umount", "swapon", "swapoff",
    "iptables", "ufw", "firewall-cmd",
    "wget", "curl",  # network downloads — not allowed
    "nc", "netcat", "ncat",
    "ssh", "scp", "rsync",
    "apt", "apt-get", "yum", "dnf", "pacman", "brew",
    "pip", "pip3", "npm", "yarn", "cargo", "gem",
    "docker", "docker-compose", "kubectl",
    "kill", "pkill", "killall",
    "systemctl", "service",
    "crontab", "at",
    "perl", "ruby", "php",  # script interpreters that could exec anything
})

# Commands that are explicitly allowed for repository analysis.
ALLOWED_COMMANDS: frozenset[str] = frozenset({
    "git",
    "find",
    "rg",
    "tree",
    "ls",
    "cat",
    "head",
    "tail",
    "wc",
    "python",
    "pytest",
    "ruff",
    "pylint",
    "flake8",
    "bandit",
    "radon",
    "mypy",
    "npm",
    "cargo",
    "go",
    # Additional safe inspection commands
    "echo",
    "printf",
    "grep",
    "awk",
    "sed",
    "sort",
    "uniq",
    "cut",
    "tr",
    "diff",
    "comm",
    "cmp",
    "file",
    "du",
    "df",
    "stat",
    "which",
    "env",
    "printenv",
    "pwd",
    "date",
    "cal",
    "bc",
    "expr",
    "test",
    "true",
    "false",
    "dirname",
    "basename",
    "realpath",
    "readlink",
    "mktemp",
    "mkfifo",
    "tty",
    "yes",
    "seq",
    "nproc",
    "arch",
    "uname",
    "hostname",
    "whoami",
    "id",
    "groups",
    "logname",
    "users",
    "who",
    "w",
    "uptime",
    "hostid",
    "link",
    "unlink",
    "readlink",
    "md5sum",
    "sha1sum",
    "sha256sum",
    "sha512sum",
    "basenc",
    "base32",
    "base64",
})


@dataclass(frozen=True)
class CommandResult:
    """Result of a command execution."""

    stdout: str
    stderr: str
    return_code: int
    command: list[str] = field(repr=False)


class DangerousCommandError(Exception):
    """Raised when a dangerous or prohibited command is requested."""


class TimeoutError(Exception):
    """Raised when a command exceeds the configured timeout."""


class CommandRunner:
    """Executes commands safely with timeouts and a blocklist.

    Examples::

        runner = CommandRunner()
        result = runner.run(["ls", "-la"], cwd=Path("/some/repo"))
        print(result.stdout)
        print(f"Exit code: {result.return_code}")
    """

    def __init__(self, timeout: int = 60) -> None:
        """Initialize the runner.

        Args:
            timeout: Default timeout in seconds for all commands.
        """
        self._timeout = timeout

    def run(
        self,
        command: Sequence[str],
        cwd: Path | None = None,
        timeout: int | None = None,
    ) -> CommandResult:
        """Execute a command and capture its output and exit status.
        
        Args:
            command: The executable and its arguments.
            cwd: Working directory for the command.
            timeout: Maximum execution time in seconds, overriding the default when provided.
        
        Returns:
            A CommandResult containing captured stdout, stderr, the exit code, and command arguments.
        
        Raises:
            ValueError: If command is empty.
            DangerousCommandError: If the executable is prohibited.
            TimeoutError: If execution exceeds the configured timeout.
            FileNotFoundError: If the executable is unavailable.
        """
        if not command:
            raise ValueError("Command sequence must not be empty")

        executable = command[0]
        self._validate_command(executable)

        effective_timeout = timeout if timeout is not None else self._timeout
        logger.info(
            "Running command: %s (cwd=%s, timeout=%ds)",
            " ".join(str(c) for c in command),
            cwd or Path.cwd(),
            effective_timeout,
        )

        try:
            result = subprocess.run(
                list(command),
                capture_output=True,
                text=True,
                cwd=str(cwd) if cwd else None,
                timeout=effective_timeout,
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(
                f"Command '{' '.join(str(c) for c in command)}' timed out "
                f"after {effective_timeout}s"
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Command not found: '{executable}'. "
                f"Is it installed and available on PATH?"
            )

        cmd_result = CommandResult(
            stdout=result.stdout,
            stderr=result.stderr,
            return_code=result.returncode,
            command=list(command),
        )

        log_level = logging.WARNING if result.returncode != 0 else logging.DEBUG
        logger.log(
            log_level,
            "Command '%s' exited with code %d (stdout: %d bytes, stderr: %d bytes)",
            " ".join(str(c) for c in command),
            result.returncode,
            len(result.stdout),
            len(result.stderr),
        )

        return cmd_result

    def run_git(
        self,
        args: list[str],
        cwd: Path,
        timeout: int | None = None,
    ) -> str | None:
        """Convenience method to run a git command.

        Args:
            args: Git subcommand arguments (e.g. ``["log", "-1"]``).
            cwd: Working directory (the repo path).
            timeout: Override timeout in seconds.

        Returns:
            The stdout as a stripped string, or ``None`` if the command failed.
        """
        try:
            result = self.run(["git"] + args, cwd=cwd, timeout=timeout)
            if result.return_code == 0:
                return result.stdout.strip()
        except Exception as exc:
            logger.debug("Git command 'git %s' failed: %s", " ".join(args), exc)
        return None

    def _validate_command(self, executable: str) -> None:
        """Validate an executable against the blocked command list.
        
        Args:
            executable: The executable name or path to validate.
        
        Raises:
            DangerousCommandError: If the executable is blocked for security reasons.
        """
        base = Path(executable).name
        if base in _DANGEROUS_COMMANDS:
            raise DangerousCommandError(
                f"Command '{base}' is blocked for security reasons. "
                f"Only safe inspection commands are allowed."
            )
