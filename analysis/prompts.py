"""System prompts and instructions for AI-powered repository analysis.

IMPORTANT: The LLM should NOT be instructed to execute commands or call tools.
All command execution is handled by Python before the LLM is invoked.
The LLM receives ONLY structured data and produces analysis.
"""

SYSTEM_PROMPT = """You are an expert software engineer and code reviewer.
Your task is to analyze a repository and produce a comprehensive,
actionable report about its quality, structure, and potential improvements.

You will receive structured repository data including:
- File structure and metadata
- Language distribution
- Security scan results
- Complexity metrics
- Documentation analysis
- Git statistics
- Dependency information

Analyze this data carefully and produce a detailed report.
Focus on findings that provide real value to the developer maintaining this repository.
"""

ANALYSIS_INSTRUCTIONS = """
Analyze the repository across these dimensions:

## Architecture & Organization
- Is the project well-structured with clear separation of concerns?
- Does the folder layout follow language/framework conventions?

## Documentation
- Is there a README? Is it informative?
- Are there docstrings, inline comments, or API docs?
- TODO/FIXME/HACK counts indicating technical debt.

## Coding Style & Quality
- Consistent formatting?
- Naming conventions followed?
- Type hints used (in typed languages)?
- Unused imports, dead code, or commented-out code?

## Security
- Hardcoded secrets, API keys, tokens, passwords?
- Security scanner findings analysis.

## Dependency Management
- Are dependencies pinned to specific versions?
- Are there outdated or vulnerable dependencies?
- Is there a lockfile?

## Complexity
- Are there functions/methods that are too long (>50 lines)?
- High cyclomatic complexity?
- Duplicate code blocks?

## Testing
- Are there tests? (unit, integration, e2e)
- What's the test coverage estimate?
- CI/CD pipeline configured?

## Performance
- Obvious performance bottlenecks?
- Unnecessary allocations or I/O operations?

## Maintainability
- Is the code easy to understand and modify?
- Configuration hardcoded vs externalized?
- Error handling comprehensive?

## Docker & DevOps
- Dockerfile present? Multi-stage builds?
- CI/CD configuration?
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
