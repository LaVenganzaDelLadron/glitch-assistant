# app/application.py
"""
Shared application bootstrap for both CLI and Web interfaces.

Creates and wires together the Pipeline with all its dependencies
(LLM, memory, tools, registry). Both main.py (CLI) and web/server.py
import from here to avoid code duplication.
"""
from __future__ import annotations

from app.core.ai.factory import LLMFactory
from app.core.memory.conversation import ConversationMemory
from app.core.memory.project import ProjectMemory
from app.core.pipeline.context import PipelineContext
from app.core.pipeline.pipeline import Pipeline
from app.tools import registry


def create_pipeline() -> Pipeline:
    """Build a fully-wired Pipeline ready to process prompts."""
    memory = ConversationMemory()

    context = PipelineContext(
        llm=LLMFactory.create(),
        conversation=memory,
        project=ProjectMemory(),
    )

    return Pipeline(context, registry=registry)
