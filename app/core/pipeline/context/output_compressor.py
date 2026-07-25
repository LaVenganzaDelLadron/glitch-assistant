"""Output compression — truncates, summarizes, and compresses tool outputs
and file listings before sending them to the LLM.

Provides:
    - :class:`OutputCompressor` — compresses command outputs, file lists,
      and repetitive logs to stay within token budgets.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Default max characters for a single command / tool output.
_DEFAULT_MAX_OUTPUT_CHARS = 3000

# Default max items in a file listing summary.
_DEFAULT_MAX_FILE_LIST_ITEMS = 50

# Default max lines for command output.
_DEFAULT_MAX_OUTPUT_LINES = 100


class OutputCompressor:
    """Compresses tool outputs, file listings, and logs.

    All methods return the compressed representation as a string, with
    logging of how much was removed.
    """

    def __init__(
        self,
        max_output_chars: int = _DEFAULT_MAX_OUTPUT_CHARS,
        max_file_list_items: int = _DEFAULT_MAX_FILE_LIST_ITEMS,
        max_output_lines: int = _DEFAULT_MAX_OUTPUT_LINES,
    ) -> None:
        """Initialize the compressor.

        Args:
            max_output_chars: Maximum characters for any single output.
            max_file_list_items: Maximum items in a summarized file list.
            max_output_lines: Maximum lines for command output.
        """
        self._max_output_chars = max_output_chars
        self._max_file_list_items = max_file_list_items
        self._max_output_lines = max_output_lines
        logger.debug(
            "OutputCompressor initialized (max_chars=%d, max_items=%d, max_lines=%d)",
            max_output_chars,
            max_file_list_items,
            max_output_lines,
        )

    def compress_tool_output(self, output: str) -> str:
        """Truncate a tool output to fit within the configured character limit.

        Tries to cut at a sentence or newline boundary for readability.

        Args:
            output: The raw tool output string.

        Returns:
            The truncated output, with a note if truncation occurred.
        """
        if not output or len(output) <= self._max_output_chars:
            return output or ""

        # Try to cut at a newline boundary before the limit
        truncated = output[: self._max_output_chars]
        last_newline = truncated.rfind("\n")
        if last_newline > self._max_output_chars // 2:
            truncated = truncated[:last_newline]

        removed = len(output) - len(truncated)
        logger.info(
            "Truncated tool output: %d chars removed (%d → %d)",
            removed,
            len(output),
            len(truncated),
        )
        return f"{truncated}\n\n# ... [TRUNCATED: removed {removed} characters]"

    def compress_file_list(
        self,
        files: list[dict[str, Any]],
        important_extensions: set[str] | None = None,
    ) -> str:
        """Summarize a file list to a compact representation.

        Instead of sending every file with full metadata, this method:
        1. Shows total counts and directories.
        2. Lists "important" files (config, entry points, README) with metadata.
        3. Lists remaining files grouped by extension.

        Args:
            files: List of file metadata dicts (``path``, ``extension``,
                   ``size``, ``lines``).
            important_extensions: Extensions considered "important" for analysis.
                                  Defaults to Python, JS/TS, config files.

        Returns:
            A compact string representation of the file list.
        """
        if important_extensions is None:
            important_extensions = {
                ".py", ".js", ".ts", ".jsx", ".tsx",
                ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
                ".md", ".rst", ".txt",
                ".env", ".gitignore",
                ".dockerfile", "dockerfile",
                ".sh", ".bash",
                ".css", ".scss", ".html",
                ".go", ".rs", ".java", ".rb", ".php",
            }

        total = len(files)
        if total == 0:
            return "No files found."

        if total <= self._max_file_list_items:
            # Small enough to list fully
            lines: list[str] = [f"Total files: {total}"]
            for f in files:
                path = f.get("path", "?")
                ext = f.get("extension", "")
                size = f.get("size", 0)
                lines.append(f"  {path}  ({size} bytes)")
            return "\n".join(lines)

        # Separate important files
        important: list[dict[str, Any]] = []
        other: list[dict[str, Any]] = []
        directories: set[str] = set()

        for f in files:
            path = f.get("path", "")
            ext = f.get("extension", "").lower()
            # Extract top-level directory
            parts = path.split("/")
            if len(parts) > 1:
                directories.add(parts[0])

            if ext in important_extensions or self._is_important_file(path):
                important.append(f)
            else:
                other.append(f)

        # Sort important files by size (most relevant first)
        important.sort(key=lambda x: x.get("size", 0), reverse=True)

        # Limit important files shown
        if len(important) > self._max_file_list_items:
            important = important[: self._max_file_list_items]

        # Build compact representation
        result: list[str] = [
            f"Total files: {total}  |  Directories: {', '.join(sorted(directories)[:20])}",
            f"Important files ({len(important)} shown):",
        ]

        for f in important:
            path = f.get("path", "?")
            ext = f.get("extension", "")
            size = f.get("size", 0)
            lines = f.get("lines", 0)
            result.append(f"  [{ext}] {path}  ({size}b, {lines} lines)")

        # Group remaining files by extension
        if other:
            ext_counts: dict[str, int] = {}
            for f in other:
                ext = f.get("extension", "(unknown)").lower()
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

            result.append(f"Other files ({len(other)} total):")
            for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1])[:15]:
                ext_label = ext if ext else "(no extension)"
                result.append(f"  .{ext_label}: {count} files")

            hidden = len(other) - sum(c for _, c in list(ext_counts.items())[:15])
            if hidden > 0:
                result.append(f"  ... and {hidden} more files in other extensions")

        compressed = "\n".join(result)
        original_chars = sum(len(json.dumps(f, default=str)) for f in files)
        logger.info(
            "Compressed file list: %d files → %d chars (from ~%d chars)",
            total,
            len(compressed),
            original_chars,
        )
        return compressed

    def compress_command_output(self, output: str) -> str:
        """Compress a command output by keeping head and tail.

        Useful for long outputs like ``git log``, ``tree``, or test results.
        Keeps the first N/2 lines and last N/2 lines, summarizing the middle.

        Args:
            output: The raw command output string.

        Returns:
            A compressed string with head, summary, and tail.
        """
        if not output:
            return ""

        lines = output.split("\n")
        if len(lines) <= self._max_output_lines:
            return output

        half = self._max_output_lines // 2
        head = lines[:half]
        tail = lines[-half:]
        removed = len(lines) - self._max_output_lines

        compressed = "\n".join(head)
        compressed += f"\n\n# ... [TRUNCATED: removed {removed} lines]\n\n"
        compressed += "\n".join(tail)

        logger.info(
            "Compressed command output: %d lines → %d lines",
            len(lines),
            len(head) + len(tail),
        )
        return compressed

    def summarize_repetitive_logs(self, text: str) -> str:
        """Detect and summarize repetitive log patterns.

        For example, if the same warning or error appears dozens of times,
        this method condenses it into a single line with a count.

        Args:
            text: The log or output text to compress.

        Returns:
            Text with repetitive patterns summarized.
        """
        if not text:
            return ""

        lines = text.split("\n")
        # Count unique line frequencies
        line_counts: dict[str, int] = {}
        unique_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped in line_counts:
                line_counts[stripped] += 1
            else:
                line_counts[stripped] = 1
                unique_lines.append(stripped)

        # Only summarize if there's significant repetition
        total_before = len(lines)
        repeated = sum(1 for c in line_counts.values() if c > 3)
        if repeated < 2 and total_before < 20:
            return text

        result: list[str] = []
        summarized_count = 0
        for line in unique_lines:
            count = line_counts[line]
            if count > 3:
                result.append(f"{line}  [{count}x repeated]")
                summarized_count += count - 1
            else:
                for _ in range(count):
                    result.append(line)

        logger.info(
            "Summarized repetitive logs: %d → %d lines (%d duplicate lines collapsed)",
            total_before,
            len(result),
            summarized_count,
        )
        return "\n".join(result)

    @staticmethod
    def _is_important_file(path: str) -> bool:
        """Check if a file path is likely important for analysis.

        Args:
            path: The file path (relative to repo root).

        Returns:
            ``True`` if the file is likely important.
        """
        lower = path.lower()
        important_patterns = [
            "readme",
            "license",
            "contributing",
            "changelog",
            "setup.py",
            "setup.cfg",
            "pyproject.toml",
            "requirements",
            "dockerfile",
            "docker-compose",
            "makefile",
            "cmakelists",
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "cargo.toml",
            "go.mod",
            "pom.xml",
            "build.gradle",
            ".gitignore",
            ".env.example",
            "index.",
            "main.",
            "app.",
            "cli.",
            "cmd/",
            "internal/",
            "src/",
            "lib/",
        ]
        return any(pattern in lower for pattern in important_patterns)

    def compress_string(self, text: str, max_chars: int | None = None) -> str:
        """Generic string compression that combines truncation and summarization.

        Args:
            text: The text to compress.
            max_chars: Maximum characters. Defaults to ``self._max_output_chars``.

        Returns:
            Compressed text.
        """
        limit = max_chars or self._max_output_chars
        if not text or len(text) <= limit:
            return text or ""

        # First try repetitive log summarization
        summarized = self.summarize_repetitive_logs(text)
        if len(summarized) <= limit:
            return summarized

        # Then try line-based truncation
        line_compressed = self.compress_command_output(summarized)
        if len(line_compressed) <= limit:
            return line_compressed

        # Fall back to character truncation
        return self.compress_tool_output(line_compressed)

