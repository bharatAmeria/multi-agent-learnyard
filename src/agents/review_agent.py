"""Input: project. Output: review feedback. Evaluates maintainability, readability, scalability."""
import sys

from config import settings
from exception import MyException
from graph.state import GraphState
from logger import GLOBAL_LOGGER as logger
from utils.llm import LLM_AVAILABLE, call_llm_json
from utils.tracing import traceable

SYSTEM = (
    "You are a senior code reviewer. Score the project from 0-10 on "
    "maintainability, readability, and scalability, give brief actionable "
    "feedback, and list which of the given file paths most need a revision "
    "to address that feedback. Only list paths that actually need changes — "
    "an empty list is fine if the project is solid as-is."
)


@traceable(name="review_agent")
def review_agent(state: GraphState) -> GraphState:
    try:
        if not LLM_AVAILABLE:
            state["review_feedback"] = "Offline mode: review skipped, auto-passing."
            state["quality_score"] = settings.review_pass_threshold
            state["files_to_revise"] = []
            logger.info("review_agent_offline")
            return state

        file_paths = [f["path"] for f in state.get("generated_files", [])]
        user = (
            f"Architecture plan:\n{state.get('architecture_plan', '')}\n\n"
            f"Generated files: {file_paths}\n\n"
            f"Latest execution result: {state.get('execution_results')}\n\n"
            'Respond with JSON: {"feedback": str, "quality_score": number between 0 and 10, '
            '"files_to_revise": [str, ...]} — files_to_revise entries must be exact paths '
            "from the Generated files list above."
        )
        result = call_llm_json(SYSTEM, user)
        state["review_feedback"] = result.get("feedback", "")
        state["quality_score"] = float(result.get("quality_score", 0))
        # Defend against the LLM inventing paths that weren't in the project.
        flagged = result.get("files_to_revise") or []
        state["files_to_revise"] = [p for p in flagged if p in file_paths]
        logger.info(
            "review_agent_completed",
            quality_score=state["quality_score"],
            files_to_revise=state["files_to_revise"],
        )
        return state
    except Exception as e:
        logger.error("review_agent_failed", error=str(e))
        raise MyException(e, sys) from e
