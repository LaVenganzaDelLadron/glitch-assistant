# app/core/models/response.py
from dataclasses import dataclass
from app.core.models.usage import Usage


@dataclass(slots=True)
class AIResponse:
    content: str
    model: str
    usage: Usage
    finish_reason: str | None = None