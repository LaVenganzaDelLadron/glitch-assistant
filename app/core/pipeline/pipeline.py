"""Main pipeline — orchestrates input parsing, intent detection, tool use,
LLM generation, memory, and output formatting.
"""

from __future__ import annotations
import logging
from app.core.pipeline.input import parser
from app.core.pipeline.memory import memory as memory_module
from app.core.pipeline.reasoning import thinker
from app.core.pipeline.output import formatter
from app.core.ai import groq

logger = logging.getLogger(__name__)


def run(user_input: str) -> str:
    """Process a user input through the full assistant pipeline.

    Steps:
        1. Parse / clean the input.
        2. Load conversation history from memory.
        3. Decide whether a tool should handle the input.
        4. If a tool is selected, execute it and capture the result.
        5. Send the prompt, history, and optional tool result to the LLM.
        6. Save the exchange to memory.
        7. Format and return the final response.

    Args:
        user_input: Raw text from the user.

    Returns:
        The assistant's formatted response string.
    """
    cleaned = parser.parse(user_input)

    history = memory_module.load()

    decision = thinker.decide(cleaned)

    tool_result: str | None = None
    if decision.use_tool and decision.tool:
        tool_result = decision.tool(cleaned)
        logger.info("Tool returned: %.200s…", tool_result)

    response = groq.generate(cleaned, history, tool_result)

    memory_module.save(cleaned, response)
    return formatter.format(response)
