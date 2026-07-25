# app/core/models/message.py
from dataclasses import dataclass, field
from typing import Literal

Role = Literal[
    "system",
    "user",
    "assistant",
    "tool",
]

@dataclass(slots=True)
class Message:
    role: Role
    content: str
    tool_call_id: str = ""
    tool_calls: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "role": self.role,
        }

        if self.role == "tool":
            d["tool_call_id"] = self.tool_call_id
            d["content"] = str(self.content)
        elif self.role == "assistant" and self.tool_calls:
            d["content"] = self.content or ""
            d["tool_calls"] = [
                tc.to_dict() if hasattr(tc, "to_dict") else tc
                for tc in self.tool_calls
            ]
        else:
            d["content"] = self.content

        return d
