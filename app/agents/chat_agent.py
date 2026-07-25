from __future__ import annotations

class ChatAgent:

    def run(self, prompt, context):
        context.conversation.add_user(prompt)

        response = context.llm.generate(
            prompt=prompt,
            history=context.conversation.messages(),
        )

        context.conversation.add_assistant(
            response.content
        )
        return response