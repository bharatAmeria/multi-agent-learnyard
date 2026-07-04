"""Phase 10: evaluation metrics — code quality, test pass rate, bug
resolution rate, review score, execution success rate, project
completion rate, latency."""
import sys

from exception import MyException
from graph.state import GraphState
from logger import GLOBAL_LOGGER as logger


def compute_metrics(state: GraphState, elapsed_seconds: float) -> dict:
    try:
        results = state.get("execution_results", [])
        total = len(results) or 1
        passed = sum(1 for r in results if r.get("status") == "pass")
        metrics = {
            "test_pass_rate": passed / total,
            "execution_success_rate": passed / total,
            "review_score": state.get("quality_score", 0.0),
            "bug_resolution_rate": None,  # TODO: track resolved vs reported bugs
            "project_completion_rate": 1.0 if state.get("final_project_path") else 0.0,
            "latency_seconds": elapsed_seconds,
        }
        logger.info("metrics_computed", **{k: v for k, v in metrics.items() if k != "bug_resolution_rate"})
        return metrics
    except Exception as e:
        logger.error("compute_metrics_failed", error=str(e))
        raise MyException(e, sys) from e
