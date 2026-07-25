"""Language detection — identifies programming languages used in a repository."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Mapping of file extensions to language names.
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript (JSX)",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (TSX)",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin (Script)",
    ".scala": "Scala",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".r": "R",
    ".lua": "Lua",
    ".pl": "Perl",
    ".pm": "Perl Module",
    ".sh": "Shell",
    ".bash": "Shell (Bash)",
    ".zsh": "Shell (Zsh)",
    ".fish": "Shell (Fish)",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".astro": "Astro",
    ".elm": "Elm",
    ".clj": "Clojure",
    ".cljs": "ClojureScript",
    ".ex": "Elixir",
    ".exs": "Elixir (Script)",
    ".erl": "Erlang",
    ".hrl": "Erlang Header",
    ".hs": "Haskell",
    ".lhs": "Literate Haskell",
    ".ml": "OCaml",
    ".mli": "OCaml Interface",
    ".fs": "F#",
    ".fsx": "F# Script",
    ".zig": "Zig",
    ".nim": "Nim",
    ".cr": "Crystal",
    ".dart": "Dart",
    ".groovy": "Groovy",
    ".gradle": "Gradle",
    ".kt": "Kotlin",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".xml": "XML",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "Configuration",
    ".conf": "Configuration",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".tex": "LaTeX",
    ".dockerfile": "Dockerfile",
    "Dockerfile": "Dockerfile",
    ".makefile": "Makefile",
    "Makefile": "Makefile",
    ".cmake": "CMake",
}

# Configuration filenames that indicate language/ecosystem.
ECOSYSTEM_FILES: dict[str, str] = {
    "requirements.txt": "Python",
    "Pipfile": "Python",
    "pyproject.toml": "Python",
    "setup.py": "Python",
    "setup.cfg": "Python",
    "package.json": "JavaScript/Node.js",
    "package-lock.json": "JavaScript/Node.js",
    "yarn.lock": "JavaScript/Node.js",
    "pnpm-lock.yaml": "JavaScript/Node.js",
    "tsconfig.json": "TypeScript",
    "Cargo.toml": "Rust",
    "Cargo.lock": "Rust",
    "go.mod": "Go",
    "go.sum": "Go",
    "Gemfile": "Ruby",
    "Gemfile.lock": "Ruby",
    "build.gradle": "Java/Gradle",
    "pom.xml": "Java/Maven",
    "build.sbt": "Scala/SBT",
    "composer.json": "PHP",
    "composer.lock": "PHP",
    "mix.exs": "Elixir",
    "rebar.config": "Erlang",
    "stack.yaml": "Haskell",
    "dune-project": "OCaml",
    "pubspec.yaml": "Dart/Flutter",
    "Podfile": "Swift/CocoaPods",
    "Cartfile": "Swift/Carthage",
    "Package.swift": "Swift/SPM",
}


class LanguageDetector:
    """Detects programming languages present in a repository from its file index."""

    def detect(self, file_index: list[dict[str, Any]]) -> dict[str, float]:
        """
        Determine the percentage distribution of recognized languages in a file index.
        
        Parameters:
            file_index (list[dict[str, Any]]): File metadata entries to analyze.
        
        Returns:
            dict[str, float]: Language names mapped to their percentages among recognized
            files, sorted in descending order and excluding values below 1%.
        """
        if not file_index:
            return {}

        language_counts: dict[str, int] = {}
        total_files = 0

        for file_info in file_index:
            path = file_info.get("path", "")
            extension = file_info.get("extension", "")

            language = self._detect_language(path, extension)
            if language:
                language_counts[language] = language_counts.get(language, 0) + 1
                total_files += 1

        if total_files == 0:
            return {}

        # Convert to percentages
        percentages: dict[str, float] = {}
        for lang, count in language_counts.items():
            pct = round((count / total_files) * 100, 1)
            if pct >= 1.0:
                percentages[lang] = pct

        # Sort by percentage descending
        sorted_langs: dict[str, float] = dict(
            sorted(percentages.items(), key=lambda x: -x[1])
        )

        logger.info(
            "Detected %d languages: %s",
            len(sorted_langs),
            sorted_langs,
        )
        return sorted_langs

    def _detect_language(self, path: str, extension: str) -> str | None:
        """Detect the language for a single file.

        Args:
            path: The relative file path.
            extension: The file extension (e.g. ``.py``).

        Returns:
            A language name string, or ``None`` if unknown.
        """
        # Check ecosystem/config files first (by filename)
        filename = Path(path).name
        if filename in ECOSYSTEM_FILES:
            return ECOSYSTEM_FILES[filename]

        # Check Dockerfile / Makefile (no extension)
        if filename == "Dockerfile":
            return "Dockerfile"
        if filename == "Makefile":
            return "Makefile"

        # Check by extension
        if extension in EXTENSION_TO_LANGUAGE:
            return EXTENSION_TO_LANGUAGE[extension]

        return None

