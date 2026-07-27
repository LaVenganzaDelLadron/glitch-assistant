"""Tests for app.core.ai.groq.generate().

The PR change under test adds ``tool_choice="none"`` to the
``chat.completions.create`` call. These tests exercise the full function
behavior, with special attention to that argument being forwarded correctly.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from openai import APIError

import app.core.ai.groq as groq_module
from app.core.ai.llm_error import LLMError
from app.core.config.configuration_error import ConfigurationError
from app.core.config.settings import Settings


def _settings(**overrides: Any) -> Settings:
    defaults = dict(
        api_key="fake-key",
        model="test-model",
        base_url="https://example.invalid/v1",
        timeout=30.0,
    )
    defaults.update(overrides)
    return Settings(**defaults)


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, response: _FakeResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeOpenAI:
    """Stand-in for openai.OpenAI that records constructor kwargs."""

    last_instance: "_FakeOpenAI | None" = None

    def __init__(self, **kwargs: Any) -> None:
        self.init_kwargs = kwargs
        self.chat = _FakeChat(_FakeCompletions())
        _FakeOpenAI.last_instance = self


class TestGenerateValidation:
    def test_generate_raises_on_empty_prompt(self) -> None:
        with pytest.raises(LLMError, match="Prompt cannot be empty"):
            groq_module.generate("", history=[])

    def test_generate_raises_on_whitespace_only_prompt(self) -> None:
        with pytest.raises(LLMError, match="Prompt cannot be empty"):
            groq_module.generate("   ", history=[])

    def test_generate_wraps_configuration_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_get_settings() -> Settings:
            raise ConfigurationError("GROQ_API_KEY is required.")

        monkeypatch.setattr(groq_module, "get_settings", fake_get_settings)

        with pytest.raises(LLMError, match="GROQ_API_KEY is required"):
            groq_module.generate("hello", history=[])


class TestGenerateSuccess:
    def test_generate_passes_tool_choice_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(groq_module, "get_settings", lambda: _settings())

        fake_completions = _FakeCompletions(response=_FakeResponse("  hello there  "))

        class _Client(_FakeOpenAI):
            def __init__(self, **kwargs: Any) -> None:
                super().__init__(**kwargs)
                self.chat = _FakeChat(fake_completions)

        monkeypatch.setattr("openai.OpenAI", _Client)

        result = groq_module.generate("Hi", history=[{"role": "user", "content": "Hi"}])

        assert result == "hello there"
        assert len(fake_completions.calls) == 1
        call_kwargs = fake_completions.calls[0]
        assert call_kwargs["tool_choice"] == "none"
        assert call_kwargs["model"] == "test-model"

    def test_generate_builds_messages_with_history_and_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(groq_module, "get_settings", lambda: _settings())

        fake_completions = _FakeCompletions(response=_FakeResponse("ok"))

        class _Client(_FakeOpenAI):
            def __init__(self, **kwargs: Any) -> None:
                super().__init__(**kwargs)
                self.chat = _FakeChat(fake_completions)

        monkeypatch.setattr("openai.OpenAI", _Client)

        history = [{"role": "user", "content": "previous message"}]
        groq_module.generate("new prompt", history=history)

        messages = fake_completions.calls[0]["messages"]
        assert messages[0] == {"role": "user", "content": "previous message"}
        assert messages[-1] == {"role": "user", "content": "new prompt"}

    def test_generate_includes_tool_result_as_system_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(groq_module, "get_settings", lambda: _settings())

        fake_completions = _FakeCompletions(response=_FakeResponse("ok"))

        class _Client(_FakeOpenAI):
            def __init__(self, **kwargs: Any) -> None:
                super().__init__(**kwargs)
                self.chat = _FakeChat(fake_completions)

        monkeypatch.setattr("openai.OpenAI", _Client)

        groq_module.generate("prompt", history=[], tool_result="42")

        messages = fake_completions.calls[0]["messages"]
        assert any(
            m["role"] == "system" and "42" in m["content"]
            for m in messages
        )

    def test_generate_omits_tool_result_message_when_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(groq_module, "get_settings", lambda: _settings())

        fake_completions = _FakeCompletions(response=_FakeResponse("ok"))

        class _Client(_FakeOpenAI):
            def __init__(self, **kwargs: Any) -> None:
                super().__init__(**kwargs)
                self.chat = _FakeChat(fake_completions)

        monkeypatch.setattr("openai.OpenAI", _Client)

        groq_module.generate("prompt", history=[], tool_result=None)

        messages = fake_completions.calls[0]["messages"]
        assert all(m["role"] != "system" for m in messages)

    def test_generate_constructs_client_with_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _settings(api_key="k", base_url="https://base", timeout=99.0)
        monkeypatch.setattr(groq_module, "get_settings", lambda: settings)

        fake_completions = _FakeCompletions(response=_FakeResponse("ok"))
        created: dict[str, Any] = {}

        class _Client(_FakeOpenAI):
            def __init__(self, **kwargs: Any) -> None:
                super().__init__(**kwargs)
                created.update(kwargs)
                self.chat = _FakeChat(fake_completions)

        monkeypatch.setattr("openai.OpenAI", _Client)

        groq_module.generate("prompt", history=[])

        assert created == {"api_key": "k", "base_url": "https://base", "timeout": 99.0}


class TestGenerateErrors:
    def test_generate_wraps_api_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(groq_module, "get_settings", lambda: _settings())

        request = httpx.Request("POST", "https://example.invalid/v1")
        api_error = APIError("upstream failure", request, body=None)
        fake_completions = _FakeCompletions(error=api_error)

        class _Client(_FakeOpenAI):
            def __init__(self, **kwargs: Any) -> None:
                super().__init__(**kwargs)
                self.chat = _FakeChat(fake_completions)

        monkeypatch.setattr("openai.OpenAI", _Client)

        with pytest.raises(LLMError, match="GROQ REQUEST FAILED"):
            groq_module.generate("prompt", history=[])