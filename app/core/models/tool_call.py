# app/core/models/tool_call.py
from dataclasses import dataclass, field

@dataclass(slots=True)
class ToolCall:
    id: str = ""
    name: str = ""
    arguments: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
        }
