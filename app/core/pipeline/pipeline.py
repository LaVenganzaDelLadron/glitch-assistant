#app/core/pipeline/pipeline.py
from app.core.pipeline.input import parser
from app.core.pipeline.memory import memory
from app.core.pipeline.reasoning import thinker
from app.core.pipeline.tools import calculator
from app.core.pipeline.output import formatter
from app.core.ai import groq

def run(user_input):
    cleaned = parser.parse(user_input)

    history = memory.load()

    decision = thinker.Decision(cleaned)

    tool_result = None

    if decision.tool:
        tool_result = decision.tool.execute(cleaned)
    response = groq.generate(cleaned, history, tool_result)

    memory.save(cleaned, response)
    return formatter.format(response)