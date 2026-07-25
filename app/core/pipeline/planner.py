#app/core/pipeline/planner.py
from __future__ import annotations

class Planner:

    def plan(self, task: str, prompt: str):
        return {
            "task": task,
            "prompt": prompt,
        }