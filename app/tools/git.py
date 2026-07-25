#app/tools/git.py
from __future__ import annotations
import subprocess
from pathlib import Path
from app.tools.base import Tool, ToolResult, ToolOperation


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

            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr or None,
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def operations(self) -> list[ToolOperation]:
        return [
            ToolOperation(
                name=f"{self.name}.run",
                description="Execute a Git command inside the repository.",
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
