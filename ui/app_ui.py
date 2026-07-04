"""Streamlit UI — 8 screens:
1. Requirement Input
2. Agent Graph (live, in-memory only — nothing is saved to disk)
3. LangGraph Execution View
4. Generated Files
5. Test Results
6. Code Review
7. Human Approval
8. Final Project Download

The pipeline runs in a background thread (see _pipeline_worker) so the UI
stays responsive and the Stop button works. AUTO_APPROVE governs the human
approval step — see agents/approval_agent.py for a true CLI y/n prompt.
"""
import io
import os
import sys
import time
import zipfile
from threading import Event, Thread

# Make both the project root (for config.py) and src/ (for the sibling-style
# imports used throughout the codebase, e.g. `from exception import ...`)
# importable regardless of cwd — removes the need to set PYTHONPATH by hand
# when running `streamlit run ui/app_ui.py`.
_UI_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_UI_DIR)
_SRC_DIR = os.path.join(_ROOT_DIR, "src")
for _p in (_ROOT_DIR, _SRC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st  # noqa: E402

from dotenv import set_key  # noqa: E402

from evaluation.metrics import compute_metrics  # noqa: E402
from exception import MyException  # noqa: E402
from graph.run import run_pipeline  # noqa: E402
from logger import GLOBAL_LOGGER as logger  # noqa: E402
from tools.filesystem_tool import read_file  # noqa: E402
from utils.llm import LLM_AVAILABLE, configure_api_key  # noqa: E402

st.set_page_config(page_title="AI Software Engineering Team", layout="wide")
st.title("AI Software Engineering Team")

# --- Agent graph (live view) ------------------------------------------------
# Mirrors the node/edge structure built in graph/graph_builder.py. Rendered
# client-side via st.graphviz_chart (viz.js in the browser) — nothing is
# written to disk, this is purely an in-memory DOT string regenerated on
# every rerun.
_GRAPH_NODES = [
    "requirement_agent",
    "architecture_agent",
    "task_planner",
    "coding_agent",
    "test_agent",
    "execution_agent",
    "debug_agent",
    "review_agent",
    "human_approval",
    "memory_updater",
]
_GRAPH_EDGES = [
    ("requirement_agent", "architecture_agent"),
    ("architecture_agent", "task_planner"),
    ("task_planner", "coding_agent"),
    ("coding_agent", "test_agent"),
    ("test_agent", "execution_agent"),
    ("execution_agent", "review_agent"),
    ("execution_agent", "debug_agent"),
    ("debug_agent", "execution_agent"),
    ("review_agent", "human_approval"),
    ("review_agent", "coding_agent"),
    ("human_approval", "memory_updater"),
    ("human_approval", "coding_agent"),
    ("memory_updater", "END"),
]
_COLOR_DONE = "#86efac"
_COLOR_CURRENT = "#f59e0b"
_COLOR_PENDING = "#e5e7eb"


def _build_graph_dot(current: str | None = None, visited: list | None = None) -> str:
    visited = visited or []
    lines = [
        "digraph G {",
        "rankdir=LR;",
        'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];',
        'edge [color="#9ca3af"];',
    ]
    for node in _GRAPH_NODES:
        color = _COLOR_CURRENT if node == current else (_COLOR_DONE if node in visited else _COLOR_PENDING)
        penwidth = "2.5" if node == current else "1"
        lines.append(f'"{node}" [fillcolor="{color}", penwidth={penwidth}];')
    end_color = _COLOR_DONE if "memory_updater" in visited and current is None else _COLOR_PENDING
    lines.append(f'"END" [shape=doublecircle, style=filled, fillcolor="{end_color}"];')
    for src, dst in _GRAPH_EDGES:
        lines.append(f'"{src}" -> "{dst}";')
    lines.append("}")
    return "\n".join(lines)

if "final_state" not in st.session_state:
    st.session_state.final_state = None
    st.session_state.elapsed = None

# Background-run bookkeeping. The pipeline runs in a worker thread instead of
# blocking the Streamlit script directly — that's what lets the "Stop
# pipeline" button stay clickable (and the rest of the UI responsive) while
# a run is in progress. `pipeline_result` is a plain dict (not session_state
# itself) that the worker thread mutates; the main thread polls it.
if "pipeline_running" not in st.session_state:
    st.session_state.pipeline_running = False
    st.session_state.cancel_event = None
    st.session_state.pipeline_thread = None
    st.session_state.pipeline_result = None
    st.session_state.visited_nodes = []
    st.session_state.current_node = None
    st.session_state.last_run_message = None


def _pipeline_worker(requirement: str, cancel_event: Event, result: dict) -> None:
    result["current_node"] = None
    result["visited"] = []

    if not LLM_AVAILABLE:
        result["error"] = "No OpenAI API key configured. Set OPENAI_API_KEY before running the pipeline."
        result["done"] = True
        return

    def on_step(node_name: str, _node_state: dict) -> None:
        result["current_node"] = node_name
        result["visited"].append(node_name)

    try:
        final_state, elapsed = run_pipeline(requirement, cancel_event=cancel_event, on_step=on_step)
        result["final_state"] = final_state
        result["elapsed"] = elapsed
    except Exception as e:
        wrapped = e if isinstance(e, MyException) else MyException(e, sys)
        result["error"] = str(wrapped)
    finally:
        result["done"] = True

screen = st.sidebar.radio(
    "Screen",
    [
        "1. Requirement Input",
        "2. Agent Graph",
        "3. Execution View",
        "4. Generated Files",
        "5. Test Results",
        "6. Code Review",
        "7. Human Approval",
        "8. Download",
    ],
)

st.sidebar.divider()
st.sidebar.subheader("OpenAI API Key")
if LLM_AVAILABLE:
    st.sidebar.success("Key configured — agents will call the real LLM.")
else:
    st.sidebar.warning("No key set — agents run in offline/stub mode.")

with st.sidebar.form("api_key_form", clear_on_submit=True):
    api_key_input = st.text_input(
        "OPENAI_API_KEY",
        type="password",
        placeholder="sk-...",
        label_visibility="collapsed",
        # Stops the browser from caching/suggesting this value via its
        # normal password-save and autofill prompts — those are what expose
        # the full key in plaintext later (browser password manager,
        # autofill dropdown), not anything the app itself displays.
        autocomplete="new-password",
    )
    persist = st.checkbox(
        "Remember for future runs (saves to local .env)",
        value=False,
        help=(
            "Without this, the key is only kept in memory for this running "
            "app process. With this checked, the key is written in plain "
            "text to the .env file in the project folder — anyone with "
            "filesystem access to that folder can read it there."
        ),
    )
    submitted = st.form_submit_button("Save key")

if submitted:
    if not api_key_input.strip():
        st.sidebar.error("Enter a key first.")
    elif configure_api_key(api_key_input.strip()):
        if persist:
            try:
                env_path = os.path.join(_ROOT_DIR, ".env")
                set_key(env_path, "OPENAI_API_KEY", api_key_input.strip())
                st.sidebar.success("Key saved to .env and activated.")
            except Exception as e:
                wrapped = MyException(e, sys)
                logger.error("api_key_persist_failed", error=str(wrapped))
                st.sidebar.warning("Key activated for this session, but saving to .env failed.")
        else:
            st.sidebar.success("Key activated for this session.")
        logger.info("ui_api_key_configured", persisted=persist)
        st.rerun()
    else:
        st.sidebar.error("Could not activate that key — check it's correct.")

if st.sidebar.button("Clear key"):
    configure_api_key("")
    logger.info("ui_api_key_cleared")
    st.sidebar.info("Key cleared — back to offline/stub mode.")
    st.rerun()

state = st.session_state.final_state

# Poll the background pipeline regardless of which screen is selected, so
# the Agent Graph reflects live progress even if the user has navigated away
# from the Requirement Input screen. This only updates session_state and
# triggers a rerun — no diagram or other artifact is ever written to disk.
if st.session_state.pipeline_running:
    result = st.session_state.pipeline_result
    st.session_state.current_node = result.get("current_node")
    st.session_state.visited_nodes = result.get("visited", [])

    # Visible in the sidebar on every screen (not just Requirement Input) so
    # you can stop a run no matter where you've navigated to while it's
    # going.
    st.sidebar.divider()
    st.sidebar.info(f"Running — **{st.session_state.current_node or 'starting...'}**")
    if st.sidebar.button("Stop pipeline", type="secondary", key="sidebar_stop"):
        st.session_state.cancel_event.set()
        st.sidebar.warning("Stop requested — finishing the current step, then halting.")

    if result.get("done"):
        st.session_state.pipeline_running = False
        st.session_state.pipeline_thread = None
        st.session_state.cancel_event = None
        st.session_state.current_node = None
        if "error" in result:
            logger.error("ui_pipeline_failed", error=result["error"])
            st.session_state.last_run_message = ("error", f"Pipeline run failed: {result['error']}")
        else:
            st.session_state.final_state = result["final_state"]
            st.session_state.elapsed = result["elapsed"]
            logger.info("ui_pipeline_completed", elapsed_seconds=round(result["elapsed"], 2))
            if result["final_state"].get("approval_status") == "cancelled":
                st.session_state.last_run_message = ("warning", "Pipeline stopped. Partial results (if any) are in the other tabs.")
            else:
                st.session_state.last_run_message = ("success", "Pipeline finished — see the other tabs for results.")
        state = st.session_state.final_state
        st.rerun()
    else:
        # Poll again shortly so every screen reflects progress / the Stop
        # button's effect without requiring the user to interact.
        time.sleep(1)
        st.rerun()

if screen == "1. Requirement Input":
    st.subheader("Describe what you want built")

    if st.session_state.pipeline_running:
        st.text_area(
            "Requirement",
            value=st.session_state.get("submitted_requirement", ""),
            height=120,
            disabled=True,
        )
        st.info("Pipeline is running — use the **Stop pipeline** button in the sidebar to halt it.")
        current_node = st.session_state.current_node
        st.caption(f"Current step: **{current_node}**" if current_node else "Starting...")
        st.caption("See **2. Agent Graph** in the sidebar to watch this run live.")
    else:
        if st.session_state.last_run_message:
            kind, text = st.session_state.last_run_message
            getattr(st, kind)(text)
        requirement = st.text_area(
            "Requirement",
            placeholder="Build a FastAPI CRUD app for managing todo items, backed by SQLite.",
            height=120,
        )
        if not LLM_AVAILABLE:
            st.error(
                "No OpenAI API key configured. Set OPENAI_API_KEY in the sidebar "
                "before running the pipeline."
            )
        if st.button(
            "Run pipeline",
            type="primary",
            disabled=not requirement.strip() or not LLM_AVAILABLE,
        ):
            cancel_event = Event()
            result: dict = {}
            thread = Thread(
                target=_pipeline_worker,
                args=(requirement.strip(), cancel_event, result),
                daemon=True,
            )
            st.session_state.submitted_requirement = requirement.strip()
            st.session_state.cancel_event = cancel_event
            st.session_state.pipeline_result = result
            st.session_state.pipeline_thread = thread
            st.session_state.pipeline_running = True
            st.session_state.visited_nodes = []
            st.session_state.current_node = None
            st.session_state.last_run_message = None
            thread.start()
            st.rerun()

elif screen == "2. Agent Graph":
    st.subheader("Pipeline agent graph")
    if st.session_state.pipeline_running:
        st.info(f"Running — current step: **{st.session_state.current_node or 'starting...'}**")
    elif state is not None:
        st.success("Last run finished — highlighted nodes show the path it took.")
    else:
        st.caption("No run yet — this is the pipeline structure. Start a run on **1. Requirement Input** to watch it live.")
    st.graphviz_chart(_build_graph_dot(st.session_state.current_node, st.session_state.visited_nodes))

elif state is None:
    st.info("Run a requirement on the **1. Requirement Input** screen first.")

elif screen == "3. Execution View":
    st.subheader("Run summary")
    st.json(
        {
            "project_type": state.get("project_type"),
            "revision_count": state.get("revision_count"),
            "bug_report_count": len(state.get("bug_reports", [])),
            "approval_status": state.get("approval_status"),
            "quality_score": state.get("quality_score"),
            "elapsed_seconds": round(st.session_state.elapsed or 0, 1),
        }
    )
    st.subheader("Architecture plan")
    st.markdown(state.get("architecture_plan", "_(none)_"))
    st.subheader("Task breakdown")
    st.json(state.get("task_breakdown", []))

elif screen == "4. Generated Files":
    files = state.get("generated_files", [])
    if not files:
        st.info("No files were generated.")
    else:
        _LANGUAGE_BY_EXT = {
            "py": "python", "js": "javascript", "jsx": "javascript",
            "ts": "typescript", "tsx": "typescript", "json": "json",
            "md": "markdown", "html": "html", "css": "css", "sql": "sql",
            "sh": "bash", "yml": "yaml", "yaml": "yaml", "txt": "text",
        }
        paths = [f["path"] for f in files]

        col_files, col_content = st.columns([1, 2])
        with col_files:
            st.subheader(f"Files ({len(paths)})")
            selected_path = st.radio(
                "Select a file to view its content",
                paths,
                label_visibility="collapsed",
            )
        with col_content:
            st.subheader(selected_path)
            try:
                content = read_file(selected_path)
                ext = selected_path.rsplit(".", 1)[-1].lower() if "." in selected_path else ""
                st.code(content, language=_LANGUAGE_BY_EXT.get(ext, "text"))
            except MyException as e:
                logger.error("ui_read_file_failed", path=selected_path, error=str(e))
                st.error(f"Could not read file: {selected_path}")

elif screen == "5. Test Results":
    st.subheader("Generated test files")
    st.json(state.get("generated_tests", []))
    st.subheader("Execution results")
    st.json(state.get("execution_results", []))
    st.subheader("Bug reports / debug attempts")
    st.json(state.get("bug_reports", []))

elif screen == "6. Code Review":
    st.metric("Quality score", f"{state.get('quality_score', 0):.1f} / 10")
    st.write(state.get("review_feedback", "_(no feedback)_"))

elif screen == "7. Human Approval":
    status = state.get("approval_status", "pending")
    st.write(f"**Status:** {status}")
    auto = os.getenv("AUTO_APPROVE", "true").lower() == "true"
    st.caption(
        "AUTO_APPROVE is "
        + ("on — decided automatically from the quality score threshold." if auto else "off.")
    )

elif screen == "8. Download":
    project_dir = state.get("final_project_path")
    if project_dir and os.path.isdir(project_dir):
        try:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _dirs, filenames in os.walk(project_dir):
                    for name in filenames:
                        full = os.path.join(root, name)
                        zf.write(full, arcname=os.path.relpath(full, project_dir))
            st.download_button(
                "Download project as .zip",
                data=buffer.getvalue(),
                file_name=os.path.basename(project_dir) + ".zip",
                mime="application/zip",
            )
            metrics = compute_metrics(state, st.session_state.elapsed or 0)
            st.subheader("Evaluation metrics")
            st.json(metrics)
        except Exception as e:
            wrapped = MyException(e, sys)
            logger.error("ui_download_failed", project_dir=project_dir, error=str(wrapped))
            st.error(f"Could not prepare download: {e}")
    else:
        st.warning("No project directory found for this run.")