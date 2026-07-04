"""Input: architecture. Output: coding tasks."""
import sys

from exception import MyException
from graph.state import GraphState
from logger import GLOBAL_LOGGER as logger
from utils.llm import LLM_AVAILABLE, call_llm_json
from utils.tracing import traceable

SYSTEM = (
    "You are a software planning agent. Break an architecture plan into concrete, "
    "ordered coding tasks, one per file. Keep the list focused (at most 8 files) "
    "so the project stays buildable in one pass."
)


@traceable(name="planner_agent")
def planner_agent(state: GraphState) -> GraphState:
    try:
        if not LLM_AVAILABLE:
            state["task_breakdown"] = state["task_breakdown"] or [
                {"file_path": "app.py", "description": "Entry point / main script"}
            ]
            logger.info("planner_agent_offline")
            return state

        user = (
            f"Architecture plan:\n{state['architecture_plan']}\n\n"
            'Respond with a JSON list: [{"file_path": str, "description": str}, ...]'
        )
        state["task_breakdown"] = call_llm_json(SYSTEM, user)
        logger.info("planner_agent_completed", task_count=len(state["task_breakdown"]))
        return state
    except Exception as e:
        logger.error("planner_agent_failed", error=str(e))
        raise MyException(e, sys) from e
