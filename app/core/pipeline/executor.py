from __future__ import annotations
import json
from app.tools.registry import ToolRegistry
from app.core.utils.output_compressor import compress_output
from app.config.settings import get_settings

MAX_TOOL_STEPS = 10


class Executor:

    def __init__(self, registry: ToolRegistry | None = None):
        self.registry = registry or ToolRegistry()
        settings = get_settings()
        self.max_tool_output_chars = int(settings.max_tool_output_chars)

    def execute(self, task, prompt, context, prompts=None, system_prompt=None):

        if task == "chat":
            return self._execute_tool_loop(
                prompt=prompt,
                context=context,
                system_prompt=system_prompt,
            )

        raise NotImplementedError(task)

    def _execute_tool_loop(self, prompt, context, system_prompt=None):
        """Run the tool-calling loop.

        Standard OpenAI/Groq tool-calling workflow:
        1. Add user message to conversation.
        2. Call LLM with full conversation history + tool schemas.
        3. If LLM returns tool_calls, execute each one and append results.
        4. Loop back to step 2 with tool results included in history.
        5. When LLM returns no tool_calls, return the final answer.

        All tool outputs are compressed BEFORE being added to conversation memory
        to prevent context window overflow.
        """
        # Step 1: Store the user's prompt in conversation memory
        context.conversation.add_user(prompt)

        step = 0
        tools = self.registry.schemas() if self.registry.names() else None

        while step < MAX_TOOL_STEPS:
            step += 1

            # Call LLM with full conversation history + tools
            response = context.llm.generate(
                prompt=prompt,  # fallback; groq uses history when available
                history=context.conversation.messages(),
                system_prompt=system_prompt,
                tools=tools,
            )

            # Append assistant's response (text + tool_calls) to history
            context.conversation.add_assistant(
                content=response.content,
                tool_calls=response.tool_calls,
            )

            # No tool calls -> final answer is ready
            if not response.tool_calls:
                return response

            # Execute each tool call and append compressed results as tool messages
            for tc in response.tool_calls:
                try:
                    # ToolCall.arguments is already parsed to dict by __post_init__
                    args = tc.arguments if isinstance(tc.arguments, dict) else json.loads(tc.arguments)
                    result = self.registry.execute(tc.name, **args)

                    # Use .content (primary) or .output (backward-compatible alias)
                    raw_output = result.content

                    # SAFETY NET: Even if the tool itself compressed, ensure we never
                    # exceed the configured limit before storing in memory
                    compressed = compress_output(raw_output, max_chars=self.max_tool_output_chars)
                    safe_output = compressed.content

                except Exception as e:
                    safe_output = f"Error executing {tc.name}: {e}"

                context.conversation.add_tool(
                    content=str(safe_output),
                    tool_call_id=tc.id,
                )

            # Loop: next iteration includes tool results in conversation history

        # Max steps exhausted - return what we have
        return response

    @staticmethod
    def _parse_arguments(raw: str | dict) -> dict:
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"raw": raw}
