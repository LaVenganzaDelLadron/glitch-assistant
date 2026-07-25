"""Security scanner — detects hardcoded secrets, credentials, and vulnerabilities."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Regex patterns for detecting potential secrets / credentials.
SECRET_PATTERNS: list[tuple[str, str]] = [
    # AWS Access Key
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    # AWS Secret Key
    (r"(?i)aws[_\-\.]?secret[_\-\.]?access[_\-\.]?key\s*[=:]\s*['\"]([^'\"]+)['\"]", "AWS Secret Access Key"),
    # Private key headers
    (r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "Private Key"),
    # GitHub tokens
    (r"(?i)github[_\-\.]?token\s*[=:]\s*['\"]([^'\"]{10,})['\"]", "GitHub Token"),
    # Generic API keys / tokens
    (r"(?i)(?:api[_-]?key|api[_-]?secret|api[_-]?token)\s*[=:]\s*['\"]([^'\"]{8,})['\"]", "API Key/Token"),
    # Password assignments
    (r"""(?i)(?:password|passwd|pwd)\s*[=:]\s*['"]([^'"]{4,})['"]""", "Password"),
    # Connection strings
    (r"(?i)(?:connection[_\-\.]?string|connstr)\s*[=:]\s*['\"]([^'\"]+)['\"]", "Connection String"),
    # JWT tokens
    (r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}", "JWT Token"),
    # Slack tokens
    (r"xox[baprs]-[0-9a-zA-Z\-]{10,}", "Slack Token"),
    # Google API key pattern
    (r"AIza[0-9A-Za-z\-_]{35}", "Google API Key"),
    # Heroku API key
    (r"(?i)heroku[_\-\.]?api[_\-\.]?key\s*[=:]\s*['\"]([^'\"]+)['\"]", "Heroku API Key"),
    # MongoDB connection string
    (r"mongodb(?:\+srv)?://[^\s<>\"']+", "MongoDB Connection String"),
    # PostgreSQL connection string
    (r"postgres(?:ql)?://[^\s<>\"']+", "PostgreSQL Connection String"),
    # Redis connection string
    (r"redis://[^\s<>\"']+", "Redis Connection String"),
    # MySQL connection string
    (r"mysql://[^\s<>\"']+", "MySQL Connection String"),
]

# Files to always check for secrets (priority files).
_PRIORITY_CHECK_FILES: frozenset[str] = frozenset({
    ".env", ".env.example", ".env.local", ".env.production",
    "credentials", "credentials.json",
    "config.yml", "config.yaml", "config.json",
    "secrets.yml", "secrets.yaml",
    "docker-compose.yml", "docker-compose.yaml",
})


class SecurityScanner:
    """Scans a repository for security issues: hardcoded secrets, credentials, etc.

    Uses regex pattern matching to detect potential secrets in all text files.
    Also attempts to run ``bandit`` if available.
    """

    def scan(self, root: Path, file_index: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run security scans on the repository.

        Performs:
            1. Regex-based secret scanning across all indexed files.
            2. Bandit scan (Python-specific) if bandit is installed.

        Args:
            root: The root :class:`Path` of the cloned repository.
            file_index: The file index from :class:`FileIndexer`.

        Returns:
            A list of security findings, each containing:
                - ``type``: The type of finding (str)
                - ``severity``: ``"HIGH"``, ``"MEDIUM"``, or ``"LOW"`` (str)
                - ``file``: The relative file path (str)
                - ``line``: The line number (int or None)
                - ``description``: Description of the finding (str)
        """
        findings: list[dict[str, Any]] = []

        # 1. Regex-based secret scanning
        for file_info in file_index:
            content = file_info.get("content", "")
            rel_path = file_info.get("path", "")

            file_findings = self._scan_file_content(rel_path, content)
            findings.extend(file_findings)

        # 2. Bandit scan (if installed)
        bandit_findings = self._run_bandit(root)
        findings.extend(bandit_findings)

        # Deduplicate by (type, file, description)
        seen = set()
        unique_findings: list[dict[str, Any]] = []
        for finding in findings:
            key = (finding["type"], finding["file"], finding["description"])
            if key not in seen:
                seen.add(key)
                unique_findings.append(finding)

        logger.info(
            "Security scan complete — %d findings (HIGH: %d, MEDIUM: %d, LOW: %d)",
            len(unique_findings),
            sum(1 for f in unique_findings if f.get("severity") == "HIGH"),
            sum(1 for f in unique_findings if f.get("severity") == "MEDIUM"),
            sum(1 for f in unique_findings if f.get("severity") == "LOW"),
        )

        return unique_findings

    def _scan_file_content(self, rel_path: str, content: str) -> list[dict[str, Any]]:
        """Scan a single file's content for secret patterns.

        Args:
            rel_path: Relative path of the file.
            content: The file content as a string.

        Returns:
            A list of finding dicts for this file.
        """
        findings: list[dict[str, Any]] = []

        for pattern, secret_type in SECRET_PATTERNS:
            for match in re.finditer(pattern, content):
                line_number = content[:match.start()].count("\n") + 1

                severity = "HIGH"
                if "JWT" in secret_type or "Token" in secret_type:
                    severity = "MEDIUM"

                findings.append({
                    "type": secret_type,
                    "severity": severity,
                    "file": rel_path,
                    "line": line_number,
                    "description": f"Potential {secret_type} found",
                })

        return findings

    def _run_bandit(self, root: Path) -> list[dict[str, Any]]:
        """Run bandit security scanner if available.

        Args:
            root: The repository root path.

        Returns:
            A list of finding dicts from bandit.
        """
        import shutil

        if not shutil.which("bandit"):
            logger.debug("bandit not found, skipping bandit scan")
            return []

        try:
            import subprocess
            result = subprocess.run(
                ["bandit", "-r", str(root), "-f", "json", "-q"],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            logger.warning("bandit scan failed: %s", exc)
            return []

        if result.returncode not in (0, 1):  # bandit returns 1 when issues found
            logger.warning("bandit returned unexpected code %d", result.returncode)
            return []

        try:
            import json
            data = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Could not parse bandit output: %s", exc)
            return []

        findings: list[dict[str, Any]] = []
        for issue in data.get("results", []):
            findings.append({
                "type": f"bandit: {issue.get('test_name', 'unknown')}",
                "severity": issue.get("issue_severity", "MEDIUM").upper(),
                "file": issue.get("filename", ""),
                "line": issue.get("line_number"),
                "description": issue.get("issue_text", ""),
            })

        return findings

