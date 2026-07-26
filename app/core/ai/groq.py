#app/core/ai/groq.py
from __future__ import annotations
from app.core.ai.base import LLMProvider
from dotenv import load_dotenv
from app.core.models.response import AIResponse
from app.core.models.usage import Usage
from app.core.models.tool_call import ToolCall
from app.core.memory.conversation import ConversationMemory
from app.core.pipeline.context_builder import build_messages

load_dotenv()


class GroqProvider(LLMProvider):
    def __init__(
        self,
        api_key,
        base_url,
        model,
        timeout,
    ):
        from openai import OpenAI

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

        self.model = model

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

        response = self.client.chat.completions.create(**kwargs)

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
