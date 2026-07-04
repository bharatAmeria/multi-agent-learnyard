"""Conditional routing logic between nodes.

Mirrors the routing spec:
  execution_agent -> review_agent (pass) | debug_agent (fail)
  debug_agent -> execution_agent
  review_agent -> coding_agent (score < threshold) | human_approval (score >= threshold)
  human_approval -> coding_agent (rejected) | memory_updater (approved)
"""
import sys

from config import settings
from exception import MyException
from graph.state import GraphState
from logger import GLOBAL_LOGGER as logger


def route_after_execution(state: GraphState) -> str:
    try:
        results = state.get("execution_results", [])
        passed = bool(results) and all(r.get("status") == "pass" for r in results)
        if passed:
            decision = "review_agent"
        elif len(state.get("bug_reports", [])) >= settings.max_debug_retries:
            # Give up retrying after max_debug_retries and send the
            # (still-failing) project to review anyway, rather than looping forever.
            decision = "review_agent"
        else:
            decision = "debug_agent"
        logger.info("route_after_execution", decision=decision)
        return decision
    except Exception as e:
        logger.error("route_after_execution_failed", error=str(e))
        raise MyException(e, sys) from e


def route_after_review(state: GraphState) -> str:
    try:
        score = state.get("quality_score", 0.0)
        if score >= settings.review_pass_threshold:
            decision = "human_approval"
        elif state.get("revision_count", 0) >= settings.max_review_revisions:
            # Give up revising after max_review_revisions and send the
            # best-effort project to human_approval anyway, rather than looping forever.
            decision = "human_approval"
        else:
            decision = "coding_agent"
        logger.info("route_after_review", decision=decision, score=score)
        return decision
    except Exception as e:
        logger.error("route_after_review_failed", error=str(e))
        raise MyException(e, sys) from e


def route_after_approval(state: GraphState) -> str:
    try:
        if state.get("approval_status") == "approved":
            decision = "memory_updater"
        elif state.get("revision_count", 0) >= settings.max_review_revisions:
            # Out of revisions — record the rejected project as-is instead of looping forever.
            decision = "memory_updater"
        else:
            decision = "coding_agent"
        logger.info("route_after_approval", decision=decision)
        return decision
    except Exception as e:
        logger.error("route_after_approval_failed", error=str(e))
        raise MyException(e, sys) from e
