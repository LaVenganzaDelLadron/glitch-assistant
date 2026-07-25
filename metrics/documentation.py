"""Documentation analysis — README, docstrings, comments, TODO/FIXME tracking."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DocumentationAnalyzer:
    """Analyzes documentation quality and coverage in a repository.

    Checks for:
        - README presence and quality
        - Docstrings / module-level documentation
        - Inline comment density
        - TODO, FIXME, HACK, XXX comment tracking
        - LICENSE, CONTRIBUTING, CHANGELOG presence
        - Overall documentation coverage estimate
    """

    def analyze(self, root: Path, file_index: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze repository documentation indicators and code documentation metrics.
        
        Parameters:
            root (Path): Repository root containing top-level documentation files.
            file_index (list[dict[str, Any]]): Indexed file data used to measure comments,
                markers, and Python module docstrings.
        
        Returns:
            dict[str, Any]: Metrics and findings for README, license, contributing,
                changelog, code-of-conduct, docstring coverage, comment density, and
                TODO/FIXME/HACK/XXX marker counts.
        """
        result: dict[str, Any] = {
            "has_readme": False,
            "readme_files": [],
            "readme_quality": "none",
            "has_license": False,
            "has_contributing": False,
            "has_changelog": False,
            "has_code_of_conduct": False,
            "docstring_coverage": 0.0,
            "comment_density": 0.0,
            "todo_count": 0,
            "fixme_count": 0,
            "hack_count": 0,
            "xxx_count": 0,
            "findings": [],
        }

        # Check root-level documentation files
        readme_files: list[str] = []
        for entry in root.iterdir():
            if not entry.is_file():
                continue
            name = entry.name.lower()

            if name.startswith("readme"):
                result["has_readme"] = True
                readme_files.append(entry.name)

            if name in ("license", "license.txt", "license.md", "license.apache-2.0", "license.mit"):
                result["has_license"] = True

            if name.startswith("contributing"):
                result["has_contributing"] = True

            if name.startswith("changelog") or name.startswith("history"):
                result["has_changelog"] = True

            if name.startswith("code_of_conduct") or name.startswith("codeofconduct"):
                result["has_code_of_conduct"] = True

        result["readme_files"] = readme_files

        # Assess README quality
        if result["has_readme"]:
            for rfile in readme_files:
                rpath = root / rfile
                try:
                    content = rpath.read_text(encoding="utf-8", errors="replace")
                    result["readme_quality"] = self._assess_readme_quality(content)
                    break
                except (UnicodeDecodeError, OSError):
                    continue

        # Count TODO/FIXME/HACK/XXX across all files
        total_comments = 0
        total_lines = 0

        for file_info in file_index:
            content = file_info.get("content", "")
            lines = file_info.get("lines", 0)
            total_lines += lines

            # Count inline comments
            comment_lines = self._count_comment_lines(file_info["path"], content)
            total_comments += comment_lines

            # Count markers
            result["todo_count"] += len(re.findall(r"(?i)\btodo\b", content))
            result["fixme_count"] += len(re.findall(r"(?i)\bfixme\b", content))
            result["hack_count"] += len(re.findall(r"(?i)\bhack\b", content))
            result["xxx_count"] += len(re.findall(r"(?i)\bxxx\b", content))

        # Comment density (comments per 100 lines)
        if total_lines > 0:
            result["comment_density"] = round((total_comments / total_lines) * 100, 2)

        # Estimate docstring coverage (simplified: count module-level docstrings)
        docstring_count = 0
        python_file_count = 0
        for file_info in file_index:
            if file_info["extension"] == ".py":
                python_file_count += 1
                content = file_info.get("content", "")
                if re.match(r'\s*(?:"""|\'\'\')', content.strip()):
                    docstring_count += 1

        if python_file_count > 0:
            result["docstring_coverage"] = round(
                (docstring_count / python_file_count) * 100, 1
            )

        # Build findings
        if result["todo_count"] > 0:
            result["findings"].append({
                "type": "todo_found",
                "description": f"Found {result['todo_count']} TODO(s) in codebase",
                "severity": "info",
            })
        if result["fixme_count"] > 0:
            result["findings"].append({
                "type": "fixme_found",
                "description": f"Found {result['fixme_count']} FIXME(s) — may indicate known issues",
                "severity": "medium",
            })
        if result["hack_count"] > 0:
            result["findings"].append({
                "type": "hack_found",
                "description": f"Found {result['hack_count']} HACK(s) — likely technical debt",
                "severity": "medium",
            })
        if not result["has_readme"]:
            result["findings"].append({
                "type": "missing_readme",
                "description": "Repository has no README file",
                "severity": "medium",
            })
        if not result["has_license"]:
            result["findings"].append({
                "type": "missing_license",
                "description": "Repository has no LICENSE file",
                "severity": "low",
            })

        logger.info(
            "Documentation analysis: README=%s, TODO=%d, FIXME=%d, "
            "docstring_cov=%.1f%%, comment_density=%.2f%%",
            result["readme_quality"],
            result["todo_count"],
            result["fixme_count"],
            result["docstring_coverage"],
            result["comment_density"],
        )

        return result

    def _assess_readme_quality(self, content: str) -> str:
        """Assess the quality of a README file.

        Args:
            content: The README content.

        Returns:
            ``"excellent"``, ``"good"``, or ``"minimal"``.
        """
        lines = content.strip().splitlines()
        if len(lines) < 5:
            return "minimal"
        if len(lines) > 50 and len(content) > 2000:
            return "excellent"
        if len(lines) > 15:
            return "good"
        return "minimal"

    def _count_comment_lines(self, path: str, content: str) -> int:
        """
        Count comment markers in file content using syntax inferred from the file extension.
        
        Parameters:
            path (str): File path used to determine the comment syntax.
            content (str): File content to inspect.
        
        Returns:
            int: Number of detected comment lines or comment markers.
        """
        ext = Path(path).suffix.lower()

        if ext in (".py", ".rb", ".sh", ".pl", ".pm", ".yaml", ".yml"):
            # Single-line comments start with #
            return len(re.findall(r'^\s*#', content, re.MULTILINE))
        elif ext in (".js", ".ts", ".jsx", ".tsx", ".java", ".kt", ".go", ".rs",
                     ".c", ".cpp", ".h", ".hpp", ".cs", ".swift", ".scala", ".dart"):
            # Single-line comments start with //
            return len(re.findall(r'^\s*//', content, re.MULTILINE))
        elif ext in (".html", ".htm", ".xml", ".vue", ".svelte"):
            # HTML comments <!-- -->
            return len(re.findall(r'<!--', content))
        elif ext in (".sql",):
            return len(re.findall(r'^\s*--', content, re.MULTILINE))
        else:
            # Generic: count lines with common comment markers
            return len(re.findall(r'^\s*[#//;]', content, re.MULTILINE))

