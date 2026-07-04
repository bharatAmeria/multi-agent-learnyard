"""Input: failures. Output: code fixes, written back via the filesystem tool."""
import os
import sys

from exception import MyException
from graph.state import GraphState
from logger import GLOBAL_LOGGER as logger
from tools.filesystem_tool import read_file, write_file
from utils.llm import LLM_AVAILABLE, call_llm, strip_code_fences
from utils.tracing import traceable

SYSTEM = (
    "You are a debugging agent. You will be given a failing pytest log and "
    "the current content of ONE file from the project. If this file is the "
    "cause (or part of the cause) of the failure, return its corrected full "
    "content. If this file is unrelated to the failure, return it completely "
    "unchanged. Output ONLY the file content — no explanations, no markdown "
    "code fences, no commentary."
)

_MAX_TOKENS = 4096


def _relevant_files(generated_files: list, log: str) -> list:
    """Narrow the fix-up scope to files the failure log actually mentions.

    Sending every generated file's full content on every retry — and asking
    the LLM to hand all of them back as one JSON blob — is both expensive
    (full project re-sent as input tokens each loop) and fragile (a multi-file
    JSON response is exactly what truncates mid-string and comes back
    unparseable). pytest tracebacks name the file(s) involved, so use that to
    fix one file at a time and only touch what's implicated.
    """
    matched = [
        f for f in generated_files
        if f["path"] in log or os.path.basename(f["path"]) in log
    ]
    return matched or generated_files


@traceable(name="debug_agent")
def debug_agent(state: GraphState) -> GraphState:
    try:
        last_result = (state.get("execution_results") or [{}])[-1]
        log = last_result.get("log", "")

        if not LLM_AVAILABLE:
            state["bug_reports"] = (state.get("bug_reports") or []) + [
                {"log_excerpt": log[:300], "note": "offline mode: no automated fix applied"}
            ]
            # Clear results so we don't loop forever retrying the same failure with no fix.
            state["execution_results"] = [{"status": "pass", "log": "offline mode: skipping repair"}]
            logger.info("debug_agent_offline")
            return state

        candidates = _relevant_files(state.get("generated_files", []), log)

        fixed_paths = []
        failed_paths = []
        for f in candidates:
            path = f["path"]
            try:
                original = read_file(path)
            except MyException as e:
                logger.error("debug_agent_read_failed", path=path, error=str(e))
                failed_paths.append(path)
                continue

            user = f"Failing pytest log:\n{log}\n\nCurrent content of {path}:\n{original}"
            try:
                fixed = strip_code_fences(call_llm(SYSTEM, user, max_tokens=_MAX_TOKENS))
            except MyException as e:
                # One file's fix attempt failing is recoverable — keep going
                # on the rest, and let route_after_execution's
                # max_debug_retries cap decide when to give up entirely
                # rather than crashing the whole pipeline run.
                logger.error("debug_agent_fix_failed", path=path, error=str(e))
                failed_paths.append(path)
                continue

            if fixed.strip() and fixed != original:
                write_file(path, fixed)
                fixed_paths.append(path)

        state["bug_reports"] = (state.get("bug_reports") or []) + [
            {"log_excerpt": log[:300], "files_fixed": fixed_paths, "files_unfixable": failed_paths}
        ]
        # Force re-execution against the patched files. If nothing was
        # actually fixed this round, execution_results stays empty/"fail"-y
        # via re-running pytest, so the retry cap in routing.py is still
        # what eventually breaks the loop — no special-casing needed here.
        state["execution_results"] = []
        logger.info("debug_agent_completed", files_fixed=fixed_paths, files_unfixable=failed_paths)
        return state
    except Exception as e:
        logger.error("debug_agent_failed", error=str(e))
        raise MyException(e, sys) from e
