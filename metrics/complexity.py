"""Complexity analysis — cyclomatic complexity, code size metrics, and code smells."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ComplexityAnalyzer:
    """Analyzes code complexity in a repository.

    Attempts to use tools like ``radon``, ``pylint``, and basic file-level
    heuristics to identify complex and hard-to-maintain code.
    """

    def analyze(self, root: Path, file_index: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run complexity analysis on the repository.

        Performs:
            1. Radon cyclomatic complexity analysis (if radon installed).
            2. Large file / long function detection via heuristics.
            3. Line count distribution statistics.

        Args:
            root: The root :class:`Path` of the cloned repository.
            file_index: The file index from :class:`FileIndexer`.

        Returns:
            A list of complexity findings, each containing:
                - ``type``: The type of complexity issue (str)
                - ``file``: The relative file path (str, optional)
                - ``description``: Description of the finding (str)
                - ``value``: Numeric value if applicable (int or float, optional)
        """
        findings: list[dict[str, Any]] = []

        # 1. Radon CC analysis (Python files)
        radon_findings = self._run_radon(root)
        findings.extend(radon_findings)

        # 2. Pylint analysis
        pylint_findings = self._run_pylint(root)
        findings.extend(pylint_findings)

        # 3. Heuristic: large files (> 500 lines)
        large_files = self._find_large_files(file_index)
        findings.extend(large_files)

        # 4. Line count distribution
        dist = self._line_count_distribution(file_index)
        findings.append({
            "type": "code_distribution",
            "file": None,
            "description": (
                f"File size distribution: "
                f"small (<50 lines): {dist['small']}, "
                f"medium (50-200): {dist['medium']}, "
                f"large (200-500): {dist['large']}, "
                f"xlarge (>500): {dist['xlarge']}"
            ),
            "value": dist,
        })

        logger.info(
            "Complexity analysis complete — %d findings",
            len(findings),
        )
        return findings

    def _run_radon(self, root: Path) -> list[dict[str, Any]]:
        """Run radon cyclomatic complexity analysis on Python files.

        Args:
            root: The repository root path.

        Returns:
            A list of finding dicts from radon.
        """
        import shutil

        if not shutil.which("radon"):
            logger.debug("radon not found, skipping cyclomatic complexity")
            return []

        findings: list[dict[str, Any]] = []

        try:
            result = subprocess.run(
                ["radon", "cc", str(root), "--min", "C", "--json"],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            logger.warning("radon cc analysis failed: %s", exc)
            return []

        if result.returncode != 0:
            return []

        try:
            import json
            data = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Could not parse radon output: %s", exc)
            return []

        for file_path, blocks in data.items():
            for block in blocks:
                if block.get("rank") in ("C", "D", "E", "F"):
                    findings.append({
                        "type": "high_cyclomatic_complexity",
                        "file": file_path,
                        "description": (
                            f"Function '{block.get('name', 'unknown')}' "
                            f"has cyclomatic complexity {block.get('complexity', '?')} "
                            f"(rank {block.get('rank', '?')})"
                        ),
                        "value": block.get("complexity"),
                    })

        return findings

    def _run_pylint(self, root: Path) -> list[dict[str, Any]]:
        """Run pylint analysis if available.

        Args:
            root: The repository root path.

        Returns:
            A list of finding dicts from pylint.
        """
        import shutil

        if not shutil.which("pylint"):
            logger.debug("pylint not found, skipping pylint analysis")
            return []

        findings: list[dict[str, Any]] = []

        try:
            result = subprocess.run(
                ["pylint", str(root), "--exit-zero", "--output-format", "text"],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            logger.warning("pylint analysis failed: %s", exc)
            return []

        # Parse the text output for key issues
        for line in result.stdout.splitlines():
            if "C0" in line or "R0" in line or "W0" in line or "E0" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    file_part = parts[0].strip() if parts[0].strip() else str(root)
                    findings.append({
                        "type": "pylint",
                        "file": file_part,
                        "description": line.strip(),
                        "value": None,
                    })

        return findings

    def _find_large_files(self, file_index: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find files with excessive line counts.

        Args:
            file_index: The file index.

        Returns:
            A list of finding dicts for large files.
        """
        findings: list[dict[str, Any]] = []
        for file_info in file_index:
            lines = file_info.get("lines", 0)
            if lines > 500:
                findings.append({
                    "type": "large_file",
                    "file": file_info["path"],
                    "description": (
                        f"File has {lines} lines — "
                        f"consider splitting into smaller modules"
                    ),
                    "value": lines,
                })
        return findings

    def _line_count_distribution(self, file_index: list[dict[str, Any]]) -> dict[str, int]:
        """Compute the distribution of file sizes.

        Args:
            file_index: The file index.

        Returns:
            A dict with counts for ``small``, ``medium``, ``large``, ``xlarge``.
        """
        dist: dict[str, int] = {"small": 0, "medium": 0, "large": 0, "xlarge": 0}
        for file_info in file_index:
            lines = file_info.get("lines", 0)
            if lines < 50:
                dist["small"] += 1
            elif lines < 200:
                dist["medium"] += 1
            elif lines < 500:
                dist["large"] += 1
            else:
                dist["xlarge"] += 1
        return dist

