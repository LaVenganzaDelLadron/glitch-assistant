"""Local repository scanner — walks the file tree and records file metadata."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Directories to skip during recursive scanning.
IGNORE_DIRS: frozenset[str] = frozenset({
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "coverage",
    ".next",
    "target",
    "vendor",
})

# Maximum file size in bytes to read (10 MB).
_MAX_FILE_SIZE = 10 * 1024 * 1024

# Maximum characters to store per file (100 KB).
_MAX_CONTENT_LENGTH = 100_000

# Binary file extensions to skip entirely.
BINARY_EXTENSIONS: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv",
    ".pyc", ".pyo", ".pyd",
    ".whl", ".egg", ".egg-info",
    ".o", ".a", ".lib", ".obj",
    ".class", ".jar",
    ".wasm",
    ".lock",  # package-lock.json, yarn.lock etc. (too large/noisy)
})


class RepoScanner:
    """Scans a locally cloned repository and builds a structured file index."""

    def scan(self, root: Path) -> list[dict[str, Any]]:
        """Walk the repository directory tree and collect file information.

        Skips:
            - Directories listed in :const:`IGNORE_DIRS`.
            - Binary files (by extension).
            - Files larger than :const:`_MAX_FILE_SIZE`.
            - Files with non-UTF-8 encodable content.

        Args:
            root: The root :class:`Path` of the cloned repository.

        Returns:
            A list of dicts, each containing:
                - ``path``: Relative path from repository root (str)
                - ``extension``: File extension (str, e.g. ``.py``)
                - ``size``: File size in bytes (int)
                - ``content``: Truncated text content (str)
        """
        if not root.is_dir():
            raise NotADirectoryError(f"Repository root is not a directory: {root}")

        files: list[dict[str, Any]] = []
        scan_errors = 0

        for entry in root.rglob("*"):
            # Skip directories
            if not entry.is_file():
                continue

            # Check ignore patterns on all path parts
            if any(part in IGNORE_DIRS for part in entry.parts):
                continue

            # Skip binary extensions
            if entry.suffix.lower() in BINARY_EXTENSIONS:
                continue

            # Check file size before reading
            try:
                file_size = entry.stat().st_size
            except OSError:
                scan_errors += 1
                continue

            if file_size > _MAX_FILE_SIZE:
                logger.debug("Skipping large file: %s (%d bytes)", entry, file_size)
                continue

            # Read text content
            try:
                content = entry.read_text(encoding="utf-8", errors="replace")
            except (UnicodeDecodeError, OSError) as exc:
                logger.debug("Skipping unreadable file %s: %s", entry, exc)
                scan_errors += 1
                continue

            # Truncate very large content
            if len(content) > _MAX_CONTENT_LENGTH:
                content = content[:_MAX_CONTENT_LENGTH] + "\n\n# ... [TRUNCATED]"

            files.append({
                "path": str(entry.relative_to(root)),
                "extension": entry.suffix or "(no extension)",
                "size": file_size,
                "content": content,
            })

        logger.info(
            "Scanned %s — %d files indexed, %d scan errors",
            root,
            len(files),
            scan_errors,
        )
        return files

