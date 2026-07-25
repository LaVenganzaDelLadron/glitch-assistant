"""Repository cloning utilities — clone with ``git clone --depth 1`` into a temp dir."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)


class CloneError(Exception):
    """Raised when a repository clone operation fails."""


class RepoCloner:
    """Clones a GitHub repository into a temporary directory and cleans up afterwards.

    Usage as a context manager::

        cloner = RepoCloner()
        with cloner.clone("https://github.com/owner/repo.git") as repo_path:
            # work with repo_path
            ...
        # temp directory is automatically removed on exit.
    """

    def __init__(self, timeout: int = 120) -> None:
        """Initialize the cloner.

        Args:
            timeout: Maximum time in seconds to wait for the clone operation.
        """
        self._timeout = timeout
        self._temp_dir: Path | None = None

    def clone(self, url: str) -> Generator[Path, None, None]:
        """Clone a repository into a temporary directory.

        Args:
            url: The HTTPS git clone URL of the repository.

        Yields:
            The :class:`Path` to the temporary directory containing the cloned repo.

        Raises:
            CloneError: If the clone fails for any reason (network, invalid URL, etc.).
        """
        self._temp_dir = Path(tempfile.mkdtemp(prefix="glitch_repo_"))
        logger.info("Cloning %s into temporary directory %s", url, self._temp_dir)

        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", url, str(self._temp_dir)],
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            self._cleanup()
            raise CloneError(
                f"Clone operation timed out after {self._timeout} seconds "
                f"for URL: {url}"
            )
        except FileNotFoundError:
            self._cleanup()
            raise CloneError("Git executable not found. Is git installed on the system?")

        if result.returncode != 0:
            self._cleanup()
            error_msg = result.stderr.strip() or "Unknown clone error"
            raise CloneError(f"Failed to clone {url}: {error_msg}")

        logger.info(
            "Successfully cloned %s (%d bytes stderr)",
            url,
            len(result.stderr),
        )

        try:
            yield self._temp_dir
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        """Remove the temporary directory if it exists."""
        if self._temp_dir is not None and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            logger.info("Cleaned up temporary directory: %s", self._temp_dir)
            self._temp_dir = None

