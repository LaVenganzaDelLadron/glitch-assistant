#app/core/ai/groq.py
from __future__ import annotations
from app.core.ai.base import LLMProvider
from dotenv import load_dotenv
from app.core.models.response import AIResponse
from app.core.models.usage import Usage
from app.core.models.tool_call import ToolCall

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

    def generate(self, prompt, history=None, tool_result=None, system_prompt=None, tools=None):
        """Generate a response from the LLM.

        IMPORTANT: The caller (Executor) is responsible for storing messages
        into ConversationMemory. This method uses `history` as the SOLE source
        of messages, avoiding duplicate user messages. The `prompt` param is
        only used as a fallback when no history is provided.
        """
        messages: list[dict] = []

        # System prompt (loaded dynamically per route) comes first
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })

        # History is the authoritative message list — includes user, assistant, tool
        if history:
            for msg in history:
                d = msg.to_dict()
                # Skip any stale system messages from memory (we prepend fresh one above)
                if d["role"] == "system":
                    continue
                messages.append(d)
        else:
            # No history: use prompt as a standalone user message
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
