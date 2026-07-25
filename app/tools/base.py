#app/tools/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class ToolResult:
    success: bool
    output: Any = None
    error: str | None = None


@dataclass(slots=True)
class ToolParameter:
    """JSON Schema for a single parameter."""
    type: str
    description: str = ""
    enum: list[str] | None = None
    default: Any = None


@dataclass(slots=True)
class ToolOperation:
    """A callable operation exposed as a tool to the LLM."""
    name: str
    description: str
    parameters: dict
    fn: Callable[..., ToolResult]


class Tool(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    def operations(self) -> list[ToolOperation]:
        raise NotImplementedError
