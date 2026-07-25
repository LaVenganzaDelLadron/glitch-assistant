#app/core/ai/groq.py
from app.core.ai.base import LLMProvider
from dotenv import load_dotenv
from app.core.models.response import AIResponse
from app.core.models.usage import Usage

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

    def generate(self, prompt, history=None, tool_result=None, system_prompt=None):
        messages = []

        # System prompt (route-specific, loaded dynamically) comes first
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })

        # Conversation history (user/assistant/tool messages, no system messages stored)
        if history:
            messages.extend(
                msg.to_dict() for msg in history
                if msg.role != "system"
            )

        # Tool result as a system message (temporary context)
        if tool_result:
            messages.append({
                "role": "system",
                "content": tool_result,
            })

        # Current user prompt
        messages.append({
            "role": "user",
            "content": prompt,
        })

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        return AIResponse(
            content=response.choices[0].message.content,
            model=self.model,
            usage=Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
            finish_reason=response.choices[0].finish_reason,
        )
