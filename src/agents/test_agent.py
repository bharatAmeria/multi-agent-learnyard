"""Input: source files. Output: unit tests."""
import os
import sys

from exception import MyException
from graph.state import GraphState
from logger import GLOBAL_LOGGER as logger
from tools.filesystem_tool import read_file, write_file
from utils.llm import LLM_AVAILABLE, call_llm, strip_code_fences
from utils.tracing import traceable

SYSTEM = (
    "You are a test engineer. Write pytest tests for the given module. "
    "Assume the test file lives in a tests/ directory at the project root and "
    "the module is importable from the project root. Output ONLY the test "
    "file content — no explanations, no markdown code fences."
)


@traceable(name="test_agent")
def test_agent(state: GraphState) -> GraphState:
    try:
        project_dir = state.get("final_project_path") or "."

        if not LLM_AVAILABLE:
            state["generated_tests"] = state["generated_tests"] or []
            logger.info("test_agent_offline")
            return state

        is_revision = state.get("revision_count", 0) > 0
        files_to_revise = state.get("files_to_revise") or []
        existing_tests_by_path = {t["path"]: t for t in (state.get("generated_tests") or [])}

        tests = []
        for f in state.get("generated_files", []):
            path = f["path"]
            rel = os.path.relpath(path, project_dir)
            if not rel.endswith(".py"):
                continue
            base = os.path.basename(rel)
            # Skip files that don't need (or shouldn't get) a generated test:
            # __init__.py is typically empty/trivial, and if a test file
            # itself ended up in generated_files (e.g. the planner included
            # one in the coding task breakdown), don't write a test for a
            # test — that's how runs end up with nonsense like
            # tests/test_test_sorting.py and burn an extra LLM call for
            # nothing.
            if base == "__init__.py" or base.startswith("test_") or f"{os.sep}tests{os.sep}" in os.sep + rel:
                continue
            module_name = os.path.splitext(base)[0]
            test_path = os.path.join(project_dir, "tests", f"test_{module_name}.py")

            # On a revision pass, a source file review didn't flag has
            # unchanged content — its existing test is still valid, so keep
            # it instead of paying for a fresh LLM call that would very
            # likely produce the same test again.
            if is_revision and files_to_revise and path not in files_to_revise and test_path in existing_tests_by_path:
                tests.append(existing_tests_by_path[test_path])
                continue

            source = read_file(path)
            user = f"Module path (relative to project root): {rel}\n\nModule source:\n{source}"
            test_code = strip_code_fences(call_llm(SYSTEM, user, max_tokens=2048))
            write_file(test_path, test_code)
            tests.append({"path": test_path})

        state["generated_tests"] = tests
        logger.info("test_agent_completed", tests_written=len(tests))
        return state
    except Exception as e:
        logger.error("test_agent_failed", error=str(e))
        raise MyException(e, sys) from e


# Tell pytest not to collect this as a test item — it's a pipeline agent
# function, not a test, despite the test_*.py / test_* naming.
test_agent.__test__ = False
