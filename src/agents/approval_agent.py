"""Input: reviewed project. Output: approved/rejected (human-in-the-loop)."""
import os
import sys

from config import settings
from exception import MyException
from graph.state import GraphState
from logger import GLOBAL_LOGGER as logger
from utils.tracing import traceable


@traceable(name="human_approval")
def human_approval(state: GraphState) -> GraphState:
    try:
        # AUTO_APPROVE=true (default) lets the pipeline run unattended — useful
        # for the Streamlit flow and for non-interactive environments. Set
        # AUTO_APPROVE=false to get a real y/n prompt on the CLI.
        auto_approve = os.getenv("AUTO_APPROVE", "true").lower() == "true"

        if auto_approve:
            passed = state.get("quality_score", 0.0) >= settings.review_pass_threshold
            state["approval_status"] = "approved" if passed else "rejected"
            logger.info("human_approval_auto", approval_status=state["approval_status"])
            return state

        print(f"\n--- Human Approval ---\nQuality score: {state.get('quality_score')}/10")
        print(f"Review feedback: {state.get('review_feedback')}")
        decision = input("Approve this project? [y/n]: ").strip().lower()
        state["approval_status"] = "approved" if decision.startswith("y") else "rejected"
        logger.info("human_approval_manual", approval_status=state["approval_status"])
        return state
    except Exception as e:
        logger.error("human_approval_failed", error=str(e))
        raise MyException(e, sys) from e
