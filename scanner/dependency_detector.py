"""Dependency detection — identifies dependency management files and their contents."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Known dependency / config filenames and their ecosystem names.
DEPENDENCY_FILES: dict[str, str] = {
    "requirements.txt": "Python (pip)",
    "Pipfile": "Python (pipenv)",
    "Pipfile.lock": "Python (pipenv lock)",
    "pyproject.toml": "Python (poetry/pdm)",
    "setup.py": "Python (setuptools)",
    "setup.cfg": "Python (setuptools config)",
    "package.json": "Node.js (npm)",
    "package-lock.json": "Node.js (npm lock)",
    "yarn.lock": "Node.js (yarn lock)",
    "pnpm-lock.yaml": "Node.js (pnpm lock)",
    "Cargo.toml": "Rust (Cargo)",
    "Cargo.lock": "Rust (Cargo lock)",
    "go.mod": "Go (modules)",
    "go.sum": "Go (modules checksum)",
    "Gemfile": "Ruby (Bundler)",
    "Gemfile.lock": "Ruby (Bundler lock)",
    "build.gradle": "Java/Gradle",
    "pom.xml": "Java/Maven",
    "build.sbt": "Scala/SBT",
    "composer.json": "PHP (Composer)",
    "composer.lock": "PHP (Composer lock)",
    "mix.exs": "Elixir (Mix)",
    "rebar.config": "Erlang (Rebar)",
    "stack.yaml": "Haskell (Stack)",
    "pubspec.yaml": "Dart/Flutter (pub)",
    "Podfile": "CocoaPods",
    "Cartfile": "Carthage",
    "Package.swift": "Swift Package Manager",
}


class DependencyDetector:
    """Scans a repository for dependency management files and extracts their contents."""

    def detect(self, root: Path) -> list[dict[str, Any]]:
        """Find and read dependency files in the repository.

        Searches the repository root and one level deep for known dependency
        filenames.

        Args:
            root: The root :class:`Path` of the cloned repository.

        Returns:
            A list of dicts, each containing:
                - ``file``: Relative path to the dependency file (str)
                - ``ecosystem``: Description of the package ecosystem (str)
                - ``content``: The file content (str, truncated to 5000 chars)
        """
        dependencies: list[dict[str, Any]] = []

        for filename, ecosystem in DEPENDENCY_FILES.items():
            # Check root level
            file_path = root / filename
            if file_path.is_file():
                content = self._read_file(file_path)
                dependencies.append({
                    "file": filename,
                    "ecosystem": ecosystem,
                    "content": content,
                })
                continue

            # Check one level deep
            for subdir in root.iterdir():
                if subdir.is_dir():
                    nested_path = subdir / filename
                    if nested_path.is_file():
                        rel_path = str(nested_path.relative_to(root))
                        content = self._read_file(nested_path)
                        dependencies.append({
                            "file": rel_path,
                            "ecosystem": ecosystem,
                            "content": content,
                        })

        logger.info(
            "Found %d dependency files in %s",
            len(dependencies),
            root,
        )
        return dependencies

    def _read_file(self, path: Path) -> str:
        """Read a file and return its content, truncated if necessary.

        Args:
            path: Absolute path to the file.

        Returns:
            The file content as a string, or an error message if unreadable.
        """
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            if len(content) > 5_000:
                content = content[:5_000] + "\n\n# ... [TRUNCATED]"
            return content
        except (UnicodeDecodeError, OSError) as exc:
            logger.warning("Could not read dependency file %s: %s", path, exc)
            return f"[Error reading file: {exc}]"

