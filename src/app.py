"""CLI entry point: run the full agent graph against a single user requirement."""
import os
import sys

# Make both the project root (for config.py) and src/ (for the sibling-style
# imports used throughout the codebase, e.g. `from exception import ...`)
# importable no matter how this script is invoked (uv run, plain python,
# from a different cwd, etc.) — removes the need to set PYTHONPATH by hand.
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_SRC_DIR)
for _p in (_ROOT_DIR, _SRC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json  # noqa: E402

from evaluation.metrics import compute_metrics  # noqa: E402
from exception import MyException  # noqa: E402
from graph.run import run_pipeline  # noqa: E402
from logger import GLOBAL_LOGGER as logger  # noqa: E402


def main() -> None:
    user_requirement = " ".join(sys.argv[1:]) or "Build a FastAPI CRUD application"
    logger.info("pipeline_starting", requirement=user_requirement)
    print(f"Requirement: {user_requirement}\n")

    try:
        final_state, elapsed = run_pipeline(user_requirement)
    except Exception as e:
        logger.error("pipeline_failed", error=str(e))
        raise MyException(e, sys) from e

    print("\n=== Final state ===")
    print(json.dumps(final_state, indent=2, default=str))

    metrics = compute_metrics(final_state, elapsed)
    print("\n=== Evaluation metrics ===")
    print(json.dumps(metrics, indent=2))

    print(f"\nProject written to: {final_state.get('final_project_path')}")
    logger.info(
        "pipeline_finished",
        project_path=final_state.get("final_project_path"),
        elapsed_seconds=round(elapsed, 2),
    )


if __name__ == "__main__":
    try:
        main()
    except MyException as e:
        logger.error("fatal_error", error=str(e))
        print(f"\nFatal error: {e}", file=sys.stderr)
        sys.exit(1)
