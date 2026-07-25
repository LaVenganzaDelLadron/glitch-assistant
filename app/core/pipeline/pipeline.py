"""Main pipeline — orchestrates input parsing, intent detection, tool use,
LLM generation, memory, and output formatting.
"""

from __future__ import annotations
import logging
from typing import Any

from app.core.pipeline.input import parser
from app.core.pipeline.memory import memory as memory_module
from app.core.pipeline.reasoning import thinker
from app.core.pipeline.output import formatter
from app.core.ai import groq

logger = logging.getLogger(__name__)


def run(user_input: str) -> str:
    """
    Process user input through parsing, memory, tool selection, response generation, and formatting.
    
    Args:
        user_input: Raw text provided by the user.
    
    Returns:
        The formatted assistant response, or an error message if the pipeline fails.
    """
    try:
        cleaned = parser.parse(user_input)

        history = memory_module.load()

        decision = thinker.decide(cleaned)

        tool_result: str | None = None
        if decision.use_tool and decision.tool:
            logger.info("Executing tool for: %.60s", cleaned)
            try:
                tool_result = decision.tool(cleaned)
                logger.info("Tool returned: %.200s…", tool_result)
            except Exception as exc:
                logger.exception("Tool execution failed")
                tool_result = f"Error: Tool execution failed — {exc}"

        response = groq.generate(cleaned, history, tool_result)

        memory_module.save(cleaned, response)
        return formatter.format(response)

    except Exception as exc:
        logger.exception("Pipeline error")
        return f"I encountered an error: {exc}"

