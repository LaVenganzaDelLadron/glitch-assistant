"""Git scanner — extracts repository Git metadata and statistics."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from terminal.command_runner import CommandRunner, CommandResult

logger = logging.getLogger(__name__)


class GitScanner:
    """Extracts Git repository statistics and metadata.

    Runs various ``git`` commands to gather information about:
        - Branch status
        - Commit history
        - File tracking
        - Contributor info
        - Tag/release info
    """

    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        """Initialize the git scanner.

        Args:
            command_runner: Optional :class:`CommandRunner` instance.
        """
        self._runner = command_runner or CommandRunner(timeout=30)

    def scan(self, repo_path: Path) -> dict[str, Any]:
        """Run git analysis commands on the repository.

        Args:
            repo_path: Path to the cloned repository.

        Returns:
            A dict containing git statistics:
                - ``branch``: Current branch name (str)
                - ``commit_count``: Total number of commits (int)
                - ``last_commit``: Last commit message and hash (str)
                - ``first_commit_date``: Date of the first commit (str)
                - ``total_files_tracked``: Number of files tracked by git (int)
                - ``contributors``: Number of unique authors (int)
                - ``has_tags``: Whether the repo has tags (bool)
                - ``is_dirty``: Whether the working tree is dirty (bool)
                - ``branches``: List of branch names (list[str])
                - ``findings``: list of finding dicts
        """
        result: dict[str, Any] = {
            "branch": "unknown",
            "commit_count": 0,
            "last_commit": "",
            "first_commit_date": "",
            "total_files_tracked": 0,
            "contributors": 0,
            "has_tags": False,
            "is_dirty": False,
            "branches": [],
            "findings": [],
        }

        # Current branch
        branch_result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_path)
        if branch_result and branch_result.return_code == 0:
            result["branch"] = branch_result.stdout.strip()

        # Commit count
        count_result = self._run_git(["rev-list", "--count", "HEAD"], repo_path)
        if count_result and count_result.return_code == 0:
            try:
                result["commit_count"] = int(count_result.stdout.strip())
            except ValueError:
                pass

        # Last commit
        last_result = self._run_git(
            ["log", "-1", "--format=%h %s (%ai)"], repo_path
        )
        if last_result and last_result.return_code == 0:
            result["last_commit"] = last_result.stdout.strip()

        # First commit date
        first_result = self._run_git(
            ["log", "--reverse", "--format=%ai", "--max-count=1"], repo_path
        )
        if first_result and first_result.return_code == 0:
            result["first_commit_date"] = first_result.stdout.strip()

        # Files tracked
        files_result = self._run_git(["ls-files"], repo_path)
        if files_result and files_result.return_code == 0:
            result["total_files_tracked"] = len(files_result.stdout.splitlines())

        # Contributors
        shortlog_result = self._run_git(
            ["shortlog", "-sn", "--all"], repo_path
        )
        if shortlog_result and shortlog_result.return_code == 0:
            result["contributors"] = len(shortlog_result.stdout.splitlines())

            # Count commits per contributor for the report
            contributor_lines = shortlog_result.stdout.strip().splitlines()
            if contributor_lines:
                top_contributor = contributor_lines[0].strip()
                result["findings"].append({
                    "type": "contributors",
                    "description": (
                        f"Repository has {result['contributors']} contributor(s). "
                        f"Top: {top_contributor}"
                    ),
                    "severity": "info",
                })

        # Tags
        tags_result = self._run_git(["tag"], repo_path)
        if tags_result and tags_result.return_code == 0:
            result["has_tags"] = len(tags_result.stdout.strip()) > 0

        # Dirty status
        dirty_result = self._run_git(["status", "--porcelain"], repo_path)
        if dirty_result and dirty_result.return_code == 0:
            result["is_dirty"] = len(dirty_result.stdout.strip()) > 0

        # All branches
        branches_result = self._run_git(
            ["branch", "-a"], repo_path
        )
        if branches_result and branches_result.return_code == 0:
            branches = [
                b.strip().replace("* ", "").strip()
                for b in branches_result.stdout.splitlines()
                if b.strip()
            ]
            result["branches"] = branches

        # Findings from git stats
        if result["commit_count"] == 0:
            result["findings"].append({
                "type": "no_commits",
                "description": "Repository has no commits",
                "severity": "high",
            })
        elif result["commit_count"] < 10:
            result["findings"].append({
                "type": "few_commits",
                "description": (
                    f"Repository has only {result['commit_count']} commits — "
                    f"may be very new or inactive"
                ),
                "severity": "info",
            })

        if result["is_dirty"]:
            result["findings"].append({
                "type": "dirty_tree",
                "description": "Working tree has uncommitted changes",
                "severity": "low",
            })

        logger.info(
            "Git scan complete — branch=%s, commits=%d, contributors=%d, files=%d",
            result["branch"],
            result["commit_count"],
            result["contributors"],
            result["total_files_tracked"],
        )

        return result

    def _run_git(self, args: list[str], cwd: Path) -> CommandResult | None:
        """Run a git command safely.

        Args:
            args: Git subcommand arguments (e.g. ``["log", "-1"]``).
            cwd: Working directory (the repo path).

        Returns:
            The :class:`CommandResult`, or ``None`` if the command failed.
        """
        try:
            return self._runner.run(["git"] + args, cwd=cwd)
        except Exception as exc:
            logger.debug("Git command 'git %s' failed: %s", " ".join(args), exc)
            return None

