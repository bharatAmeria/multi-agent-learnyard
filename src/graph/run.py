"""Shared helpers for running the graph from app.py and the Streamlit UI."""
import os
import re
import sys
import time
from threading import Event
from typing import Callable, Optional

from exception import MyException
from graph.graph_builder import build_graph
from logger import GLOBAL_LOGGER as logger


def make_initial_state(user_requirement: str, project_dir: str) -> dict:
    return {
        "user_requirement": user_requirement,
        "project_type": "",
        "architecture_plan": "",
        "task_breakdown": [],
        "generated_files": [],
        "generated_tests": [],
        "execution_results": [],
        "bug_reports": [],
        "review_feedback": "",
        "quality_score": 0.0,
        "approval_status": "pending",
        "memory_context": [],
        "final_project_path": project_dir,
        "revision_count": 0,
        "files_to_revise": [],
    }


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:max_len] or "project"


def new_project_dir(user_requirement: str, base: str = "generated_projects") -> str:
    try:
        project_dir = os.path.join(base, f"{int(time.time())}_{slugify(user_requirement)}")
        os.makedirs(project_dir, exist_ok=True)
        return project_dir
    except Exception as e:
        logger.error("new_project_dir_failed", error=str(e))
        raise MyException(e, sys) from e


def run_pipeline(
    user_requirement: str,
    recursion_limit: int = 60,
    cancel_event: Event | None = None,
    on_step: Optional[Callable[[str, dict], None]] = None,
) -> tuple[dict, float]:
    """Builds a fresh project workspace, runs the full graph, and returns
    (final_state, elapsed_seconds).

    If `cancel_event` is provided and gets set while the graph is running,
    the pipeline stops as soon as the currently-executing node finishes
    (graph nodes run one LLM call / tool call at a time, so this is a short
    wait, not an instant kill — true mid-call interruption isn't possible
    without killing the process). The returned state has
    `approval_status="cancelled"` and whatever partial work was completed.

    If `on_step` is provided, it's called as `on_step(node_name, state)`
    after each node finishes — every agent function mutates and returns the
    *entire* GraphState (not a partial diff), so `state` is always the full
    state as of that point. The Streamlit UI uses this to drive a live
    "which agent is running now" diagram. A failure inside `on_step` is
    logged and swallowed so a UI rendering bug can never break a pipeline
    run.
    """
    try:
        project_dir = new_project_dir(user_requirement)
        graph = build_graph()
        initial_state = make_initial_state(user_requirement, project_dir)

        started = time.time()
        final_state = initial_state
        for step in graph.stream(
            initial_state,
            config={"recursion_limit": recursion_limit},
            stream_mode="updates",
        ):
            # `step` is {node_name: full_state} for whichever node just ran.
            node_name, node_state = next(iter(step.items()))
            final_state = node_state

            if on_step is not None:
                try:
                    on_step(node_name, node_state)
                except Exception as e:
                    logger.error("run_pipeline_on_step_failed", node=node_name, error=str(e))

            if cancel_event is not None and cancel_event.is_set():
                elapsed = time.time() - started
                final_state["approval_status"] = "cancelled"
                logger.info(
                    "run_pipeline_cancelled",
                    project_dir=project_dir,
                    last_node=node_name,
                    elapsed_seconds=round(elapsed, 2),
                )
                return final_state, elapsed

        elapsed = time.time() - started
        logger.info("run_pipeline_completed", project_dir=project_dir, elapsed_seconds=round(elapsed, 2))
        return final_state, elapsed
    except MyException:
        raise
    except Exception as e:
        logger.error("run_pipeline_failed", error=str(e))
        raise MyException(e, sys) from e
