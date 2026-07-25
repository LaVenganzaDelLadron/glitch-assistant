#app/core/pipeline/router.py
from __future__ import annotations

class Router:

    def route(self, prompt: str) -> str:
        lower = prompt.lower()

        if "review" in lower:
            return "review"
        if "debug" in lower:
            return "debug"
        if "scan" in lower:
            return "scan"
        if "document" in lower:
            return "documentation"
        return "chat"