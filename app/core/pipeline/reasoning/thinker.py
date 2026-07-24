#app/core/pipeline/reasoning/thinker.py

from app.core.pipeline.tools import calculator

class Decision:
    def __init__(self, use_tool=False, tool=None):
        self.use_tool = use_tool
        self.tool = tool

def decide(text):
    try:
        if text.startwith("calculate", ""):
            return Decision(use_tool=True, tool=calculator)
        return Decision(use_tool=False)
    except Exception as e:
        print(f"ERROR: {e}")