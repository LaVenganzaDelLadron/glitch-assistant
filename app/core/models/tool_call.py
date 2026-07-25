# app/core/models/tool_call.py
from dataclasses import dataclass, field\

@dataclass(slots=True)
class ToolCall:
    name: str
    arguments: dict = field(default_factory=dict)