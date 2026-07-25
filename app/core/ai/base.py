#app/core/ai/base.py
from abc import ABC, abstractmethod
from app.core.models.response import AIResponse


class LLMProvider(ABC):

    @abstractmethod
    def generate(self, prompt: str, history=None, tool_result=None, system_prompt=None, tools=None) -> AIResponse:
        raise NotImplementedError
