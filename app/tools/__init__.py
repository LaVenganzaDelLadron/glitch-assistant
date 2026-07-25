from app.tools.registry import ToolRegistry

from app.tools.filesystem import FileSystemTool
from app.tools.terminal import TerminalTool
from app.tools.git import GitTool


registry = ToolRegistry()

registry.register(FileSystemTool())
registry.register(TerminalTool())
registry.register(GitTool())