# app/core/models/message.py
from dataclasses import dataclass
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

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
        }