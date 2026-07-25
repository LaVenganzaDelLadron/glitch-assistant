"""Context management package — prevents token overflow by trimming, summarizing,
and compressing conversation context before sending to the LLM.

Provides:
    - :class:`TokenEstimator` — estimates token usage of messages
    - :class:`OutputCompressor` — compresses tool outputs and file listings
    - :class:`HistorySummarizer` — summarizes old conversation history
    - :class:`ContextManager` — orchestrates context preparation end-to-end
"""

from __future__ import annotations

from app.core.pipeline.context.token_estimator import TokenEstimator
from app.core.pipeline.context.output_compressor import OutputCompressor
from app.core.pipeline.context.history_summarizer import HistorySummarizer
from app.core.pipeline.context.context_manager import ContextManager

__all__ = [
    "TokenEstimator",
    "OutputCompressor",
    "HistorySummarizer",
    "ContextManager",
]

