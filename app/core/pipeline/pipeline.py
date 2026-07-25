#app/core/pipeline/pipeline.py
from __future__ import annotations
from app.core.pipeline.context import PipelineContext
from app.core.pipeline.router import Router
from app.core.pipeline.executor import Executor

class Pipeline:

    def __init__(self, context: PipelineContext):
        self.context = context
        self.router = Router()
        self.executor = Executor()

    def run(self, prompt: str):

        task = self.router.route(prompt)

        return self.executor.execute(
            task=task,
            prompt=prompt,
            context=self.context,
        )