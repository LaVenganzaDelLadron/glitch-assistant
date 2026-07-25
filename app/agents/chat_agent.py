from __future__ import annotations

class ChatAgent:

    def run(self, prompt, context, system_prompt=None):
        context.conversation.add_user(prompt)

        response = context.llm.generate(
            prompt=prompt,
            history=context.conversation.messages(),
            system_prompt=system_prompt,
        )

        context.conversation.add_assistant(
            response.content
        )
        return response
