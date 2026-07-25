#app/tools/terminal.py
from __future__ import annotations
import subprocess
from app.tools.base import Tool, ToolResult, ToolOperation


class TerminalTool(Tool):

    name = "terminal"
    description = "Execute shell commands in the terminal."

    def run(self, command: str) -> ToolResult:
        try:
            result = subprocess.run(
                command,
                shell=True,
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
                description="Execute a shell command and return its stdout and stderr.",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The shell command to execute.",
                        },
                    },
                    "required": ["command"],
                },
                fn=self.run,
            ),
        ]
