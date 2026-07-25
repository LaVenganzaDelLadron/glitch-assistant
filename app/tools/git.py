#app/tools/git.py
from __future__ import annotations
import subprocess
from pathlib import Path
from app.tools.base import Tool, ToolResult, ToolOperation
from app.core.utils.output_compressor import compress_output


class GitTool(Tool):

    name = "git"
    description = "Execute Git commands."

    def run(self, command: str, cwd: str = "") -> ToolResult:
        try:
            working_dir = cwd if cwd else str(Path.cwd())
            result = subprocess.run(
                ["git"] + command.split(),
                cwd=working_dir,
                capture_output=True,
                text=True,
            )

            raw_output = result.stdout if result.returncode == 0 else (result.stderr or result.stdout)
            error_output = result.stderr if result.returncode != 0 else None

            # Apply compression: binary/JSON/HTML detection + text truncation
            compressed = compress_output(raw_output)

            return ToolResult(
                success=result.returncode == 0,
                content=compressed.content,
                error=error_output or (compressed.summary if compressed.truncated else None),
                truncated=compressed.truncated,
                original_length=compressed.original_length,
                metadata={
                    "returncode": result.returncode,
                    "original_type": compressed.original_type,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=str(e),
            )

    def operations(self) -> list[ToolOperation]:
        return [
            ToolOperation(
                name=f"{self.name}.run",
                description="Execute a Git command inside the repository. Long outputs are automatically summarized.",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Git command to run (e.g. 'status', 'log --oneline -5').",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "Working directory for the git command.",
                        },
                    },
                    "required": ["command"],
                },
                fn=self.run,
            ),
        ]
