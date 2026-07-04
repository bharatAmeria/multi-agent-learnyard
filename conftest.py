"""Root pytest conftest.

This codebase uses sibling-style imports throughout (e.g.
`from exception import MyException`, `from graph.run import run_pipeline`)
rather than `src.`-prefixed imports. That means both the project root (for
config.py) and src/ (for everything else) need to be on sys.path for tests
to collect and run — this file makes that automatic for `pytest` / `uv run
pytest`, with no PYTHONPATH needed.
"""
import os
import sys

_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_ROOT_DIR, "src")
for _p in (_ROOT_DIR, _SRC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)
