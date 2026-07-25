from __future__ import annotations
import json
from app.tools.registry import ToolRegistry

MAX_TOOL_STEPS = 10


class Executor:

    def __init__(self, registry: ToolRegistry | None = None):
        self.registry = registry or ToolRegistry()

    def execute(self, task, prompt, context, prompts=None, system_prompt=None):

        if task == "chat":
            return self._execute_tool_loop(
                prompt=prompt,
                context=context,
                system_prompt=system_prompt,
            )

        raise NotImplementedError(task)

    def _execute_tool_loop(self, prompt, context, system_prompt=None):
        """Run the tool-calling loop: generate -> execute tools -> repeat -> return final."""
        # Step 1: Add the user prompt to conversation
        context.conversation.add_user(prompt)

        step = 0
        tools = self.registry.schemas() if self.registry.names() else None

        while step < MAX_TOOL_STEPS:
            step += 1

            # Generate with tool schemas
            response = context.llm.generate(
                prompt=prompt if step == 1 else "",
                history=context.conversation.messages(),
                system_prompt=system_prompt,
                tools=tools,
            )

            # Store the assistant response (with tool_calls if any)
            context.conversation.add_assistant(
                content=response.content,
                tool_calls=response.tool_calls,
            )

            # If no tool calls, we're done -- return the final response
            if not response.tool_calls:
                return response

            # Execute each tool call
            for tc in response.tool_calls:
                try:
                    args = self._parse_arguments(tc.arguments)
                    result = self.registry.execute(tc.name, **args)
                    output = result.output if result.success else result.error
                except Exception as e:
                    output = f"Error executing {tc.name}: {e}"

                context.conversation.add_tool(
                    content=str(output),
                    tool_call_id=tc.id,
                )

            # Continue loop: next iteration includes tool results in history

        # Max steps reached -- return last response
        return response

    @staticmethod
    def _parse_arguments(raw: str | dict) -> dict:
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"raw": raw}

