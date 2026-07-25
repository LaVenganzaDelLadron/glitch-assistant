#app/tools/filesystem.py
from __future__ import annotations
from pathlib import Path
from app.tools.base import Tool, ToolResult, ToolOperation


class FileSystemTool(Tool):

    name = "filesystem"
    description = "Read and write files, list directories, check file existence."

    def read_file(self, path: str) -> ToolResult:
        try:
            return ToolResult(
                success=True,
                output=Path(path).read_text(encoding="utf-8"),
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def write_file(self, path: str, content: str) -> ToolResult:
        try:
            Path(path).write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                output="File written successfully.",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def exists(self, path: str) -> ToolResult:
        try:
            return ToolResult(
                success=True,
                output=Path(path).exists(),
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def list_directory(self, path: str) -> ToolResult:
        try:
            return ToolResult(
                success=True,
                output=[str(p) for p in Path(path).iterdir()],
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def operations(self) -> list[ToolOperation]:
        return [
            ToolOperation(
                name=f"{self.name}.read_file",
                description="Read the contents of a file at the given path.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute path to the file.",
                        },
                    },
                    "required": ["path"],
                },
                fn=self.read_file,
            ),
            ToolOperation(
                name=f"{self.name}.write_file",
                description="Write content to a file at the given path. Creates parent directories if needed.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute path to the file.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file.",
                        },
                    },
                    "required": ["path", "content"],
                },
                fn=self.write_file,
            ),
            ToolOperation(
                name=f"{self.name}.exists",
                description="Check if a file or directory exists at the given path.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to check.",
                        },
                    },
                    "required": ["path"],
                },
                fn=self.exists,
            ),
            ToolOperation(
                name=f"{self.name}.list_directory",
                description="List the contents of a directory.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute path to the directory.",
                        },
                    },
                    "required": ["path"],
                },
                fn=self.list_directory,
            ),
        ]
