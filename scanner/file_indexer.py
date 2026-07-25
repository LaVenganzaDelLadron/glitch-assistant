"""File indexer — recursively walks a repository and builds a structured file index.

Skips:
    - Directories in IGNORE_DIRS (.git, node_modules, __pycache__, etc.)
    - Binary files (by extension)
    - Files larger than MAX_FILE_SIZE
    - Non-UTF-8 decodable files
"""

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
    "build",
    "dist",
    "coverage",
    ".next",
    "target",
    "vendor",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".eggs",
    "eggs",
    ".bzr",
    ".hg",
    ".svn",
    "CVS",
    ".idea",
    ".vscode",
    ".DS_Store",
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
    ".lock",
    ".db", ".sqlite", ".sqlite3",
})


class FileIndexer:
    """Recursively scans a repository directory and builds a structured file index.

    The index stores metadata for each file including path, extension, size,
    truncated content, and line count.
    """

    def scan(self, root: Path) -> list[dict[str, Any]]:
        """
        Recursively scan a repository and collect metadata and text content for eligible files.
        
        Parameters:
            root (Path): Directory to scan.
        
        Returns:
            list[dict[str, Any]]: File records containing the relative path, extension,
                size in bytes, text content, and line count. Content exceeding the
                configured limit is truncated.
        
        Raises:
            NotADirectoryError: If `root` is not a directory.
        """
        if not root.is_dir():
            raise NotADirectoryError(f"Repository root is not a directory: {root}")

        files: list[dict[str, Any]] = []
        scan_errors = 0

        for entry in root.rglob("*"):
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

            line_count = content.count("\n")
            if not content.endswith("\n"):
                line_count += 1

            # Truncate very large content
            if len(content) > _MAX_CONTENT_LENGTH:
                content = content[:_MAX_CONTENT_LENGTH] + "\n\n# ... [TRUNCATED]"

            files.append({
                "path": str(entry.relative_to(root)),
                "extension": entry.suffix or "(no extension)",
                "size": file_size,
                "content": content,
                "lines": line_count,
            })

        logger.info(
            "Scanned %s — %d files indexed, %d scan errors",
            root,
            len(files),
            scan_errors,
        )
        return files

