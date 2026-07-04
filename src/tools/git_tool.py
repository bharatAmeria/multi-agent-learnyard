"""Wrapper around the Git MCP server."""
import sys

from exception import MyException
from logger import GLOBAL_LOGGER as logger
from tools.terminal_tool import run_command


def git_init(repo_path: str) -> dict:
    try:
        result = run_command("git init", cwd=repo_path)
        logger.info("git_init", repo_path=repo_path, status=result.get("status"))
        return result
    except Exception as e:
        logger.error("git_init_failed", repo_path=repo_path, error=str(e))
        raise MyException(e, sys) from e


def git_commit(repo_path: str, message: str) -> dict:
    try:
        run_command("git add -A", cwd=repo_path)
        result = run_command(f'git commit -m "{message}"', cwd=repo_path)
        logger.info("git_commit", repo_path=repo_path, status=result.get("status"))
        return result
    except Exception as e:
        logger.error("git_commit_failed", repo_path=repo_path, error=str(e))
        raise MyException(e, sys) from e
