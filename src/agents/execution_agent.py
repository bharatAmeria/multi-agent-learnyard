"""Input: project. Output: execution logs, produced by actually running pytest."""
import sys

from exception import MyException
from graph.state import GraphState
from logger import GLOBAL_LOGGER as logger
from tools.terminal_tool import run_command
from utils.tracing import traceable

# pytest exit code 5 = "no tests collected" — treat as a pass so an empty
# project (e.g. offline mode) doesn't get stuck looping into debug_agent.
_PASS_CODES = (0, 5)


@traceable(name="execution_agent")
def execution_agent(state: GraphState) -> GraphState:
    try:
        project_dir = state.get("final_project_path") or "."
        result = run_command("python -m pytest -q", cwd=project_dir, timeout=120)
        log = (result["stdout"] + "\n" + result["stderr"]).strip()[-4000:]
        status = "pass" if result["returncode"] in _PASS_CODES else "fail"
        state["execution_results"] = [{"status": status, "log": log}]
        logger.info("execution_agent_completed", status=status)
        return state
    except Exception as e:
        logger.error("execution_agent_failed", error=str(e))
        raise MyException(e, sys) from e
