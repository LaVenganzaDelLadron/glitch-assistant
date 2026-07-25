"""Repository analysis module — AI prompts, structured reports, and orchestration."""

from analysis.prompts import SYSTEM_PROMPT, ANALYSIS_INSTRUCTIONS, build_file_index_prompt
from analysis.report import AnalysisReport, Issue, Recommendation, Strength
from analysis.analyzer import RepoAnalyzer, AnalysisError
from analysis.prompt_builder import PromptBuilder
from analysis.report_builder import ReportBuilder

__all__ = [
    "SYSTEM_PROMPT",
    "ANALYSIS_INSTRUCTIONS",
    "build_file_index_prompt",
    "AnalysisReport",
    "Issue",
    "Recommendation",
    "Strength",
    "RepoAnalyzer",
    "AnalysisError",
    "PromptBuilder",
    "ReportBuilder",
]

