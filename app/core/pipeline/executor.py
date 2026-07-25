#app/core/pipeline/executor.py
from __future__ import annotations
from app.agents.chat_agent import ChatAgent


class Executor:

    def __init__(self):

        self.chat = ChatAgent()

    def execute(self, task, prompt, context, prompts=None):

        if task == "chat":
            return self.chat.run(
                prompt,
                context,
            )

        raise NotImplementedError(task)
