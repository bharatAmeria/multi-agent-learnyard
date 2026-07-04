"""Input: requirements. Output: architecture document."""
import sys

from exception import MyException
from graph.state import GraphState
from logger import GLOBAL_LOGGER as logger
from utils.llm import LLM_AVAILABLE, call_llm
from utils.tracing import traceable

SYSTEM = (
    "You are a pragmatic software architect. Produce a concise architecture plan "
    "for a small, runnable MVP: components, tech stack, and an explicit list of "
    "files to create (path: one-line purpose each). Keep it to at most 8 files."
)


@traceable(name="architecture_agent")
def architecture_agent(state: GraphState) -> GraphState:
    try:
        if not LLM_AVAILABLE:
            state["architecture_plan"] = state["architecture_plan"] or (
                "Single-module Python app.\nFiles:\n- app.py: entry point"
            )
            logger.info("architecture_agent_offline")
            return state

        user = f"Project type: {state['project_type']}\nUser request: {state['user_requirement']}"
        state["architecture_plan"] = call_llm(SYSTEM, user, max_tokens=2048)
        logger.info("architecture_agent_completed", project_type=state.get("project_type"))
        return state
    except Exception as e:
        logger.error("architecture_agent_failed", error=str(e))
        raise MyException(e, sys) from e
