"""Shared state schema passed between all nodes in the LangGraph."""
from typing import TypedDict


class GraphState(TypedDict):
    user_requirement: str
    project_type: str
    architecture_plan: str
    task_breakdown: list
    generated_files: list
    generated_tests: list
    execution_results: list
    bug_reports: list
    review_feedback: str
    quality_score: float
    approval_status: str
    memory_context: list
    final_project_path: str
    revision_count: int  # how many times coding_agent has revised in response to review feedback
    files_to_revise: list  # full paths review_agent flagged as needing a revision pass
