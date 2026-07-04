"""Input: final project. Output: memory update, persisted to the long-term SQLite store."""
import sys

from exception import MyException
from graph.state import GraphState
from logger import GLOBAL_LOGGER as logger
from tools.sqlite_tool import save_project_memory
from utils.tracing import traceable


@traceable(name="memory_updater")
def memory_updater(state: GraphState) -> GraphState:
    try:
        row_id = save_project_memory(state)
        print(f"Saved project memory (id={row_id}) for project at: {state.get('final_project_path')}")
        logger.info("memory_updater_completed", row_id=row_id)
        return state
    except Exception as e:
        logger.error("memory_updater_failed", error=str(e))
        raise MyException(e, sys) from e
