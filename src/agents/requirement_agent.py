"""Input: user request. Output: structured requirements (project_type)."""
import sys

from exception import MyException
from graph.state import GraphState
from logger import GLOBAL_LOGGER as logger
from utils.llm import LLM_AVAILABLE, call_llm_json
from utils.tracing import traceable

SYSTEM = (
    "You are a requirement analysis agent in a software engineering pipeline. "
    "Classify the user's request and extract its key features."
)


@traceable(name="requirement_agent")
def requirement_agent(state: GraphState) -> GraphState:
    try:
        if not LLM_AVAILABLE:
            state["project_type"] = state["project_type"] or "generic_python_app"
            logger.info("requirement_agent_offline")
            return state

        user = (
            f"User request: {state['user_requirement']}\n\n"
            'Respond with JSON: {"project_type": str (short snake_case slug), '
            '"summary": str, "key_features": [str, ...]}'
        )
        result = call_llm_json(SYSTEM, user)
        state["project_type"] = result.get("project_type", "generic_python_app")
        logger.info("requirement_agent_completed", project_type=state["project_type"])
        return state
    except Exception as e:
        logger.error("requirement_agent_failed", error=str(e))
        raise MyException(e, sys) from e
