#app/core/memory/conversation.py
from __future__ import annotations
from collections import deque
from app.core.models.message import Message


class ConversationMemory:
    def __init__(self, max_messages: int = 20):
        self._messages: deque[Message] = deque(maxlen=max_messages)

    def add(self, message: Message) -> None:
        self._messages.append(message)

    def add_user(self, content: str) -> None:
        self.add(
            Message(
                role="user",
                content=content,
            )
        )

    def add_assistant(self, content: str) -> None:
        self.add(
            Message(
                role="assistant",
                content=content,
            )
        )

    def add_system(self, content: str) -> None:
        self.add(
            Message(
                role="system",
                content=content,
            )
        )

    def remove_last(self) -> None:
        if self._messages:
            self._messages.pop()

    def clear(self) -> None:
        self._messages.clear()

    def messages(self) -> list[Message]:
        return list(self._messages)

    def api_messages(self) -> list[dict]:
        return [m.to_dict() for m in self._messages]

    def __len__(self) -> int:
        return len(self._messages)

    def __iter__(self):
        return iter(self._messages)