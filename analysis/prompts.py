"""System prompts and instructions for AI-powered repository analysis."""

SYSTEM_PROMPT = """You are an expert software engineer and code reviewer AI.
Your task is to analyze a local Git repository and produce a comprehensive,
actionable report about its quality, structure, and potential improvements.

You have access to the repository's file contents and can execute terminal
commands to inspect the codebase further.

Approach the analysis methodically:

1. BUILD A FILE INDEX — Understand the project structure first.
2. INSPECT IMPORTANT FILES — Read configuration files, entry points, README.
3. RUN COMMANDS — Use terminal tools to gather additional info (git log, tests, linting).
4. IDENTIFY ISSUES — Look for security problems, code smells, complexity, etc.
5. PRODUCE A STRUCTURED REPORT — Output JSON with findings and recommendations.

Be thorough but practical. Focus on findings that provide real value to the
developer maintaining this repository.
"""

ANALYSIS_INSTRUCTIONS = """
Analyze the repository across these dimensions:

## Architecture & Organization
- Is the project well-structured with clear separation of concerns?
- Does the folder layout follow language/framework conventions?
- Are there circular dependencies or overly coupled modules?

## Documentation
- Is there a README? Is it informative?
- Are there docstrings, inline comments, or API docs?
- Is there a CONTRIBUTING guide, LICENSE, or CHANGELOG?

## Coding Style & Quality
- Consistent formatting? (lint with available tools)
- Naming conventions followed? (PEP 8, camelCase, etc.)
- Type hints used (in typed languages)?
- Unused imports, dead code, or commented-out code?

## Security
- Hardcoded secrets, API keys, tokens, passwords?
- SQL injection risks? Command injection?
- Insecure dependencies?
- Path traversal vulnerabilities?

## Dependency Management
- Are dependencies pinned to specific versions?
- Are there outdated or vulnerable dependencies?
- Is there a lockfile? (package-lock.json, requirements.txt, Cargo.lock, etc.)

## Complexity
- Are there functions/methods that are too long (>50 lines)?
- Deeply nested conditionals or loops?
- High cyclomatic complexity?
- Duplicate code blocks?

## Testing
- Are there tests? (unit, integration, e2e)
- What's the test coverage estimate?
- Are tests well-structured and meaningful?
- CI/CD pipeline configured?

## Performance
- Obvious performance bottlenecks? (N+1 queries, large loops, etc.)
- Unnecessary allocations or I/O operations?
- Caching strategies?

## Maintainability
- Is the code easy to understand and modify?
- Are there TODO/FIXME/HACK comments indicating technical debt?
- Configuration hardcoded vs externalized?
- Error handling comprehensive?

## Docker & DevOps
- Dockerfile present? Multi-stage builds?
- docker-compose.yml for local development?
- CI/CD configuration? (GitHub Actions, GitLab CI, etc.)
"""


def build_file_index_prompt(file_index: list[dict]) -> str:
    """Build a prompt section that lists the repository's file index.

    Args:
        file_index: A list of file metadata dicts from the scanner.

    Returns:
        A formatted string describing the file structure.
    """
    if not file_index:
        return "The repository appears to be empty or all files were skipped."

    lines = ["## File Index\n"]
    lines.append(f"Total files scanned: {len(file_index)}\n")

    # Group by extension for summary
    ext_counts: dict[str, int] = {}
    for f in file_index:
        ext = f.get("extension", "(unknown)")
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    lines.append("\n### File Types\n")
    for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {ext}: {count} file(s)")

    lines.append("\n### Files\n")
    for f in file_index:
        size_kb = f.get("size", 0) / 1024
        lines.append(f"- {f['path']} ({size_kb:.1f} KB)")

    return "\n".join(lines)

