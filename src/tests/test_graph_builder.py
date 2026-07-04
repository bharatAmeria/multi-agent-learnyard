"""Smoke test: the graph compiles and runs end to end without an API key.

Runs fully offline (no ANTHROPIC_API_KEY needed) — every agent's LLM_AVAILABLE
fallback path is what's exercised here.
"""
from graph.graph_builder import build_graph
from graph.run import make_initial_state


def test_graph_compiles_and_runs_offline(tmp_path):
    graph = build_graph()
    initial_state = make_initial_state(
        "Build a FastAPI CRUD application", str(tmp_path / "project")
    )
    final_state = graph.invoke(initial_state, config={"recursion_limit": 60})
    assert final_state["final_project_path"]
    assert final_state["approval_status"] in ("approved", "rejected")
    assert final_state["generated_files"]
