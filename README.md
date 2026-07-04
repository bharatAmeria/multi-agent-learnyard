# AI Software Engineering Team

A LangGraph multi-agent system that turns a software requirement into a
tested, reviewed application: Requirement → Architecture → Planning →
Coding → Testing → Execution → Debug loop → Review → Human Approval →
Memory. MCP-style tool wrappers for filesystem/terminal/git/sqlite live in
`tools/` (local implementations today; swap in real MCP servers without
touching agent code).

See `SETUP.md` for exact install/run steps, and `docs/Build_Plan_and_ETA.md`
for the original phased build plan.

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY
python app.py "Build a FastAPI CRUD app for managing todo items"
# or:
streamlit run ui/app_ui.py
```

Without an `ANTHROPIC_API_KEY` set, every agent falls back to a small
deterministic offline stub so the graph still runs end to end (this is what
the test suite uses — no API key needed to run `pytest`).

## Layout

- `app.py` — CLI entry point
- `config.py` — settings & env loading
- `graph/` — state schema, routing, graph builder, `run.py` (shared run helper)
- `agents/` — one module per agent node, each calling Claude via `utils/llm.py`
- `tools/` — filesystem/terminal/git/sqlite wrappers (MCP-shaped interface)
- `utils/` — `llm.py` (Anthropic wrapper) and `tracing.py` (LangSmith decorator)
- `prompts/` — prompt notes (the live prompts are inline in each agent module)
- `schemas/` — pydantic models for structured I/O
- `memory/` — SQLite long-term memory store
- `ui/` — Streamlit app (`app_ui.py`)
- `evaluation/` — `metrics.py` scoring
- `tests/` — test suite for this project itself
- `generated_projects/` — output of each pipeline run (created on first use)
