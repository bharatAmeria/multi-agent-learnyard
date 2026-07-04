"""Input: task. Output: source files, written via the filesystem tool."""
import os
import sys

from exception import MyException
from graph.state import GraphState
from logger import GLOBAL_LOGGER as logger
from tools.filesystem_tool import write_file
from utils.llm import LLM_AVAILABLE, call_llm, strip_code_fences
from utils.tracing import traceable

SYSTEM = (
    "You are an expert software engineer. Write complete, runnable, "
    "production-quality code for the requested file. Output ONLY the file "
    "content — no explanations, no markdown code fences."
)


@traceable(name="coding_agent")
def coding_agent(state: GraphState) -> GraphState:
    try:
        project_dir = state.get("final_project_path") or "."
        is_revision = bool(state.get("generated_files"))
        if is_revision:
            # Not the first pass — this run was triggered by review feedback.
            state["revision_count"] = state.get("revision_count", 0) + 1

        if not LLM_AVAILABLE:
            if not state.get("generated_files"):
                path = os.path.join(project_dir, "app.py")
                write_file(path, "# generated offline (no ANTHROPIC_API_KEY configured)\nprint('hello world')\n")
                state["generated_files"] = [{"path": path, "description": "offline stub"}]
            logger.info("coding_agent_offline", project_dir=project_dir)
            return state

        # On a revision pass, review_agent has already named which files
        # actually need to change — re-running every file from scratch each
        # time (often 3x, capped by max_review_revisions) burns a full
        # project's worth of LLM calls per loop for files that didn't need
        # touching. Reuse the prior entry for anything not flagged.
        files_to_revise = state.get("files_to_revise") or []
        existing_by_path = {f["path"]: f for f in state.get("generated_files", [])}

        generated = []
        for task in state.get("task_breakdown", []):
            rel_path = task["file_path"]
            full_path = os.path.join(project_dir, rel_path)

            if is_revision and files_to_revise and full_path not in files_to_revise and full_path in existing_by_path:
                generated.append(existing_by_path[full_path])
                continue

            user = (
                f"Architecture plan:\n{state.get('architecture_plan', '')}\n\n"
                f"Review feedback from a previous pass, address it if relevant:\n"
                f"{state.get('review_feedback') or '(none — first pass)'}\n\n"
                f"File to write: {rel_path}\n"
                f"Purpose: {task['description']}\n"
            )
            content = strip_code_fences(call_llm(SYSTEM, user, max_tokens=4096))
            write_file(full_path, content)
            generated.append({"path": full_path, "description": task["description"]})

        state["generated_files"] = generated
        logger.info("coding_agent_completed", files_written=len(generated), revision=is_revision)
        return state
    except Exception as e:
        logger.error("coding_agent_failed", error=str(e))
        raise MyException(e, sys) from e
