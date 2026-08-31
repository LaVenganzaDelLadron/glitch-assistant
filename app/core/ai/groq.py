#app/core/ai/groq.py
from __future__ import annotations
import logging
from collections.abc import Callable, Iterable

from app.core.ai.base import LLMProvider
from app.config.settings import ApiKeyConfig
from app.core.ai.key_manager import ApiKeyManager
from app.core.models.response import AIResponse
from app.core.models.usage import Usage
from app.core.models.tool_call import ToolCall
from app.core.memory.conversation import ConversationMemory
from app.core.pipeline.context_builder import build_messages

logger = logging.getLogger(__name__)


class AllApiKeyAttemptsFailedError(RuntimeError):
    """Raised after every permitted retryable key attempt has failed."""


class GroqProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_keys: Iterable[ApiKeyConfig] | None = None,
        base_url: str,
        model: str,
        timeout: float,
        max_api_attempts: int = 5,
        rate_limit_cooldown_seconds: float = 60.0,
        temporary_failure_cooldown_seconds: float = 5.0,
        api_key: str | None = None,
        client_factory: Callable[[str], object] | None = None,
    ):
        # ``api_key`` preserves compatibility for callers still constructing this
        # provider directly. Application wiring always supplies ``api_keys``.
        if api_keys is None:
            if not api_key:
                raise ValueError("GroqProvider needs at least one API key.")
            api_keys = (ApiKeyConfig(slot=1, key=api_key),)
        self.key_manager = ApiKeyManager(
            api_keys,
            rate_limit_cooldown_seconds=rate_limit_cooldown_seconds,
            temporary_failure_cooldown_seconds=temporary_failure_cooldown_seconds,
        )
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.max_api_attempts = max_api_attempts
        self._client_factory = client_factory

    def _create_client(self, api_key: str):
        """Create a request-scoped SDK client so concurrent calls cannot share auth."""
        if self._client_factory is not None:
            return self._client_factory(api_key)
        from openai import OpenAI

        return OpenAI(api_key=api_key, base_url=self.base_url, timeout=self.timeout)

    def generate(
        self,
        prompt,
        history=None,
        tool_result=None,
        system_prompt=None,
        tools=None,
        max_tokens: int | None = None,
        max_context_tokens: int = 6000,
        reserve_tokens: int = 1000,
        conversation_memory: ConversationMemory | None = None,
    ):
        """Generate a response from the LLM with token budget enforcement.

        Uses ContextBuilder to construct the message list, enforces
        the token budget, and logs usage statistics after each response.

        Args:
            prompt: Current user message (used as fallback when no history).
            history: Legacy param — not used directly; conversation_memory is preferred.
            tool_result: Legacy param — not used directly.
            system_prompt: System-level instructions.
            tools: Tool schemas for function calling.
            max_tokens: Maximum tokens for the LLM response.
            max_context_tokens: Maximum total context tokens allowed.
            reserve_tokens: Tokens reserved for the LLM response.
            conversation_memory: ConversationMemory instance for context building.
        """
        # Build messages using ContextBuilder
        messages: list[dict] = []

        if conversation_memory:
            # Use ContextBuilder for proper message construction
            messages = build_messages(
                system_prompt=system_prompt,
                conversation=conversation_memory,
                current_user_message=prompt,
                max_context_tokens=max_context_tokens,
                reserve_tokens=reserve_tokens,
            )
        else:
            # Fallback: simple message construction
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt,
                })

            if history:
                for msg in history:
                    d = msg.to_dict()
                    if d["role"] == "system":
                        continue
                    messages.append(d)
            else:
                messages.append({
                    "role": "user",
                    "content": prompt,
                })

        # Tool result injected as a system hint (for legacy compatibility)
        if tool_result:
            messages.append({
                "role": "system",
                "content": tool_result,
            })

        kwargs: dict = {
            "model": self.model,
            "messages": messages,
        }

        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self._create_completion_with_rotation(kwargs)

        choice = response.choices[0]
        message = choice.message

        # Parse tool calls from the response
        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    )
                )

        # Log token usage for debugging
        if response.usage:
            print(
                f"[Token Usage] Prompt: {response.usage.prompt_tokens} | "
                f"Completion: {response.usage.completion_tokens} | "
                f"Total: {response.usage.total_tokens}"
            )

        return AIResponse(
            content=message.content or "",
            model=self.model,
            usage=Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls,
        )

    def _create_completion_with_rotation(self, kwargs: dict):
        """Keep retry policy separate from key selection and request construction."""
        attempted_slots: set[int] = set()
        last_error: Exception | None = None

        for _ in range(self.max_api_attempts):
            lease = self.key_manager.acquire(excluded_slots=attempted_slots)
            attempted_slots.add(lease.slot)
            try:
                response = self._create_client(lease.key).chat.completions.create(**kwargs)
            except Exception as error:
                action = self._retry_action(error)
                if action == "rate_limit":
                    self.key_manager.record_rate_limit(lease)
                elif action == "temporary":
                    self.key_manager.record_temporary_failure(lease)
                else:
                    # Authentication, malformed requests, and other permanent 4xx
                    # failures must be returned immediately and never rotated.
                    raise
                last_error = error
                logger.warning("Groq request failed using key slot %s; trying another eligible key", lease.slot)
                continue
            self.key_manager.record_success(lease)
            return response

        message = f"Groq request failed after {len(attempted_slots)} retryable key attempt(s)."
        raise AllApiKeyAttemptsFailedError(message) from last_error

    @staticmethod
    def _retry_action(error: Exception) -> str | None:
        """Classify only transient provider failures as eligible for rotation."""
        from openai import APIConnectionError, APIStatusError, APITimeoutError

        if isinstance(error, (APITimeoutError, APIConnectionError)):
            return "temporary"
        if isinstance(error, APIStatusError):
            if error.status_code == 429:
                return "rate_limit"
            if error.status_code in {408, 500, 502, 503, 504}:
                return "temporary"
        return None
